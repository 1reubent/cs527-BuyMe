from functools import wraps
from collections import defaultdict

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

bp = Blueprint("admin", __name__, url_prefix="/admin")


def admin_required(view):
  @wraps(view)
  def wrapped_view(**kwargs):
    if g.user is None or g.user["user_type"] != "admin":
      abort(403)
    return view(**kwargs)

  return wrapped_view


@bp.route("/dashboard")
@admin_required
def dashboard():
  return render_template("admin/dashboard.html")


# --- Category management --- #


@bp.route("/categories", methods=["GET", "POST"])
@admin_required
def manage_categories():
  db = get_db()

  if request.method == "POST":
    category_name = request.form.get("category_name", "").strip()
    detail_names = request.form.get("detail_names", "").strip()

    if not category_name:
      flash("Category name is required.")
      return redirect(url_for("admin.manage_categories"))

    cursor = db.execute(
      "INSERT INTO category (category_name) VALUES (?)",
      (category_name,),
    )
    category_id = cursor.lastrowid

    if detail_names:
      for detail_name in [d.strip() for d in detail_names.split(",") if d.strip()]:
        db.execute(
          """
          INSERT INTO category_detail_type (category_id, detail_name)
          VALUES (?, ?)
          """,
          (category_id, detail_name),
        )
    db.commit()
    flash("Category created successfully.")
    return redirect(url_for("admin.manage_categories"))

  categories = db.execute(
    "SELECT category_id, category_name FROM category ORDER BY category_name"
  ).fetchall()

  return render_template("admin/categories.html", categories=categories)


@bp.route("/categories/<int:category_id>/delete", methods=["POST"])
@admin_required
def delete_category(category_id):
  db = get_db()

  # Delete associated items & details for simplicity (ok for project)
  db.execute(
    """
    DELETE FROM item_detail
    WHERE item_id IN (SELECT item_id FROM item WHERE category_id = ?)
    """,
    (category_id,),
  )
  db.execute(
    "DELETE FROM category_detail_type WHERE category_id = ?",
    (category_id,),
  )
  db.execute("DELETE FROM item WHERE category_id = ?", (category_id,))
  db.execute("DELETE FROM category WHERE category_id = ?", (category_id,))
  db.commit()
  flash("Category and associated items deleted.")
  return redirect(url_for("admin.manage_categories"))


# --- Create Customer Representative accounts --- #


@bp.route("/create-rep", methods=["GET", "POST"])
@admin_required
def create_rep():
  db = get_db()

  if request.method == "POST":
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    error = None
    if not username:
      error = "Username is required."
    elif not password:
      error = "Password is required."

    if error:
      flash(error)
    else:
      try:
        db.execute(
          """
          INSERT INTO user (username, password, f_name, l_name, email, user_type)
          VALUES (?, ?, NULL, NULL, ?, 'representative')
          """,
          (username, generate_password_hash(password), email),
        )
        db.commit()
        flash("Customer representative account created.")
        return redirect(url_for("admin.create_rep"))
      except Exception as e:
        flash(f"Failed to create account: {e}")

  return render_template("admin/create_rep.html")


# --- Summary Sales Reports --- #


@bp.route("/reports")
@admin_required
def reports():
  """
  Generate summary sales reports:
    - total earnings
    - earnings per item
    - earnings per item type (category)
    - earnings per end-user (seller)
    - best-selling items and best-selling end-users
  """
  db = get_db()

  # For each auction, define revenue as the highest bid price (if any)
  rows = db.execute(
    """
    SELECT 
      a.auction_id,
      a.item_id,
      a.user_id AS seller_id,
      i.item_name,
      c.category_name,
      u.username AS seller_username,
      MAX(b.bid_price) AS winning_price
    FROM auctions a
    JOIN item i ON a.item_id = i.item_id
    JOIN category c ON i.category_id = c.category_id
    JOIN user u ON a.user_id = u.id
    LEFT JOIN bid b ON b.auction_id = a.auction_id
    GROUP BY a.auction_id
    """
  ).fetchall()

  total_earnings = 0.0
  earnings_per_item = defaultdict(float)
  earnings_per_category = defaultdict(float)
  earnings_per_seller = defaultdict(float)

  for r in rows:
    revenue = r["winning_price"] or 0.0
    total_earnings += revenue
    earnings_per_item[r["item_name"]] += revenue
    earnings_per_category[r["category_name"]] += revenue
    earnings_per_seller[r["seller_username"]] += revenue

  items_sorted = sorted(earnings_per_item.items(), key=lambda x: x[1], reverse=True)
  categories_sorted = sorted(
    earnings_per_category.items(), key=lambda x: x[1], reverse=True
  )
  sellers_sorted = sorted(earnings_per_seller.items(), key=lambda x: x[1], reverse=True)

  best_items = items_sorted[:5]
  best_sellers = sellers_sorted[:5]

  return render_template(
    "admin/reports.html",
    total_earnings=total_earnings,
    earnings_per_item=items_sorted,
    earnings_per_category=categories_sorted,
    earnings_per_seller=sellers_sorted,
    best_items=best_items,
    best_sellers=best_sellers,
  )
