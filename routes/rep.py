from functools import wraps

from flask import (
  Blueprint,
  render_template,
  request,
  redirect,
  url_for,
  flash,
  g,
)
from werkzeug.security import generate_password_hash
from werkzeug.exceptions import abort

from db import get_db
from .auth import login_required
from .alerts import create_alert

bp = Blueprint("rep", __name__, url_prefix="/rep")


def rep_required(view):
  @wraps(view)
  def wrapped_view(**kwargs):
    if g.user is None or g.user["user_type"] not in ("representative", "admin"):
      abort(403)
    return view(**kwargs)

  return wrapped_view


@bp.route("/dashboard")
@login_required
@rep_required
def dashboard():
  return render_template("rep/dashboard.html")


# --- User search & modify --- #


@bp.route("/users", methods=["GET"])
@login_required
@rep_required
def search_users():
  query = request.args.get("q", "").strip()
  db = get_db()
  users = []
  if query:
    users = db.execute(
      """
      SELECT id, username, f_name, l_name, user_type, 
             COALESCE(email, '') AS email
      FROM user
      WHERE username LIKE ?
         OR f_name LIKE ?
         OR l_name LIKE ?
         OR COALESCE(email, '') LIKE ?
      ORDER BY username
      """,
      (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"),
    ).fetchall()

  return render_template("rep/user_search.html", query=query, users=users)


@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@rep_required
def edit_user(user_id):
  db = get_db()
  user = db.execute(
    """
    SELECT id, username, f_name, l_name, user_type, 
           COALESCE(email, '') AS email
    FROM user
    WHERE id = ?
    """,
    (user_id,),
  ).fetchone()

  if user is None:
    abort(404, "User not found.")

  if request.method == "POST":
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not username:
      flash("Username is required.")
      return redirect(url_for("rep.edit_user", user_id=user_id))

    if password:
      db.execute(
        """
        UPDATE user
        SET username = ?, email = ?, password = ?
        WHERE id = ?
        """,
        (username, email, generate_password_hash(password), user_id),
      )
    else:
      db.execute(
        """
        UPDATE user
        SET username = ?, email = ?
        WHERE id = ?
        """,
        (username, email, user_id),
      )
    db.commit()
    flash("User updated successfully.")
    return redirect(url_for("rep.search_users", q=username))

  return render_template("rep/edit_user.html", user=user)


# --- Auction monitoring --- #


@bp.route("/auctions", methods=["GET"])
@login_required
@rep_required
def list_auctions():
  """
  List all auctions so that a customer representative can inspect
  and remove illegal ones.
  """
  db = get_db()
  auctions = db.execute(
    """
    SELECT 
      a.auction_id,
      a.auction_title,
      a.auction_desc,
      a.auction_start,
      a.auction_end,
      i.item_name,
      u.username AS seller_username
    FROM auctions a
    JOIN item i ON a.item_id = i.item_id
    JOIN user u ON a.user_id = u.id
    ORDER BY a.auction_start DESC
    """
  ).fetchall()

  return render_template("rep/auctions.html", auctions=auctions)


@bp.route("/auctions/<int:auction_id>/remove", methods=["POST"])
@login_required
@rep_required
def remove_auction(auction_id):
  """
  Remove an illegal auction.
  This deletes the auction and all associated bids
  and sends alerts to the seller and any bidders.
  """
  db = get_db()
  auction = db.execute(
    """
    SELECT a.auction_id, a.auction_title, u.id AS seller_id
    FROM auctions a
    JOIN user u ON a.user_id = u.id
    WHERE a.auction_id = ?
    """,
    (auction_id,),
  ).fetchone()

  if auction is None:
    abort(404, "Auction not found.")

  # Collect bidders
  bidders = db.execute(
    """
    SELECT DISTINCT user_id
    FROM bid
    WHERE auction_id = ?
    """,
    (auction_id,),
  ).fetchall()

  # Delete bids and the auction itself
  db.execute("DELETE FROM bid WHERE auction_id = ?", (auction_id,))
  db.execute("DELETE FROM auctions WHERE auction_id = ?", (auction_id,))
  db.commit()

  # Alerts
  create_alert(
    auction["seller_id"],
    f"Your auction '{auction['auction_title']}' has been removed by a customer representative for violating site policy.",
  )

  for row in bidders:
    uid = row["user_id"]
    if uid == auction["seller_id"]:
      continue
    create_alert(
      uid,
      f"An auction you bid on ('{auction['auction_title']}') has been removed by a customer representative. Your bids are no longer valid.",
    )

  flash("Auction removed successfully.")
  return redirect(url_for("rep.list_auctions"))


# --- Forum (Q&A) --- #


@bp.route("/forum")
@login_required
@rep_required
def forum():
  """List all questions and whether they have answers."""
  db = get_db()
  questions = db.execute(
    """
    SELECT 
      q.id,
      q.title,
      q.body,
      q.created_at,
      u.username AS asker_username,
      EXISTS (
        SELECT 1 FROM forum_answer a
        WHERE a.question_id = q.id
      ) AS has_answer
    FROM forum_question q
    JOIN user u ON q.user_id = u.id
    ORDER BY q.created_at DESC
    """
  ).fetchall()

  return render_template("rep/forum_list.html", questions=questions)


@bp.route("/forum/<int:question_id>", methods=["GET", "POST"])
@login_required
@rep_required
def forum_detail(question_id):
  db = get_db()
  question = db.execute(
    """
    SELECT 
      q.id,
      q.title,
      q.body,
      q.created_at,
      u.username AS asker_username
    FROM forum_question q
    JOIN user u ON q.user_id = u.id
    WHERE q.id = ?
    """,
    (question_id,),
  ).fetchone()

  if question is None:
    abort(404, "Question not found.")

  if request.method == "POST":
    body = request.form.get("body", "").strip()
    if not body:
      flash("Answer body is required.")
    else:
      db.execute(
        """
        INSERT INTO forum_answer (question_id, rep_id, body)
        VALUES (?, ?, ?)
        """,
        (question_id, g.user["id"], body),
      )
      db.commit()
      flash("Answer posted.")
    return redirect(url_for("rep.forum_detail", question_id=question_id))

  answers = db.execute(
    """
    SELECT 
      a.id,
      a.body,
      a.created_at,
      u.username AS rep_username
    FROM forum_answer a
    JOIN user u ON a.rep_id = u.id
    WHERE a.question_id = ?
    ORDER BY a.created_at ASC
    """,
    (question_id,),
  ).fetchall()

  return render_template(
    "rep/forum_detail.html",
    question=question,
    answers=answers,
  )
