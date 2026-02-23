# Main Topics page route


# routes/storyboard.py
import os
from uuid import uuid4
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from database import execute_query
from story_service import (
    get_topic_by_slug, get_stories, get_comments, get_media, get_story
)

storyboard_bp = Blueprint("storyboard", __name__)

ALLOWED_MEDIA_EXT = {"png","jpg","jpeg","gif","webp","mp4","mov","webm"}
ALLOWED_AUDIO_EXT = {"mp3","wav","m4a","ogg","webm"}


def _avatar_url(raw_value):
    fallback = url_for("static", filename="uploads/main_topics_images/defaultProfile.webp")
    profile_picture = str(raw_value or "").strip()

    if profile_picture.lower() in {"", "none", "null", "nil", "undefined", "nan"}:
        return fallback

    profile_picture = profile_picture.replace("\\", "/")
    lower_path = profile_picture.lower()

    if lower_path.startswith(("http://", "https://", "data:image/")):
        return profile_picture

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

    return url_for("static", filename=profile_picture) if profile_picture else fallback

def _ext_ok(filename: str, allowed: set[str]) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in allowed

def _save_file(file_obj, folder_rel: str) -> str:
    """
    Saves file into /static/uploads/... and returns relative path like:
    uploads/story_media/xxx.jpg
    """
    filename = secure_filename(file_obj.filename)
    ext = filename.rsplit(".", 1)[1].lower()
    new_name = f"{uuid4().hex}.{ext}"

    base_static = os.path.join(current_app.root_path, "static")
    folder_abs = os.path.join(base_static, folder_rel)
    os.makedirs(folder_abs, exist_ok=True)

    abs_path = os.path.join(folder_abs, new_name)
    file_obj.save(abs_path)

    return f"{folder_rel}/{new_name}"



@storyboard_bp.route("/story/<int:story_id>")
@login_required
def view_story(story_id):
    story = get_story(story_id)
    if not story:
        flash("Story not found.", "danger")
        return redirect(url_for("main.storyboard"))
    # Get topic slug
    topic_row = execute_query("SELECT slug FROM topics WHERE id=%s", (story['topic_id'],), fetch_one=True)
    if not topic_row or not topic_row.get('slug'):
        flash("Topic not found.", "danger")
        return redirect(url_for("main.storyboard"))
    slug = topic_row['slug']
    # Redirect to topic detail with anchor
    return redirect(url_for("storyboard.topic_detail", slug=slug) + f"#story-{story_id}")

@storyboard_bp.route("/topic/<slug>")
@login_required
def topic_detail(slug):
    feed = (request.args.get("feed") or "for_you").lower()
    if feed not in ("for_you", "connections", "mine"):
        feed = "for_you"

    topic = get_topic_by_slug(slug)
    if not topic:
        flash("Topic not found.", "danger")
        return redirect(url_for("main.storyboard"))

    stories = get_stories(topic["id"], current_user.id, feed)

    # Attach media + comments for each story (simple approach for demo)
    from connections_service import get_connection_ids
    connected_ids = get_connection_ids(current_user.id)
    # Get connection usernames for sharing
    connection_users = []
    if connected_ids:
        placeholders = ','.join(['%s'] * len(connected_ids))
        sql = f"SELECT id, username FROM users WHERE id IN ({placeholders})"
        connection_users = execute_query(sql, tuple(connected_ids), fetch_all=True) or []
    for s in stories:
        s["avatar_url"] = _avatar_url(s.get("profile_pic"))
        s["media"] = get_media(s["id"])
        comments = get_comments(s["id"], current_user.id)
        for c in comments:
            c["avatar_url"] = _avatar_url(c.get("profile_pic"))
            # Allow delete if current user is comment owner or story owner
            c["can_delete"] = (c["user_id"] == current_user.id) or (s["user_id"] == current_user.id)
            # Set rel_status for modal logic
            if c["user_id"] == current_user.id:
                c["rel_status"] = "self"
            elif c["user_id"] in connected_ids:
                c["rel_status"] = "connected"
            else:
                c["rel_status"] = "none"
        s["comments"] = comments

    return render_template(
        "storyboard/topic_detail.html",
        topic=topic,
        feed=feed,
        stories=stories,
        connections=connection_users
    )

@storyboard_bp.route("/topic/<slug>/add", methods=["GET","POST"])
@login_required
def add_story(slug):
    topic = get_topic_by_slug(slug)
    if not topic:
        flash("Topic not found.", "danger")
        return redirect(url_for("main.storyboard"))

    if request.method == "GET":
        return render_template("storyboard/add_story.html", topic=topic)

    from deep_translator import GoogleTranslator
    title = (request.form.get("title") or "").strip()
    body = (request.form.get("body") or "").strip()

    def translate_if_chinese(text):
        if text:
            try:
                if any('\u4e00' <= c <= '\u9fff' for c in text):
                    return GoogleTranslator(source='auto', target='en').translate(text)
            except Exception:
                pass
        return text

    title = translate_if_chinese(title)
    body = translate_if_chinese(body)

    if not title:
        flash("Title is required.", "warning")
        return redirect(url_for("storyboard.add_story", slug=slug))

    # Audio upload (optional)
    audio = request.files.get("audio")
    audio_path = None
    if audio and audio.filename:
        if not _ext_ok(audio.filename, ALLOWED_AUDIO_EXT):
            flash("Audio file type not allowed.", "danger")
            return redirect(url_for("storyboard.add_story", slug=slug))
        audio_path = _save_file(audio, "uploads/story_audio")

    # Insert story
    story_id = execute_query(
        """
        INSERT INTO stories (user_id, topic_id, title, body, audio_path)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (current_user.id, topic["id"], title, body if body else None, audio_path),
        commit=True
    )

    # Media uploads (optional, multiple)
    media_files = request.files.getlist("media")
    for f in media_files:
        if not f or not f.filename:
            continue
        if not _ext_ok(f.filename, ALLOWED_MEDIA_EXT):
            continue

        rel_path = _save_file(f, "uploads/story_media")
        ext = f.filename.rsplit(".", 1)[1].lower()
        media_type = "video" if ext in {"mp4","mov","webm"} else "image"

        execute_query(
            "INSERT INTO story_media (story_id, media_type, file_path) VALUES (%s,%s,%s)",
            (story_id, media_type, rel_path),
            commit=True
        )

    flash("Story posted!", "success")
    return redirect(url_for("storyboard.topic_detail", slug=slug, feed="for_you"))

@storyboard_bp.route("/story/<int:story_id>/comment", methods=["POST"])
@login_required
def add_comment(story_id):
    body = (request.form.get("comment") or "").strip()
    if not body:
        return redirect(request.referrer or url_for("main.storyboard"))

    execute_query(
        "INSERT INTO comments (story_id, user_id, body) VALUES (%s,%s,%s)",
        (story_id, current_user.id, body),
        commit=True
    )
    return redirect(request.referrer or url_for("main.storyboard"))

@storyboard_bp.route("/story/<int:story_id>/like", methods=["POST"])
@login_required
def toggle_story_like(story_id):
    liked = execute_query(
        "SELECT 1 FROM story_likes WHERE story_id=%s AND user_id=%s",
        (story_id, current_user.id),
        fetch_one=True
    )

    if liked:
        execute_query(
            "DELETE FROM story_likes WHERE story_id=%s AND user_id=%s",
            (story_id, current_user.id),
            commit=True
        )
    else:
        execute_query(
            "INSERT INTO story_likes (story_id, user_id) VALUES (%s,%s)",
            (story_id, current_user.id),
            commit=True
        )

    return redirect(request.referrer or url_for("main.storyboard"))

@storyboard_bp.route("/comment/<int:comment_id>/like", methods=["POST"])
@login_required
def toggle_comment_like(comment_id):
    liked = execute_query(
        "SELECT 1 FROM comment_likes WHERE comment_id=%s AND user_id=%s",
        (comment_id, current_user.id),
        fetch_one=True
    )

    if liked:
        execute_query(
            "DELETE FROM comment_likes WHERE comment_id=%s AND user_id=%s",
            (comment_id, current_user.id),
            commit=True
        )
    else:
        execute_query(
            "INSERT INTO comment_likes (comment_id, user_id) VALUES (%s,%s)",
            (comment_id, current_user.id),
            commit=True
        )

    return redirect(request.referrer or url_for("main.storyboard"))

@storyboard_bp.route("/story/<int:story_id>/delete", methods=["POST"])
@login_required
def delete_story(story_id):
    story = get_story(story_id)
    if not story or story["user_id"] != current_user.id:
        flash("Not allowed.", "danger")
        return redirect(request.referrer or url_for("main.storyboard"))

    # delete children first
    execute_query("DELETE FROM comment_likes WHERE comment_id IN (SELECT id FROM comments WHERE story_id=%s)", (story_id,), commit=True)
    execute_query("DELETE FROM comments WHERE story_id=%s", (story_id,), commit=True)
    execute_query("DELETE FROM story_likes WHERE story_id=%s", (story_id,), commit=True)
    execute_query("DELETE FROM story_media WHERE story_id=%s", (story_id,), commit=True)
    execute_query("DELETE FROM stories WHERE id=%s", (story_id,), commit=True)

    flash("Story deleted.", "success")
    return redirect(request.referrer or url_for("main.storyboard"))

@storyboard_bp.route("/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    # Get the comment + which story it belongs to
    comment = execute_query(
        "SELECT id, story_id, user_id FROM comments WHERE id=%s",
        (comment_id,),
        fetch_one=True
    )
    if not comment:
        flash("Comment not found.", "danger")
        return redirect(request.referrer or url_for("main.storyboard"))

    # Get story owner
    story = execute_query(
        "SELECT id, user_id FROM stories WHERE id=%s",
        (comment["story_id"],),
        fetch_one=True
    )
    if not story:
        flash("Story not found.", "danger")
        return redirect(request.referrer or url_for("main.storyboard"))

    # Allowed if:
    # - comment owner OR
    # - story owner
    if current_user.id != comment["user_id"] and current_user.id != story["user_id"]:
        flash("Not allowed to delete this comment.", "danger")
        return redirect(request.referrer or url_for("main.storyboard"))

    # Delete likes first, then comment
    execute_query(
        "DELETE FROM comment_likes WHERE comment_id=%s",
        (comment_id,),
        commit=True
    )
    execute_query(
        "DELETE FROM comments WHERE id=%s",
        (comment_id,),
        commit=True
    )

    flash("Comment deleted.", "success")
    return redirect(request.referrer or url_for("main.storyboard"))
