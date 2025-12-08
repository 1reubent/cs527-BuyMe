from flask import (
  Blueprint,
  render_template,
  g,
)
from .auth import login_required
from db import get_db

bp = Blueprint("alerts", __name__, url_prefix="/alerts")


def create_alert(user_id, message):
  """Helper to insert an alert for a user."""
  if user_id is None:
    return
  db = get_db()
  db.execute(
    """
    INSERT INTO alert (user_id, message)
    VALUES (?, ?)
    """,
    (user_id, message),
  )
  db.commit()


@bp.route("/", methods=["GET"])
@login_required
def list_alerts():
  """Show all alerts for the current user."""
  db = get_db()
  alerts = db.execute(
    """
    SELECT id, message, created_at, is_read
    FROM alert
    WHERE user_id = ?
    ORDER BY created_at DESC
    """,
    (g.user["id"],),
  ).fetchall()

  return render_template("alerts/list.html", alerts=alerts)
