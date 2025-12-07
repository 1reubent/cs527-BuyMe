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

bp = Blueprint("search", __name__, url_prefix="/search")


@bp.route("/")
def search():
  query = request.args.get("q", "").strip()
  search_type = request.args.get("type", "auction")

  if not query:
    # If no query, just render the search page
    return render_template(
      "search/results.html", search_type=search_type, results=[], query=""
    )

  db = get_db()
  results = []

  if search_type == "auction":
    # Search auctions by item name or description
    results = db.execute(
      """
      SELECT a.*, i.item_name, i.item_desc, c.category_name,
             u.username as seller_username
      FROM auctions a
      JOIN item i ON a.item_id = i.item_id
      LEFT JOIN category c ON i.category_id = c.category_id
      JOIN user u ON a.user_id = u.id
      WHERE i.item_name LIKE ? OR i.item_desc LIKE ?
      ORDER BY a.auction_start DESC
      """,
      (f"%{query}%", f"%{query}%"),
    ).fetchall()

  elif search_type == "user":
    # Search users by username or name
    results = db.execute(
      """
      SELECT id, username, f_name, l_name, user_type
      FROM user
      WHERE username LIKE ? OR f_name LIKE ? OR l_name LIKE ?
      """,
      (f"%{query}%", f"%{query}%", f"%{query}%"),
    ).fetchall()

  return render_template(
    "search/results.html",
    search_type=search_type,
    results=results,
    query=query,
    now=datetime.now(),
  )
