import functools
import sqlite3

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

    user = db.execute("SELECT * FROM user WHERE username = ?", (username,)).fetchone()

    if error is None:
      try:
        db.execute(
          "INSERT INTO user (username, password, f_name, l_name, user_type) VALUES (?, ?, ?, ?, ?)",
          (
            username,
            password,
            f_name,
            l_name,
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
