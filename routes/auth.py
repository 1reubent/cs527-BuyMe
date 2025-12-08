import functools
import sqlite3
from datetime import datetime

from flask import (
  Blueprint,
  flash,
  g,
  redirect,
  render_template,
  request,
  session,
  url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db
# from models.user import User

bp = Blueprint("auth", __name__, url_prefix="/auth")


# store authentication related views here, as part of the /auth blueprint
@bp.route("/register", methods=("GET", "POST"))
def register():
  # TODO: register different types
  if request.method == "POST":
    f_name = request.form["f_name"]
    l_name = request.form["l_name"]
    username = request.form["username"]
    password = request.form["password"]
    email = request.form["email"]

    db = get_db()
    error = None

    if not username:
      error = "Username is required."
    elif not password:
      error = "Password is required."
    elif not f_name:
      error = "First Name is required."
    elif not l_name:
      error = "Last Name is required."
    elif not email:
      error = "Email is required."

    user = db.execute("SELECT * FROM user WHERE username = ?", (username,)).fetchone()

    if error is None:
      try:
        db.execute(
          "INSERT INTO user (username, password, f_name, l_name, email, user_type) VALUES (?, ?, ?, ?, ?, ?)",
          (
            username,
            password,
            f_name,
            l_name,
            email,
            "customer",
          ),
        )
        # TODO: pass `generate_password_hash(password)` for password to hash it
        db.commit()
      except db.IntegrityError:
        error = f"User {username} is already registered."
      else:
        return redirect(url_for("auth.login"))
        # redirect to login view

    flash(error)

  return render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
def login():
  if request.method == "POST":
    username = request.form["username"]
    password = request.form["password"]
    db = get_db()
    error = None
    user = db.execute("SELECT * FROM user WHERE username = ?", (username,)).fetchone()

    if user is None:
      error = "Incorrect username."
    elif not user["password"] == password:
      error = "Incorrect password."

    # TODO: check with check_password_hash(user["password"], password) if hashing during registration

    if error is None:
      # store the userID as a new session. for subsequent requests from this user, load their information
      session.clear()
      print(user)
      session["id"] = user["id"]  # pyright: ignore[reportOptionalMemberAccess]
      # redirect to /rep/dashboard or /index or /admin/dashboard based on user type
      if user["user_type"] == "representative":
        return redirect(url_for("rep.dashboard"))
      elif user["user_type"] == "admin":
        return redirect(url_for("admin.dashboard"))
      else:
        return redirect(url_for("index"))

    flash(error)

  return render_template("auth/login.html")


# this function will be run before all view functions. It stores the user information in g.user which lasts for the entire request.
@bp.before_app_request
def load_logged_in_user():
  user_id = session.get("id")

  if user_id is None:
    g.user = None
  else:
    g.user = get_db().execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()

  # Check for ended auctions and mark winners
  _process_ended_auctions()


def _process_ended_auctions():
  """
  Check for auctions that have ended and mark the highest bidder as WON.
  Send an alert to the winning bidder.
  This runs on every request via before_app_request.
  """
  db = get_db()
  now = datetime.now()

  # Find all auctions that have ended but haven't been processed yet
  # (bid_status is still LEADING, not yet changed to WON)
  ended_auctions = db.execute(
    """
    SELECT DISTINCT a.auction_id, a.auction_title
    FROM auctions a
    WHERE datetime(a.auction_end) < datetime('now')
    AND EXISTS (
      SELECT 1 FROM bid b
      WHERE b.auction_id = a.auction_id
      AND b.bid_status = 'LEADING'
    )
    """
  ).fetchall()

  print(ended_auctions)

  for auction in ended_auctions:
    auction_id = auction["auction_id"]
    auction_title = auction["auction_title"]

    # Get the highest bid (LEADING bid)
    highest_bid = db.execute(
      """
      SELECT b.bid_id, b.user_id, b.bid_price
      FROM bid b
      WHERE b.auction_id = ? AND b.bid_status = 'LEADING'
      ORDER BY b.bid_price DESC
      LIMIT 1
      """,
      (auction_id,),
    ).fetchone()

    if highest_bid:
      # Mark this bid as WON
      db.execute(
        "UPDATE bid SET bid_status = 'WON' WHERE bid_id = ?",
        (highest_bid["bid_id"],),
      )

      # Mark all other bids as LOST
      db.execute(
        """
        UPDATE bid
        SET bid_status = 'LOST'
        WHERE auction_id = ? AND bid_id != ? AND bid_status IN ('OUTBID', 'PLACED')
        """,
        (auction_id, highest_bid["bid_id"]),
      )

      # Create alert for winner
      db.execute(
        """
        INSERT INTO alert (user_id, message)
        VALUES (?, ?)
        """,
        (
          highest_bid["user_id"],
          f"Congratulations! You won the auction '{auction_title}' with a bid of ${highest_bid['bid_price']:.2f}",
        ),
      )

      db.commit()


# clear the session, so that load_logged_in_user won't load the user for subsequent requests
@bp.route("/logout")
def logout():
  session.clear()
  return redirect(url_for("index"))


# takes a view and returns a wrapped version of it that redirects to the login page if the user is not logged in
# userful for requests that require login, like writing blog posts.
# now any view tagged with @login_required will be wrapped with wrapped_view (checks login)
def login_required(view):
  @functools.wraps(view)
  def wrapped_view(**kwargs):
    if g.user is None:
      return redirect(url_for("auth.login"))

    return view(**kwargs)  # return original view

  return wrapped_view


# Allow users to delete their own account. This will attempt to remove
# related records (bids, forum posts, auctions and related items) and
# then remove the user row. It requires the user to be logged in.
@bp.route("/delete", methods=("POST",))
@login_required
def delete():
  db = get_db()
  user_id = g.user["id"]
  try:
    # remove bids made by the user
    db.execute("DELETE FROM bid WHERE user_id = ?", (user_id,))

    # remove forum answers where this user acted as a rep
    db.execute("DELETE FROM forum_answer WHERE rep_id = ?", (user_id,))

    # remove forum questions created by the user
    db.execute("DELETE FROM forum_question WHERE user_id = ?", (user_id,))

    # find auctions created by the user so we can remove referenced items
    auctions = db.execute(
      "SELECT auction_id, item_id FROM auctions WHERE user_id = ?",
      (user_id,),
    ).fetchall()

    item_ids = [a["item_id"] for a in auctions]
    for item_id in item_ids:
      db.execute("DELETE FROM item_detail WHERE item_id = ?", (item_id,))
      db.execute("DELETE FROM item WHERE item_id = ?", (item_id,))

    # remove auctions created by the user
    db.execute("DELETE FROM auctions WHERE user_id = ?", (user_id,))

    # finally remove the user record
    db.execute("DELETE FROM user WHERE id = ?", (user_id,))
    db.commit()
  except Exception as exc:  # pragma: no cover - defensive fallback
    db.rollback()
    flash("Could not delete account: " + str(exc))
    return redirect(url_for("home.profile"))

  # clear the session so user is logged out after deletion
  session.clear()
  flash("Your account has been deleted.")
  return redirect(url_for("index"))
