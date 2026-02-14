from database import execute_query

def get_connected_user_ids(user_id):
    query = """
        SELECT user_low, user_high
        FROM connections
        WHERE (user_low = %s OR user_high = %s)
        AND status = 'accepted'
    """
    rows = execute_query(query, (user_id, user_id), fetch_all=True)

    connected_ids = []

    for row in rows:
        if row['user_low'] == user_id:
            connected_ids.append(row['user_high'])
        else:
            connected_ids.append(row['user_low'])

    return connected_ids
