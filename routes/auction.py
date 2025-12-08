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

bp = Blueprint("auction", __name__, url_prefix="/auction")


def _get_auction_or_404(auction_id):
  db = get_db()
  auction = db.execute(
    """
    SELECT 
      a.auction_id,
      a.item_id,
      a.auction_title,
      a.auction_desc,
      a.starting_price,
      a.auction_start,
      a.auction_end,
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


@bp.route("/<int:auction_id>", methods=["GET", "POST"])
def view(auction_id):
  """
  Auction View
  - View item info, seller info, highest bid, recent bidders
  - View bid history
  - Show similar items listed within the past month (recommended section)
  - POST: place a bid (requires login)
  """
  db = get_db()
  auction = _get_auction_or_404(auction_id)

  # Handle bid submission
  if request.method == "POST":
    if g.user is None:
      flash("You must be logged in to place a bid.")
      return redirect(url_for("auth.login"))

    # Prevent the seller from placing a bid on their own auction
    if g.user["id"] == auction["seller_id"]:
      flash("You cannot place a bid on your own auction.")
      return redirect(url_for("auction.view", auction_id=auction_id))

    bid_amount_raw = request.form.get("bid_amount", "").strip()
    try:
      bid_amount = Decimal(bid_amount_raw)
    except InvalidOperation:
      flash("Invalid bid amount.")
      return redirect(url_for("auction.view", auction_id=auction_id))

    # Current highest bid
    highest_bid_row = db.execute(
      """
      SELECT MAX(bid_price) AS max_price
      FROM bid
      WHERE auction_id = ?
      """,
      (auction_id,),
    ).fetchone()

    min_required = auction["starting_price"]
    if highest_bid_row["max_price"] is not None:
      min_required = max(Decimal(min_required), Decimal(highest_bid_row["max_price"]))

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

    # Insert new LEADING bid
    db.execute(
      """
      INSERT INTO bid (auction_id, user_id, bid_price, bid_status)
      VALUES (?, ?, ?, 'LEADING')
      """,
      (auction_id, g.user["id"], float(bid_amount)),
    )
    db.commit()
    flash("Bid placed successfully!")
    # Update current highest bid in auctions table
    db.execute(
      """
      UPDATE auctions
      SET current_highest_bid = ?
      WHERE auction_id = ?
      """,
      (float(bid_amount), auction_id),
    )
    db.commit()
    return redirect(url_for("auction.view", auction_id=auction_id))

  # Highest bid
  highest_bid = db.execute(
    """
    SELECT b.bid_id, b.bid_price, b.auction_bid_time,
           u.username AS bidder_username
    FROM bid b
    JOIN user u ON b.user_id = u.id
    WHERE b.auction_id = ?
    ORDER BY b.bid_price DESC
    LIMIT 1
    """,
    (auction_id,),
  ).fetchone()

  # Recent bidders (distinct, last 5)
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

  # Full bid history (latest first)
  bid_history = db.execute(
    """
    SELECT b.bid_id, b.bid_price, b.auction_bid_time,
           u.username AS bidder_username, b.bid_status
    FROM bid b
    JOIN user u ON b.user_id = u.id
    WHERE b.auction_id = ?
    ORDER BY b.auction_bid_time DESC
    """,
    (auction_id,),
  ).fetchall()

  # Recommended similar auctions (same category, past month)
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

  return render_template(
    "auction/view.html",
    auction=auction,
    highest_bid=highest_bid,
    recent_bidders=recent_bidders,
    bid_history=bid_history,
    similar_auctions=similar_auctions,
  )
