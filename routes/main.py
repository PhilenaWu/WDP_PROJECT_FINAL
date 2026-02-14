from flask import Blueprint, render_template, g
from flask_login import login_required, current_user
import mysql.connector
from config import Config

main_bp = Blueprint("main", __name__)


# =========================================================
# DB HELPERS (SELECT only)
# =========================================================
def get_db():
    """Request-scoped DB connection using Flask g."""
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
        )
    try:
        if not g.db.is_connected():
            g.db.reconnect(attempts=2, delay=0)
    except Exception:
        g.db = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
        )
    return g.db


def select_all(query, params=()):
    conn = get_db()
    cur = conn.cursor(dictionary=True, buffered=True)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def normalize_users(rows):
    rows = rows or []
    for r in rows:
        r["name"] = r.get("display_name") or r.get("username") or "User"
        r["profile_picture"] = r.get("profile_picture") or r.get("profile_pic") or ""
        r["age_group"] = r.get("age_group") or ""
        r["mutual_count"] = r.get("mutual_count", 0)
    return rows


# =========================================================
# ROUTE: /home
# =========================================================
@main_bp.route("/home")
@login_required
def home():
    """Main home page with events + dynamic connections/suggestions."""
    uid = current_user.id

    # -----------------------------
    # Your Connections (accepted) - show 3
    # -----------------------------
    current = select_all("""
        SELECT u.id, u.username, u.display_name, u.age_group, u.profile_picture
        FROM connections c
        JOIN users u
          ON u.id = CASE
              WHEN c.requester_id = %s THEN c.receiver_id
              ELSE c.requester_id
          END
        WHERE (c.requester_id = %s OR c.receiver_id = %s)
          AND c.status = 'accepted'
        ORDER BY COALESCE(u.display_name, u.username)
        LIMIT 3
    """, (uid, uid, uid))

    # -----------------------------
    # Suggestions (mutual friends) - show 3
    # excludes pending/accepted with me
    # -----------------------------
    suggestions = select_all("""
        SELECT
          u.id,
          u.username,
          u.display_name,
          u.age_group,
          u.profile_picture,
          COALESCE(mutuals.mutual_count, 0) AS mutual_count
        FROM users u
        LEFT JOIN (
          SELECT cand.id AS candidate_id, COUNT(*) AS mutual_count
          FROM (
            SELECT CASE
              WHEN c.requester_id = %s THEN c.receiver_id
              ELSE c.requester_id
            END AS friend_id
            FROM connections c
            WHERE (c.requester_id = %s OR c.receiver_id = %s)
              AND c.status = 'accepted'
          ) myfriends
          JOIN connections c2
            ON c2.status = 'accepted'
           AND (c2.requester_id = myfriends.friend_id OR c2.receiver_id = myfriends.friend_id)
          JOIN users cand
            ON cand.id = CASE
              WHEN c2.requester_id = myfriends.friend_id THEN c2.receiver_id
              ELSE c2.requester_id
            END
          WHERE cand.id <> %s
          GROUP BY cand.id
        ) mutuals
          ON mutuals.candidate_id = u.id
        WHERE u.id <> %s
          AND u.id NOT IN (
            SELECT CASE
              WHEN c.requester_id = %s THEN c.receiver_id
              ELSE c.requester_id
            END
            FROM connections c
            WHERE (c.requester_id = %s OR c.receiver_id = %s)
              AND c.status IN ('pending','accepted')
          )
        ORDER BY mutual_count DESC, COALESCE(u.display_name, u.username)
        LIMIT 3
    """, (uid, uid, uid, uid, uid, uid, uid, uid))

    current = normalize_users(current)
    suggestions = normalize_users(suggestions)

    return render_template(
        "main/home.html",
        user=current_user,
        current=current,
        suggestions=suggestions
    )
