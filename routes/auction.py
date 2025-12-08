from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import (
  Blueprint,
  render_template,
  request,
  redirect,
  url_for,
  flash,
  g,
)
from werkzeug.exceptions import abort

from db import get_db
from .auth import login_required
from .alerts import create_alert

bp = Blueprint("auction", __name__, url_prefix="/auction")


def _get_auction_or_404(auction_id):
  db = get_db()
  auction = db.execute(
    """
    SELECT 
      a.*,
      i.item_name,
      i.item_desc,
      i.category_id,
      c.category_name,
      u.id AS seller_id,
      u.username AS seller_username,
      u.f_name AS seller_fname,
      u.l_name AS seller_lname
    FROM auctions a
    JOIN item i ON a.item_id = i.item_id
    JOIN category c ON i.category_id = c.category_id
    JOIN user u ON a.user_id = u.id
    WHERE a.auction_id = ?
    """,
    (auction_id,),
  ).fetchone()

  if auction is None:
    abort(404, f"Auction {auction_id} does not exist.")

  return auction


def _get_current_highest_bid(db, auction_id):
  """Return the current highest bid row for an auction, or None."""
  return db.execute(
    """
    SELECT b.bid_id, b.user_id, b.bid_price, b.auction_bid_time
    FROM bid b
    WHERE b.auction_id = ?
    ORDER BY b.bid_price DESC, b.auction_bid_time ASC
    LIMIT 1
    """,
    (auction_id,),
  ).fetchone()


def _run_auto_bidding(auction_id, auction_title):
  """
  Run automatic bidding for all active auto-bid configurations on this auction.

  This implements a simple proxy bidding:
  - Each auto-bidder has a max_bid and an increment.
  - We repeatedly let the best candidate raise the price up to
    min(max_bid, current_price + increment) until no one can beat the current price.
  """
  db = get_db()

  while True:
    highest = _get_current_highest_bid(db, auction_id)

    if highest:
      current_price = Decimal(highest["bid_price"])
      current_user_id = highest["user_id"]
    else:
      auction = db.execute(
        "SELECT starting_price FROM auctions WHERE auction_id = ?",
        (auction_id,),
      ).fetchone()
      if auction is None:
        return
      current_price = Decimal(auction["starting_price"])
      current_user_id = None

    # All active autobids whose max > current_price
    auto_bids = db.execute(
      """
      SELECT id, auction_id, user_id, max_bid, increment, active
      FROM auto_bid
      WHERE auction_id = ? AND active = 1 AND max_bid > ?
      """,
      (auction_id, float(current_price)),
    ).fetchall()

    candidates = []

    for ab in auto_bids:
      # Skip if already the current highest bidder
      if current_user_id is not None and ab["user_id"] == current_user_id:
        continue

      max_bid = Decimal(ab["max_bid"])
      inc = Decimal(ab["increment"])
      new_price = min(max_bid, current_price + inc)

      if new_price > current_price:
        candidates.append((new_price, ab))

    if not candidates:
      break  # No autobidder can raise the price further

    # Choose candidate that results in the highest new bid
    candidates.sort(key=lambda x: x[0], reverse=True)
    new_price, chosen = candidates[0]

    prev_highest = highest

    # Mark previous highest as OUTBID and alert that user
    if prev_highest is not None:
      db.execute(
        "UPDATE bid SET bid_status = 'OUTBID' WHERE bid_id = ?",
        (prev_highest["bid_id"],),
      )
      create_alert(
        prev_highest["user_id"],
        f"You have been outbid on auction '{auction_title}'.",
      )

    # Insert new LEADING bid from autobidder
    db.execute(
      """
      INSERT INTO bid (auction_id, user_id, bid_price, bid_status)
      VALUES (?, ?, ?, 'LEADING')
      """,
      (auction_id, chosen["user_id"], float(new_price)),
    )
    db.commit()
    # Loop again in case there is another auto-bidder that can beat this price


@bp.route("/<int:auction_id>", methods=["GET", "POST"])
def view(auction_id):
  """
  Auction View
  - View item info, seller info, highest bid, recent bidders
  - View bid history
  - Show similar items listed within the past month (recommended section)
  - POST: place a manual bid (requires login)
  """
  db = get_db()
  auction = _get_auction_or_404(auction_id)

  # fetch item-specific details (category detail types + values)
  item_details = db.execute(
    """
    SELECT cdt.detail_name, id.detail_value
    FROM item_detail id
    JOIN category_detail_type cdt ON id.detail_type_id = cdt.detail_type_id
    WHERE id.item_id = ?
    ORDER BY cdt.detail_name
    """,
    (auction["item_id"],),
  ).fetchall()

  # normalize auction end to a datetime for comparisons
  now = datetime.now()
  auction_end = auction["auction_end"]
  end_dt = None
  if isinstance(auction_end, str):
    try:
      end_dt = datetime.fromisoformat(auction_end)
    except Exception:
      try:
        end_dt = datetime.strptime(auction_end, "%Y-%m-%d %H:%M:%S")
      except Exception:
        end_dt = None
  elif isinstance(auction_end, datetime):
    end_dt = auction_end

  is_over = False
  if end_dt is not None:
    is_over = now > end_dt

  # whether current user is the seller
  is_seller = g.user is not None and g.user["id"] == auction["seller_id"]

  # Handle manual bid submission
  if request.method == "POST":
    if g.user is None:
      flash("You must be logged in to place a bid.")
      return redirect(url_for("auth.login"))

    # Prevent the seller from placing a bid on their own auction
    if is_seller:
      flash("You cannot place a bid on your own auction.")
      return redirect(url_for("auction.view", auction_id=auction_id))

    # Prevent bidding on ended auctions
    if is_over:
      flash("This auction has ended; bidding is closed.")
      return redirect(url_for("auction.view", auction_id=auction_id))

    bid_amount_raw = request.form.get("bid_amount", "").strip()
    try:
      bid_amount = Decimal(bid_amount_raw)
    except InvalidOperation:
      flash("Invalid bid amount.")
      return redirect(url_for("auction.view", auction_id=auction_id))

    # Highest bid BEFORE this new bid
    prev_highest = _get_current_highest_bid(db, auction_id)

    # Determine minimum required amount
    min_required = Decimal(auction["starting_price"])
    if prev_highest is not None:
      min_required = max(min_required, Decimal(prev_highest["bid_price"]))

    if bid_amount <= min_required:
      flash(f"Your bid must be greater than the current highest bid ({min_required}).")
      return redirect(url_for("auction.view", auction_id=auction_id))

    # Mark existing bids as OUTBID
    db.execute(
      """
      UPDATE bid
      SET bid_status = 'OUTBID'
      WHERE auction_id = ? AND bid_status IN ('PLACED','LEADING')
      """,
      (auction_id,),
    )

    # Alert the previous highest bidder (if any)
    if prev_highest is not None:
      create_alert(
        prev_highest["user_id"],
        f"You have been outbid on auction '{auction['auction_title']}'.",
      )

    # Insert new LEADING bid
    db.execute(
      """
      INSERT INTO bid (auction_id, user_id, bid_price, bid_status)
      VALUES (?, ?, ?, 'LEADING')
      """,
      (auction_id, g.user["id"], float(bid_amount)),
    )
    db.commit()

    # After manual bid, run auto-bidding to see if any autobidder can beat it
    _run_auto_bidding(auction_id, auction["auction_title"])

    # update current highest bidder
    highest = _get_current_highest_bid(db, auction_id)
    if highest is not None:
      # update highest bid in auctions table
      db.execute(
        """
        UPDATE auctions
        SET current_highest_bid = ?
        WHERE auction_id = ?
        """,
        (float(highest["bid_price"]), auction_id),
      )
      db.commit()

    flash("Bid placed successfully!")
    return redirect(url_for("auction.view", auction_id=auction_id))

  # Highest bid (after any updates)
  highest_bid = db.execute(
    """
    SELECT b.bid_id, b.bid_price, b.auction_bid_time,
           u.username AS bidder_username
    FROM bid b
    JOIN user u ON b.user_id = u.id
    WHERE b.auction_id = ?
    ORDER BY b.bid_price DESC, b.auction_bid_time ASC
    LIMIT 1
    """,
    (auction_id,),
  ).fetchone()

  # Recent bidders
  recent_bidders = db.execute(
    """
    SELECT DISTINCT u.id, u.username
    FROM bid b
    JOIN user u ON b.user_id = u.id
    WHERE b.auction_id = ?
    ORDER BY b.auction_bid_time DESC
    LIMIT 5
    """,
    (auction_id,),
  ).fetchall()

  # Full bid history
  bid_history = db.execute(
    """
    SELECT b.bid_id, b.bid_price, b.auction_bid_time,
           u.username AS bidder_username, b.bid_status
    FROM bid b
    JOIN user u ON b.user_id = u.id
    WHERE b.auction_id = ?
    ORDER BY b.bid_price DESC, b.auction_bid_time ASC
    """,
    (auction_id,),
  ).fetchall()

  # Recommended similar auctions (same category, past 30 days)
  one_month_ago = datetime.now() - timedelta(days=30)
  similar_auctions = db.execute(
    """
    SELECT 
      a.auction_id,
      a.auction_title,
      a.starting_price,
      a.auction_start,
      a.auction_end,
      i.item_name,
      c.category_name
    FROM auctions a
    JOIN item i ON a.item_id = i.item_id
    JOIN category c ON i.category_id = c.category_id
    WHERE i.category_id = ?
      AND a.auction_id != ?
      AND a.auction_start >= ?
    ORDER BY a.auction_start DESC
    LIMIT 10
    """,
    (auction["category_id"], auction_id, one_month_ago),
  ).fetchall()

  # Existing auto-bid configuration for current user (if any)
  auto_bid_config = None
  if g.user is not None:
    auto_bid_config = db.execute(
      """
      SELECT id, max_bid, increment, active
      FROM auto_bid
      WHERE auction_id = ? AND user_id = ?
      """,
      (auction_id, g.user["id"]),
    ).fetchone()

  return render_template(
    "auction/view.html",
    auction=auction,
    highest_bid=highest_bid,
    recent_bidders=recent_bidders,
    bid_history=bid_history,
    similar_auctions=similar_auctions,
    auto_bid_config=auto_bid_config,
    is_over=is_over,
    is_seller=is_seller,
    now=now,
    item_details=item_details,
  )


@bp.route("/<int:auction_id>/auto_bid", methods=["POST"])
@login_required
def set_auto_bid(auction_id):
  """
  Configure automatic bidding for the current user on this auction.
  User specifies an upper limit (max_bid) and an optional increment.
  """
  auction = _get_auction_or_404(auction_id)
  db = get_db()

  max_bid_raw = request.form.get("max_bid", "").strip()
  increment_raw = request.form.get("increment", "").strip() or "1.00"

  try:
    max_bid = Decimal(max_bid_raw)
    increment = Decimal(increment_raw)
  except InvalidOperation:
    flash("Invalid numbers for auto-bid.")
    return redirect(url_for("auction.view", auction_id=auction_id))

  if max_bid <= 0 or increment <= 0:
    flash("Max bid and increment must be positive.")
    return redirect(url_for("auction.view", auction_id=auction_id))

  # Upsert auto-bid configuration for this user & auction
  existing = db.execute(
    """
    SELECT id FROM auto_bid
    WHERE auction_id = ? AND user_id = ?
    """,
    (auction_id, g.user["id"]),
  ).fetchone()

  if existing:
    db.execute(
      """
      UPDATE auto_bid
      SET max_bid = ?, increment = ?, active = 1
      WHERE id = ?
      """,
      (float(max_bid), float(increment), existing["id"]),
    )
  else:
    db.execute(
      """
      INSERT INTO auto_bid (auction_id, user_id, max_bid, increment, active)
      VALUES (?, ?, ?, ?, 1)
      """,
      (auction_id, g.user["id"], float(max_bid), float(increment)),
    )
  db.commit()

  # After setting auto-bid, we can try to run auto-bidding in case
  # there are existing bids that should trigger it.
  _run_auto_bidding(auction_id, auction["auction_title"])

  flash("Automatic bidding settings saved.")
  return redirect(url_for("auction.view", auction_id=auction_id))
