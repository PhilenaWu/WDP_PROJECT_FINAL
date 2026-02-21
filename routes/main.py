from flask import Blueprint, render_template, g, request, url_for
from flask_login import login_required, current_user
import mysql.connector
from config import Config

from topics import get_featured_topics, get_all_topics
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


def get_user_interest_topics(user_id, limit=3):
    user_rows = select_all(
        "SELECT interests FROM users WHERE id = %s LIMIT 1",
        (user_id,),
    )
    if not user_rows:
        return []

    raw_interests = (user_rows[0].get('interests') or '').strip()
    if not raw_interests:
        return []

    selected_slugs = [slug.strip() for slug in raw_interests.split(',') if slug.strip()]
    selected_slugs = list(dict.fromkeys(selected_slugs))[: int(limit)]
    if not selected_slugs:
        return []

    placeholders = ','.join(['%s'] * len(selected_slugs))
    topic_rows = select_all(
        f"SELECT title, slug, image FROM topics WHERE slug IN ({placeholders})",
        tuple(selected_slugs),
    )

    by_slug = {row.get('slug'): row for row in (topic_rows or [])}
    ordered_topics = [by_slug[slug] for slug in selected_slugs if slug in by_slug]
    return ordered_topics[: int(limit)]


def normalize_users(rows):
    rows = rows or []
    fallback_avatar = url_for("static", filename="uploads/main_topics_images/default_pfp.png")

    def build_avatar_url(raw_value):
        profile_picture = str(raw_value or "").strip()
        if profile_picture.lower() in {"", "none", "null", "nil", "undefined", "nan"}:
            return "", fallback_avatar

        profile_picture = profile_picture.replace("\\", "/")
        lower_path = profile_picture.lower()

        if lower_path.startswith(("http://", "https://", "data:image/")):
            return profile_picture, profile_picture

        if "/static/" in lower_path:
            idx = lower_path.find("/static/") + len("/static/")
            profile_picture = profile_picture[idx:]
        elif lower_path.startswith("static/"):
            profile_picture = profile_picture[len("static/"):]

        profile_picture = profile_picture.lstrip("/")

        if profile_picture.startswith("profile_pics/"):
            profile_picture = f"uploads/{profile_picture}"
        elif profile_picture and "/" not in profile_picture:
            profile_picture = f"uploads/profile_pics/{profile_picture}"

        avatar_url = url_for("static", filename=profile_picture) if profile_picture else fallback_avatar
        return profile_picture, avatar_url

    for r in rows:
        r["name"] = r.get("display_name") or r.get("username") or "User"
        profile_picture, avatar_url = build_avatar_url(r.get("profile_picture") or r.get("profile_pic") or "")
        r["profile_picture"] = profile_picture
        r["avatar_url"] = avatar_url
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
        suggestions=suggestions)

@main_bp.route('/storyboard', methods=['GET'])
@login_required
def storyboard():
    q = (request.args.get("q") or "").strip()
    sort = (request.args.get("sort") or "").strip().lower()

    featured = get_featured_topics()
    topics = get_all_topics(q=q, sort=sort)
    selected_interest_topics = get_user_interest_topics(current_user.id, limit=3)

    result_count = len(topics)  # ✅ ADD THIS

    return render_template(
        'storyboard/main_topics.html',
        user=current_user,
        featured=featured,
        selected_interest_topics=selected_interest_topics,
        topics=topics,
        q=q,
        sort=sort,
        result_count=result_count   # ✅ PASS IT
    )
    