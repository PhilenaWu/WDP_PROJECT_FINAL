# story_service.py
from database import execute_query
from connections_service import get_connection_ids

def get_topic_by_slug(slug: str):
    return execute_query(
        "SELECT id, title, slug FROM topics WHERE slug=%s",
        (slug,),
        fetch_one=True
    )

def get_stories(topic_id: int, current_user_id: int, feed: str):
    sql = """
    SELECT s.id, s.title, s.body, s.audio_path, s.user_id, s.created_at,
           u.username,
           (SELECT COUNT(*) FROM story_likes sl WHERE sl.story_id=s.id) AS like_count,
           (SELECT COUNT(*) FROM comments c WHERE c.story_id=s.id) AS comment_count,
           EXISTS(SELECT 1 FROM story_likes sl2 WHERE sl2.story_id=s.id AND sl2.user_id=%s) AS liked_by_me
    FROM stories s
    JOIN users u ON u.id = s.user_id
    WHERE s.topic_id=%s
    """
    params = [current_user_id, topic_id]

    if feed == "mine":
        sql += " AND s.user_id=%s"
        params.append(current_user_id)

    if feed == "connections":
        from connections_service import get_connection_ids
        ids = get_connection_ids(current_user_id)
        if not ids:
            return []
        placeholders = ",".join(["%s"] * len(ids))
        sql += f" AND s.user_id IN ({placeholders})"
        params.extend(ids)

    sql += " ORDER BY s.created_at DESC"

    return execute_query(sql, tuple(params), fetch_all=True) or []


def get_story(story_id: int):
    return execute_query(
        "SELECT * FROM stories WHERE id=%s",
        (story_id,),
        fetch_one=True
    )

def get_media(story_id: int):
    return execute_query(
        "SELECT * FROM story_media WHERE story_id=%s",
        (story_id,),
        fetch_all=True
    ) or []

def get_comments(story_id: int, current_user_id: int):
    sql = """
    SELECT c.id, c.body, c.created_at, c.user_id,
           (SELECT COUNT(*) FROM comment_likes cl WHERE cl.comment_id=c.id) AS like_count,
           EXISTS(SELECT 1 FROM comment_likes cl2 WHERE cl2.comment_id=c.id AND cl2.user_id=%s) AS liked_by_me
    FROM comments c
    WHERE c.story_id=%s
    ORDER BY c.created_at ASC
    """
    return execute_query(sql, (current_user_id, story_id), fetch_all=True) or []