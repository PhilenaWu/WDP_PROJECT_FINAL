from flask import Blueprint, render_template, request, jsonify, g, url_for
from flask_login import login_required, current_user
import mysql.connector
from config import Config
from database import execute_query

connections_bp = Blueprint("connections", __name__, url_prefix="/connections")

@connections_bp.route("/request", methods=["POST"])
@login_required
def request_connection():
    return send_request()


# =========================================================
# DB HELPERS (SELECT only – avoids "Unread result found")
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


def select_one(query, params=()):
    conn = get_db()
    cur = conn.cursor(dictionary=True, buffered=True)
    cur.execute(query, params)
    row = cur.fetchone()
    cur.close()
    return row

def filter_out_admins(rows):
    return [r for r in (rows or []) if (r.get("user_type") or "").lower() != "admin"]

# =========================================================
# JSON HELPERS
# =========================================================
def ok(msg="ok", **extra):
    data = {"ok": True, "msg": msg}
    data.update(extra)
    return jsonify(data), 200


def fail(msg="error", code=400, **extra):
    data = {"ok": False, "msg": msg}
    data.update(extra)
    return jsonify(data), code


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
        elif lower_path.startswith("/static/"):
            profile_picture = profile_picture[len("/static/"):]

        profile_picture = profile_picture.lstrip("/")

        if profile_picture.startswith("profile_pics/"):
            profile_picture = f"uploads/{profile_picture}"
        elif profile_picture and "/" not in profile_picture:
            profile_picture = f"uploads/profile_pics/{profile_picture}"

        return profile_picture, url_for("static", filename=profile_picture) if profile_picture else fallback_avatar

    for r in rows:
        r["name"] = r.get("display_name") or r.get("username") or "User"
        profile_picture, avatar_url = build_avatar_url(r.get("profile_picture") or r.get("profile_pic") or "")
        r["profile_picture"] = profile_picture
        r["avatar_url"] = avatar_url
        r["age_group"] = r.get("age_group") or ""
        # mutual_count may exist for suggestions; keep if present
    return rows


# =========================================================
# PAGE: /connections/
# =========================================================
@connections_bp.route("/", methods=["GET"])
@login_required
def connections():
    uid = current_user.id
    q = (request.args.get("q") or "").strip()
    role = (request.args.get("role") or "").strip()  # youth/adult/elderly
    like = f"%{q}%"

    # Incoming requests: people who sent requests TO me
    incoming = select_all("""
        SELECT u.id, u.username, u.display_name, u.age_group, u.profile_picture, u.user_type
        FROM connections c
        JOIN users u ON u.id = c.requester_id
        WHERE c.receiver_id = %s
          AND c.status = 'pending'
          AND (%s = '' OR u.username LIKE %s OR u.display_name LIKE %s)
          AND (%s = '' OR u.age_group = %s)
        ORDER BY c.created_at DESC
    """, (uid, q, like, like, role, role))

    # Outgoing requests: people I requested
    outgoing = select_all("""
        SELECT u.id, u.username, u.display_name, u.age_group, u.profile_picture, u.user_type
        FROM connections c
        JOIN users u ON u.id = c.receiver_id
        WHERE c.requester_id = %s
          AND c.status = 'pending'
          AND (%s = '' OR u.username LIKE %s OR u.display_name LIKE %s)
          AND (%s = '' OR u.age_group = %s)
        ORDER BY c.created_at DESC
    """, (uid, q, like, like, role, role))

    # Current connections (accepted)
    current = select_all("""
        SELECT u.id, u.username, u.display_name, u.age_group, u.profile_picture, u.user_type
        FROM connections c
        JOIN users u
          ON u.id = CASE
              WHEN c.requester_id = %s THEN c.receiver_id
              ELSE c.requester_id
          END
        WHERE (c.requester_id = %s OR c.receiver_id = %s)
          AND c.status = 'accepted'
          AND (%s = '' OR u.username LIKE %s OR u.display_name LIKE %s)
          AND (%s = '' OR u.age_group = %s)
        ORDER BY u.display_name, u.username
    """, (uid, uid, uid, q, like, like, role, role))

    # Suggestions (mutual friends ranking)
    # Mutual friends = users who share at least one accepted connection with you.
    suggestions = select_all("""
        SELECT
          u.id,
          u.username,
          u.display_name,
          u.age_group,
          u.profile_picture,
          u.user_type,
          COALESCE(mutuals.mutual_count, 0) AS mutual_count
        FROM users u
        LEFT JOIN (
          SELECT cand.id AS candidate_id, COUNT(*) AS mutual_count
          FROM (
            -- my accepted friends
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
          AND (%s = '' OR u.username LIKE %s OR u.display_name LIKE %s)
          AND (%s = '' OR u.age_group = %s)
          -- exclude already pending/accepted with me
          AND u.id NOT IN (
            SELECT CASE
              WHEN c.requester_id = %s THEN c.receiver_id
              ELSE c.requester_id
            END
            FROM connections c
            WHERE (c.requester_id = %s OR c.receiver_id = %s)
              AND c.status IN ('pending', 'accepted')
          )
        ORDER BY mutual_count DESC, u.display_name, u.username
        LIMIT 10
    """, (
        uid, uid, uid,      # for myfriends
        uid,                # cand.id <> uid
        uid,                # u.id <> uid
        q, like, like,
        role, role,
        uid, uid, uid       # exclusion list
    ))

        # ---------------------------------------------------------
    # Search Results: show everyone (connected OR not)
    # Adds rel_status so template can show the right buttons
    # rel_status: connected / outgoing / incoming / none
    # ---------------------------------------------------------
    search_results = select_all("""
        SELECT
          u.id,
          u.username,
          u.display_name,
          u.age_group,
          u.profile_picture,
          u.user_type,
          CASE
            WHEN c.status = 'accepted' THEN 'connected'
            WHEN c.status = 'pending' AND c.requester_id = %s THEN 'outgoing'
            WHEN c.status = 'pending' AND c.receiver_id = %s THEN 'incoming'
            ELSE 'none'
          END AS rel_status
        FROM users u
        LEFT JOIN connections c
          ON (
            (c.requester_id = %s AND c.receiver_id = u.id)
            OR
            (c.requester_id = u.id AND c.receiver_id = %s)
          )
          AND c.status IN ('pending','accepted')
        WHERE u.id <> %s
          AND (%s = '' OR u.username LIKE %s OR u.display_name LIKE %s)
          AND (%s = '' OR u.age_group = %s)
        ORDER BY
          FIELD(rel_status, 'incoming', 'outgoing', 'connected', 'none'),
          COALESCE(u.display_name, u.username)
    """, (uid, uid, uid, uid, uid, q, like, like, role, role))

    incoming = filter_out_admins(incoming)
    outgoing = filter_out_admins(outgoing)
    current = filter_out_admins(current)
    suggestions = filter_out_admins(suggestions)
    search_results = filter_out_admins(search_results)

    incoming = normalize_users(incoming)
    outgoing = normalize_users(outgoing)
    current = normalize_users(current)
    suggestions = normalize_users(suggestions)
    search_results = normalize_users(search_results)


    counts = {"current": len(current), "incoming": len(incoming), "outgoing": len(outgoing)}

    return render_template(
        "connections/connections.html",
        user=current_user,
        counts=counts,
        incoming=incoming,
        outgoing=outgoing,
        current=current,
        suggestions=suggestions,
        search_results=search_results,
        q=q,
        role=role
    )


# =========================================================
# API: SEND REQUEST
# =========================================================
@connections_bp.route("/api/send", methods=["POST"])
@login_required
def send_request():
    uid = current_user.id
    data = request.get_json(silent=True) or {}
    target_id = data.get("target_id") or data.get("user_id")
    try:
        target_id = int(target_id)
    except Exception:
        return fail("Invalid user")
    if target_id == uid:
        return fail("Cannot connect to yourself")

    low = min(uid, target_id)
    high = max(uid, target_id)

    existing = select_one("""
        SELECT id, status, requester_id, receiver_id
        FROM connections
        WHERE user_low=%s AND user_high=%s
        LIMIT 1
    """, (low, high))

    if existing:
        status = existing["status"]

        if status in ("pending", "accepted"):
            return fail("Request already exists", 409)

        execute_query("""
            UPDATE connections
            SET requester_id=%s,
                receiver_id=%s,
                status='pending',
                updated_at=NOW()
            WHERE id=%s
        """, (uid, target_id, existing["id"]), commit=True)

        return ok("Request sent")

    try:
        execute_query("""
            INSERT INTO connections (requester_id, receiver_id, user_low, user_high, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 'pending', NOW(), NOW())
        """, (uid, target_id, low, high), commit=True)

    except mysql.connector.IntegrityError as e:
        # Handles race condition (two inserts at same time)
        if e.errno == 1062:
            return fail("Request already exists", 409)
        raise

    return ok("Request sent")


# =========================================================
# API: ACCEPT REQUEST
# =========================================================
@connections_bp.route("/api/accept", methods=["POST"])
@login_required
def accept_request():
    uid = current_user.id
    target_id = (request.get_json(silent=True) or {}).get("target_id")

    try:
        target_id = int(target_id)
    except Exception:
        return fail("Invalid user")

    execute_query("""
        UPDATE connections
        SET status='accepted'
        WHERE requester_id=%s AND receiver_id=%s AND status='pending'
    """, (target_id, uid), commit=True)

    return ok("Request accepted")


# =========================================================
# API: REJECT REQUEST
# =========================================================
@connections_bp.route("/api/reject", methods=["POST"])
@login_required
def reject_request():
    uid = current_user.id
    target_id = (request.get_json(silent=True) or {}).get("target_id")

    try:
        target_id = int(target_id)
    except Exception:
        return fail("Invalid user")

    execute_query("""
        UPDATE connections
        SET status='rejected'
        WHERE requester_id=%s AND receiver_id=%s AND status='pending'
    """, (target_id, uid), commit=True)

    return ok("Request rejected")


# =========================================================
# API: CANCEL OUTGOING REQUEST
# =========================================================
@connections_bp.route("/api/cancel", methods=["POST"])
@login_required
def cancel_request():
    uid = current_user.id
    target_id = (request.get_json(silent=True) or {}).get("target_id")

    try:
        target_id = int(target_id)
    except Exception:
        return fail("Invalid user")

    execute_query("""
        DELETE FROM connections
        WHERE requester_id=%s AND receiver_id=%s AND status='pending'
    """, (uid, target_id), commit=True)

    return ok("Request cancelled")


# =========================================================
# API: REMOVE CURRENT CONNECTION (accepted)
# =========================================================
@connections_bp.route("/api/remove", methods=["POST"])
@login_required
def remove_connection():
    uid = current_user.id
    target_id = (request.get_json(silent=True) or {}).get("target_id")

    try:
        target_id = int(target_id)
    except Exception:
        return fail("Invalid user")

    if target_id == uid:
        return fail("Invalid target")

    # Delete accepted connection regardless of direction
    execute_query("""
        DELETE FROM connections
        WHERE status='accepted'
          AND ((requester_id=%s AND receiver_id=%s)
            OR (requester_id=%s AND receiver_id=%s))
    """, (uid, target_id, target_id, uid), commit=True)

    return ok("Connection removed")

@connections_bp.route("/api/ack_accept", methods=["POST"])
@login_required
def ack_accept():
    uid = current_user.id
    conn_id = (request.get_json(silent=True) or {}).get("conn_id")

    try:
        conn_id = int(conn_id)
    except Exception:
        return fail("Invalid notification")

    execute_query("""
        UPDATE connections
        SET status='connected'
        WHERE id=%s AND requester_id=%s AND status='accepted'
    """, (conn_id, uid), commit=True)

    return ok("Dismissed")