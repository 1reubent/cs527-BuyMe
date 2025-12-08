from datetime import datetime

from flask import (
  Blueprint,
  render_template,
  request,
)
from db import get_db

bp = Blueprint("search", __name__, url_prefix="/search")


@bp.route("/", methods=["GET"])
def search():
  """
  Search view with support for:
  - searching auctions or users
  - filtering auctions by category
  - filtering auctions by category-detail (via a free-text detail query)
  """
  db = get_db()
  query = request.args.get("q", "").strip()
  search_type = request.args.get("type", "auction")
  category_id_raw = request.args.get("category_id", "").strip()
  detail_query = request.args.get("detail_q", "").strip()

  category_id = None
  if category_id_raw:
    try:
      category_id = int(category_id_raw)
    except ValueError:
      category_id = None

  # For the filters UI: list all categories
  categories = db.execute(
    "SELECT category_id, category_name FROM category ORDER BY category_name"
  ).fetchall()

  results = []

  if search_type == "user":
    if query:
      results = db.execute(
        """
        SELECT id, username, f_name, l_name, user_type
        FROM user
        WHERE username LIKE ?
           OR f_name LIKE ?
           OR l_name LIKE ?
        """,
        (f"%{query}%", f"%{query}%", f"%{query}%"),
      ).fetchall()
    else:
      # get all users if no query provided
      results = db.execute(
        """
        SELECT id, username, f_name, l_name, user_type
        FROM user
        ORDER BY username
        """
      ).fetchall()
  else:
    # Auction search with optional category & detail filters
    where_clauses = []
    params = []

    if query:
      where_clauses.append(
        "(a.auction_title LIKE ? OR i.item_name LIKE ? OR i.item_desc LIKE ?)"
      )
      like_q = f"%{query}%"
      params.extend([like_q, like_q, like_q])

    if category_id is not None:
      where_clauses.append("c.category_id = ?")
      params.append(category_id)

    join_detail = False
    if detail_query:
      join_detail = True
      where_clauses.append("(dt.detail_name LIKE ? OR d.detail_value LIKE ?)")
      like_d = f"%{detail_query}%"
      params.extend([like_d, like_d])

    # Base query
    sql = """
      SELECT DISTINCT
        a.*,
        i.item_name,
        i.item_desc,
        c.category_name
      FROM auctions a
      JOIN item i ON a.item_id = i.item_id
      JOIN category c ON i.category_id = c.category_id
    """

    if join_detail:
      sql += """
      JOIN item_detail d ON d.item_id = i.item_id
      JOIN category_detail_type dt ON dt.detail_type_id = d.detail_type_id
      """

    if where_clauses:
      sql += " WHERE " + " AND ".join(where_clauses)

    sql += " ORDER BY a.auction_start DESC"

    results = db.execute(sql, tuple(params)).fetchall()

  return render_template(
    "search/results.html",
    search_type=search_type,
    results=results,
    query=query,
    now=datetime.now(),
    categories=categories,
    selected_category_id=category_id,
    detail_query=detail_query,
  )
