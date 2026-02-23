from flask import Blueprint, render_template, g, request, jsonify
from flask_login import login_required, current_user
import mysql.connector
from config import Config

from topics import get_featured_topics, get_all_topics

main_bp = Blueprint("main", __name__)

# =========================================================
# DB HELPERS
# =========================================================
def get_db():
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
        r["profile_picture"] = r.get("profile_picture") or ""
        r["age_group"] = r.get("age_group") or ""
        r["mutual_count"] = r.get("mutual_count", 0)
    return rows

@main_bp.app_template_filter("fmt_time")
def fmt_time(value):
    if not value:
        return ""

    # MySQL TIME may return timedelta
    if hasattr(value, "total_seconds"):
        total = int(value.total_seconds())
        h = (total // 3600) % 24
        m = (total % 3600) // 60
    else:
        h = getattr(value, "hour", 0)
        m = getattr(value, "minute", 0)

    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12
    if h12 == 0:
        h12 = 12

    return f"{h12:02d}:{m:02d} {ampm}"

@main_bp.app_context_processor
def inject_nav_notifications():
    if not current_user.is_authenticated:
        return dict(
            nav_notification_count=0,
            nav_pending_requests=[],
            nav_nearing_events=[]
        )

    uid = current_user.id

    nav_pending_requests = select_all("""
        SELECT
          u.id AS from_id,
          COALESCE(u.display_name, u.username) AS from_name,
          u.profile_picture AS from_pic
        FROM connections c
        JOIN users u ON u.id = c.requester_id
        WHERE c.receiver_id = %s
          AND c.status = 'pending'
        ORDER BY c.created_at DESC
        LIMIT 5
    """, (uid,))

    nav_nearing_events = select_all("""
        SELECT
          e.id,
          e.title,
          e.event_date,
          e.start_time
        FROM event_registrations r
        JOIN events e ON e.id = r.event_id
        WHERE r.user_id = %s
          AND e.event_date >= CURDATE()
          AND e.event_date <= DATE_ADD(CURDATE(), INTERVAL 3 DAY)
          AND (e.status IS NULL OR e.status <> 'cancelled')
        ORDER BY e.event_date ASC, e.start_time ASC
        LIMIT 5
    """, (uid,))

    return dict(
        nav_notification_count=len(nav_pending_requests) + len(nav_nearing_events),
        nav_pending_requests=nav_pending_requests,
        nav_nearing_events=nav_nearing_events
    )

@main_bp.route("/home")
@login_required
def home():
    uid = current_user.id

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

    suggestions = select_all("""
        SELECT
          u.id,
          u.username,
          u.display_name,
          u.age_group,
          u.profile_picture
        FROM users u
        WHERE u.id <> %s
        LIMIT 3
    """, (uid,))

    current = normalize_users(current)
    suggestions = normalize_users(suggestions)

    upcoming_events = select_all("""
        SELECT
          id,
          title,
          event_date,
          start_time,
          end_time,
          location,
          image_url,
          max_participants,
          current_participants,
          event_type
        FROM events
        WHERE event_date >= CURDATE()
          AND (status IS NULL OR status <> 'cancelled')
        ORDER BY event_date ASC, start_time ASC
        LIMIT 4
    """)

    cal_filter = (request.args.get("cal") or "all").lower()
    if cal_filter not in ("all", "week", "month"):
        cal_filter = "all"

    days = 3650
    if cal_filter == "week":
        days = 7
    elif cal_filter == "month":
        days = 30

    my_calendar_events = select_all("""
        SELECT
          e.id,
          e.title,
          e.event_date,
          e.start_time,
          e.end_time,
          e.event_type
        FROM event_registrations r
        JOIN events e ON e.id = r.event_id
        WHERE r.user_id = %s
          AND e.event_date >= CURDATE()
          AND e.event_date <= DATE_ADD(CURDATE(), INTERVAL %s DAY)
          AND (e.status IS NULL OR e.status <> 'cancelled')
        ORDER BY e.event_date ASC, e.start_time ASC
        LIMIT 8
    """, (uid, days))

    pending_row = select_all("""
        SELECT COUNT(*) AS c
        FROM connections
        WHERE receiver_id = %s AND status='pending'
    """, (uid,))
    pending_count = pending_row[0]["c"] if pending_row else 0

    storyboard_preview = select_all("""
    SELECT
      s.id,
      s.user_id,
      s.title,
      s.body,
      s.audio_path,
      DATE_FORMAT(s.created_at, '%d %b %Y, %h:%i %p') AS created_at,

      u.username,
      u.display_name,
      u.profile_picture,

      t.title AS topic_title,
      t.slug  AS topic_slug,

      -- counts
      (SELECT COUNT(*) FROM story_likes sl WHERE sl.story_id = s.id) AS like_count,
      (SELECT COUNT(*) FROM comments c WHERE c.story_id = s.id)      AS comment_count,

      -- did I like it?
      EXISTS(
        SELECT 1 FROM story_likes sl2
        WHERE sl2.story_id = s.id AND sl2.user_id = %s
      ) AS liked_by_me,

      -- pick one latest image for preview
      (SELECT sm.file_path
         FROM story_media sm
        WHERE sm.story_id = s.id AND sm.media_type = 'image'
        ORDER BY sm.created_at DESC
        LIMIT 1) AS image_path

    FROM stories s
    JOIN topics t ON t.id = s.topic_id
    JOIN users  u ON u.id = s.user_id
    WHERE s.user_id IN (
      SELECT CASE
        WHEN c.requester_id = %s THEN c.receiver_id
        ELSE c.requester_id
      END
      FROM connections c
      WHERE (c.requester_id = %s OR c.receiver_id = %s)
        AND c.status = 'accepted'
    )
    ORDER BY s.created_at DESC
    LIMIT 3
""", (uid, uid, uid, uid))

    return render_template(
        "main/home.html",
        user=current_user,
        current=current,
        suggestions=suggestions,
        upcoming_events=upcoming_events,
        my_calendar_events=my_calendar_events,
        cal_filter=cal_filter,
        pending_count=pending_count,
        storyboard_preview=storyboard_preview
    )


@main_bp.route('/storyboard', methods=['GET'])
@login_required
def storyboard():
    q = (request.args.get("q") or "").strip()
    sort = (request.args.get("sort") or "").strip().lower()

    featured = get_featured_topics()
    topics = get_all_topics(q=q, sort=sort)

    result_count = len(topics)

    return render_template(
        'storyboard/main_topics.html',
        user=current_user,
        featured=featured,
        topics=topics,
        q=q,
        sort=sort,
        result_count=result_count
    )

@main_bp.get("/api/calendar")
@login_required
def api_calendar():
    uid = current_user.id

    cal_filter = (request.args.get("cal") or "all").lower()
    if cal_filter not in ("all", "week", "month"):
        cal_filter = "all"

    days = 3650
    if cal_filter == "week":
        days = 7
    elif cal_filter == "month":
        days = 30

    rows = select_all("""
        SELECT
          e.id,
          e.title,
          e.event_date,
          e.start_time,
          e.end_time,
          e.event_type
        FROM event_registrations r
        JOIN events e ON e.id = r.event_id
        WHERE r.user_id = %s
          AND e.event_date >= CURDATE()
          AND e.event_date <= DATE_ADD(CURDATE(), INTERVAL %s DAY)
          AND (e.status IS NULL OR e.status <> 'cancelled')
        ORDER BY e.event_date ASC, e.start_time ASC
        LIMIT 8
    """, (uid, days))

    items = []
    for r in rows:
        d = r.get("event_date")
        items.append({
            "id": r.get("id"),
            "title": r.get("title") or "Event",
            "day": d.strftime("%d") if d else "",
            "mon": d.strftime("%b").upper() if d else "",
            "time": (
                f"{fmt_time(r.get('start_time'))}"
                + (f" - {fmt_time(r.get('end_time'))}" if r.get("end_time") else "")
            ).strip(),
            "event_type": r.get("event_type") or "Event"
        })

    return jsonify({"ok": True, "items": items})

@main_bp.get("/api/notifications/summary")
@login_required
def api_notifications_summary():
    uid = current_user.id

    pending = select_all("""
        SELECT
          u.id AS from_id,
          COALESCE(u.display_name, u.username) AS from_name,
          u.profile_picture AS from_pic
        FROM connections c
        JOIN users u ON u.id = c.requester_id
        WHERE c.receiver_id = %s
          AND c.status = 'pending'
        ORDER BY c.created_at DESC
        LIMIT 10
    """, (uid,))

    nearing = select_all("""
        SELECT
          e.id,
          e.title,
          e.event_date,
          e.start_time
        FROM event_registrations r
        JOIN events e ON e.id = r.event_id
        WHERE r.user_id = %s
          AND e.event_date >= CURDATE()
          AND e.event_date <= DATE_ADD(CURDATE(), INTERVAL 3 DAY)
          AND (e.status IS NULL OR e.status <> 'cancelled')
        ORDER BY e.event_date ASC, e.start_time ASC
        LIMIT 10
    """, (uid,))

    pending_items = []
    for r in pending:
        pending_items.append({
            "from_id": r.get("from_id"),
            "from_name": r.get("from_name") or "User",
            "from_pic": r.get("from_pic") or ""
        })

    nearing_items = []
    for e in nearing:
        d = e.get("event_date")
        nearing_items.append({
            "id": e.get("id"),
            "title": e.get("title") or "Event",
            "date": d.strftime("%d %b") if d else "",
            "time": fmt_time(e.get("start_time")) if e.get("start_time") else ""
        })

    return jsonify({
        "ok": True,
        "pending": pending_items,
        "nearing": nearing_items,
        "count": len(pending_items) + len(nearing_items)
    })