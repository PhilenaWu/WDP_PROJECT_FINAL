from database import execute_query

def get_featured_topics():
    return execute_query(
        "SELECT title, slug, image FROM topics WHERE is_featured = 1 ORDER BY title ASC",
        fetch_all=True
    ) or []

def get_all_topics(q="", sort=""):
    sql = "SELECT title, slug, image FROM topics WHERE is_featured = 0"
    params = []

    if q:
        sql += " AND (title LIKE %s OR category LIKE %s)"
        params.extend([f"%{q}%", f"%{q}%"])


    if sort == "za":
        sql += " ORDER BY title DESC"
    else:
        sql += " ORDER BY title ASC"  # default + az

    return execute_query(sql, params, fetch_all=True) or []

