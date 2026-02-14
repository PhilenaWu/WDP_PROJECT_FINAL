from database import execute_query
from connections_service import get_connected_user_ids


def get_stories(topic_id, user_id, feed):

    if feed == "mine":
        query = """
            SELECT s.*, u.username, u.profile_pic
            FROM stories s
            JOIN users u ON s.user_id = u.id
            WHERE s.topic_id = %s
            AND s.user_id = %s
            ORDER BY s.created_at DESC
        """
        return execute_query(query, (topic_id, user_id), fetch_all=True)


    elif feed == "connections":

        connected_ids = get_connected_user_ids(user_id)

        if not connected_ids:
            return []

        placeholders = ",".join(["%s"] * len(connected_ids))

        query = f"""
            SELECT s.*, u.username, u.profile_pic
            FROM stories s
            JOIN users u ON s.user_id = u.id
            WHERE s.topic_id = %s
            AND s.user_id IN ({placeholders})
            ORDER BY s.created_at DESC
        """

        params = [topic_id] + connected_ids
        return execute_query(query, params, fetch_all=True)


    # Default = for_you
    else:
        query = """
            SELECT s.*, u.username, u.profile_pic
            FROM stories s
            JOIN users u ON s.user_id = u.id
            WHERE s.topic_id = %s
            ORDER BY s.created_at DESC
        """
        return execute_query(query, (topic_id,), fetch_all=True)

