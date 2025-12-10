# define / route
# NOTE: All datetime values throughout this application are stored and compared in UTC.
# Use datetime.utcnow() for current time, and ensure auction start/end times are in UTC.
from crypt import methods
from multiprocessing import Value
import re
from unicodedata import category
from webbrowser import get
from flask import (
  Blueprint,
  flash,
  g,
  redirect,
  render_template,
  request,
  url_for,
)
from werkzeug.exceptions import abort
from datetime import datetime

from .auth import login_required
from db import get_db
# from models.user import User

bp = Blueprint(
  "home",
  __name__,
)  # no prefix, so this blueprint will be used as the root (index)


@bp.route("/")
def index():
  db = get_db()

  # Recent auctions (latest listed first)
  auctions = db.execute(
    """
    SELECT a.auction_id, a.auction_title, a.auction_desc, a.starting_price,
           a.auction_start, a.auction_end, i.item_name, i.item_desc,
           u.username AS seller_username, c.category_name
    FROM auctions a
    JOIN item i ON a.item_id = i.item_id
    LEFT JOIN category c ON i.category_id = c.category_id
    JOIN user u ON a.user_id = u.id
    ORDER BY a.auction_start DESC
    LIMIT 20
    """
  ).fetchall()

  # Users grouped by type
  users = db.execute(
    """
    SELECT id, username, f_name, l_name, user_type
    FROM user
    ORDER BY user_type, username
    """
  ).fetchall()

  # group users into dict: admins, representatives, customers
  grouped = {"admin": [], "representative": [], "customer": []}
  for u in users:
    t = u["user_type"] if u["user_type"] in grouped else "customer"
    grouped[t].append(u)

  return render_template(
    "home/index.html",
    auctions=auctions,
    users_grouped=grouped,
    now=datetime.utcnow(),
  )


@bp.route("/user/<int:user_id>")
def user_public(user_id):
  """Public view of a user profile (read-only)."""
  db = get_db()
  user = db.execute(
    """
    SELECT id, username, f_name, l_name, user_type, COALESCE(email, '') AS email
    FROM user
    WHERE id = ?
    """,
    (user_id,),
  ).fetchone()

  if user is None:
    abort(404, "User not found.")

  # auctions created by this user
  selling_auctions = db.execute(
    """
    SELECT a.auction_id, a.auction_title, a.auction_desc, a.starting_price,
           a.auction_start, a.auction_end, i.item_name, i.item_desc, c.category_name
    FROM auctions a
    JOIN item i ON a.item_id = i.item_id
    LEFT JOIN category c ON i.category_id = c.category_id
    WHERE a.user_id = ?
    ORDER BY a.auction_start DESC
    """,
    (user_id,),
  ).fetchall()

  # auctions the user has participated in (placed bids), excluding those they sold
  participating_auctions = db.execute(
    """
    SELECT DISTINCT a.*, i.item_name, i.item_desc, c.category_name,
           u.username as seller_username,
           MAX(b.bid_price) as your_highest_bid,
           b.bid_status,
           a.current_highest_bid
    FROM auctions a
    JOIN item i ON a.item_id = i.item_id
    LEFT JOIN category c ON i.category_id = c.category_id
    JOIN user u ON a.user_id = u.id
    JOIN bid b ON a.auction_id = b.auction_id
    WHERE b.user_id = ? AND a.user_id != ?
    GROUP BY a.auction_id
    ORDER BY a.auction_start DESC
    """,
    (user_id, user_id),
  ).fetchall()

  return render_template(
    "home/user_public.html",
    user=user,
    selling_auctions=selling_auctions,
    participating_auctions=participating_auctions,
    now=datetime.utcnow(),
  )


@bp.route("/me")
@login_required
def profile():
  db = get_db()
  user_id = g.user["id"]
  # query for selling auctions
  selling_auctions = db.execute(
    """
        SELECT a.*, i.item_name, i.item_desc, c.category_name
        FROM auctions a
        JOIN item i ON a.item_id = i.item_id
        LEFT JOIN category c ON i.category_id = c.category_id
        WHERE a.user_id = ?
        ORDER BY a.auction_start DESC
    """,
    (user_id,),
  ).fetchall()

  # query for participating auctions
  participating_auctions = db.execute(
    """
        SELECT DISTINCT a.*, i.item_name, i.item_desc, c.category_name, 
               u.username as seller_username,
               MAX(b.bid_price) as your_highest_bid,
               b.bid_status
        FROM auctions a
        JOIN item i ON a.item_id = i.item_id
        LEFT JOIN category c ON i.category_id = c.category_id
        JOIN user u ON a.user_id = u.id
        JOIN bid b ON a.auction_id = b.auction_id
        WHERE b.user_id = ? AND a.user_id != ?
        GROUP BY a.auction_id
        ORDER BY a.auction_start DESC
    """,
    (user_id, user_id),
  ).fetchall()
  # for value in participating_auctions[0]:
  #   print(value)

  # Get won auctions
  won_auctions = db.execute(
    """
      SELECT a.*, i.item_name, i.item_desc, c.category_name
      FROM auctions a
      JOIN item i ON a.item_id = i.item_id
      LEFT JOIN category c ON i.category_id = c.category_id
      JOIN bid b ON a.auction_id = b.auction_id
      WHERE b.user_id = ? AND b.bid_status = 'WON'
      ORDER BY a.auction_end DESC
  """,
    (user_id,),
  ).fetchall()

  # Calculate total spent
  total_spent_result = db.execute(
    """
      SELECT SUM(b.bid_price) as total_spent
      FROM bid b
      WHERE b.user_id = ? AND b.bid_status = 'WON'
  """,
    (user_id,),
  ).fetchone()

  total_spent = (
    total_spent_result["total_spent"] if total_spent_result["total_spent"] else 0
  )
  return render_template(
    "home/user_profile.html",
    selling_auctions=selling_auctions,
    participating_auctions=participating_auctions,
    won_auctions=won_auctions,
    total_spent=total_spent,
    now=datetime.utcnow(),
  )


@bp.route("/create_auction", methods=("GET", "POST"))
@login_required
def create_auction():
  # if get request, then just load the template
  # get categorires
  if request.method == "POST":
    # if post request, then get inputted information, and create a auction. redirect to auction view
    print(request.form)
    message = "New Auction Created!"
    # get information
    auction_title = request.form["auction_title"]
    auction_desc = request.form["auction_desc"]
    starting_price = request.form["starting_price"]
    # Use the UTC-converted values from the hidden fields
    auction_start = (
      request.form.get("auction_start_utc") or request.form["auction_start"]
    )
    auction_end = request.form.get("auction_end_utc") or request.form["auction_end"]

    item_name = request.form["item_name"]
    item_desc = request.form["item_desc"]
    item_category_id = request.form["item_category"]
    category_specific_details = {}
    # get each item detail and add to item_specific_details
    for detail_id, detail_value in [
      (det.replace("item_detail:", ""), val)
      for det, val in request.form.items()
      if det.startswith("item_detail:")
    ]:
      category_specific_details[detail_id] = detail_value
    print(category_specific_details)

    # create auction
    # need to create item first
    # get category_id

    try:
      db = get_db()
      # insert item
      item_cursor = db.execute(
        """
        INSERT INTO item (item_name, item_desc, category_id)
        VALUES (?, ?, ?)
        """,
        (
          item_name,
          item_desc,
          item_category_id,
        ),
      )
      # get item id for inserting category specific details
      item_id = item_cursor.lastrowid

      db.commit()

      # insert category specific details

      # for each detail:
      # get detail value from item_specific_details (using detail_name as key)
      # create new row in item_detail (item_id, detail_type_id, detail_value)
      for det_id, det_val in category_specific_details.items():
        db.execute(
          """
          INSERT INTO item_detail (item_id, detail_type_id, detail_value)
          VALUES (?, ?, ?)
          """,
          (item_id, det_id, det_val),
        )
        db.commit()

      # insert new auction
      # The datetime values are already in UTC ISO format from the client-side JavaScript
      # Parse them and store in the database
      # Handle both ISO format (with 'T' and 'Z') and standard format
      try:
        # Try ISO format first (from UTC conversion)
        start_dt = datetime.fromisoformat(auction_start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(auction_end.replace("Z", "+00:00"))
      except ValueError:
        # Fallback to standard datetime-local format (though this shouldn't happen with the new form)
        start_dt = datetime.strptime(auction_start, "%Y-%m-%dT%H:%M")
        end_dt = datetime.strptime(auction_end, "%Y-%m-%dT%H:%M")

      db.execute(
        """
        INSERT INTO auctions (item_id, auction_title, auction_desc, user_id, starting_price, auction_start, auction_end)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
          item_id,
          auction_title,
          auction_desc,
          g.user["id"],
          starting_price,  # starting price
          start_dt.strftime("%Y-%m-%d %H:%M:%S"),
          end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        ),
      )
      db.commit()

    except db.Error as e:
      message = f"Database error: {e}"
    message = "New Auction Created!"

    flash(message)
    return redirect(url_for("index"))

  # else get request:
  db = get_db()
  # want 2 hash tables:
  # { category_name: id}
  # { category_id: {detail_name: detail_id} }

  # get categories
  category_names_and_id = db.execute(
    """
    SELECT category_name, category_id 
    FROM category c
    """
  ).fetchall()
  # turn into a dictionary {cat_name: id}

  category_ids_and_details = {}  # { category_id: {detail_name: detail_id} }
  # for each category, get all details
  # join category with category_details
  for cat_id in [row["category_id"] for row in category_names_and_id]:
    details_rows = db.execute(
      """
      SELECT detail_name, detail_type_id
      FROM category_detail_type cd
      WHERE cd.category_id = ?
      """,
      (cat_id,),
    ).fetchall()

    category_ids_and_details[cat_id] = [
      (row["detail_name"], row["detail_type_id"]) for row in details_rows
    ]

  # turn into a dictionary {cat_name: id}
  category_names_and_id = {
    cat_name: cat_id for cat_name, cat_id in category_names_and_id
  }

  # print(categories[1]["category_name"])
  # print(category_ids_and_details)

  return render_template(
    "home/create_auction.html",
    category_ids_and_details=category_ids_and_details,
    category_names_and_id=category_names_and_id,
  )  # { category: [details] }


@bp.route("/forum", methods=("GET", "POST"))
def forum():
  """Forum view - display questions and allow users to post new questions."""
  db = get_db()

  if request.method == "POST":
    if g.user is None:
      flash("You must be logged in to post a question.")
      return redirect(url_for("auth.login"))

    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()

    if not title:
      flash("Title is required.")
    elif not body:
      flash("Question body is required.")
    else:
      try:
        db.execute(
          """
          INSERT INTO forum_question (user_id, title, body)
          VALUES (?, ?, ?)
          """,
          (g.user["id"], title, body),
        )
        db.commit()
        flash("Your question has been posted!")
        return redirect(url_for("home.forum"))
      except db.Error as e:
        flash(f"Database error: {e}")

  # Fetch all forum questions with asker info and answer details
  q_with_answers = db.execute(
    """
    SELECT 
      q.id,
      q.title,
      q.body,
      q.created_at,
      u.username AS asker_username,
      u.f_name,
      u.l_name,
      COUNT(a.id) AS answer_count,
      MAX(a.body) AS latest_answer_body,
      MAX(a.created_at) AS latest_answer_time,
      MAX(rep.username) AS latest_answerer_username
    FROM forum_question q
    JOIN user u ON q.user_id = u.id
    LEFT JOIN forum_answer a ON q.id = a.question_id
    LEFT JOIN user rep ON a.rep_id = rep.id
    GROUP BY q.id
    ORDER BY q.created_at DESC
    """
  ).fetchall()

  return render_template("home/forum.html", q_with_answers=q_with_answers)
