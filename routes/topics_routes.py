from flask import Blueprint, render_template, request
from topics import get_featured_topics, get_all_topics

bp_topics = Blueprint("topics", __name__, url_prefix="/topics")

@bp_topics.route("/", methods=["GET"])
def topics_page():
    q = (request.args.get("q") or "").strip()
    sort = (request.args.get("sort") or "").strip().lower()
    
    from config import Config
    from database import execute_query

    print("FLASK DB NAME:", Config.MYSQL_DATABASE)
    print("FLASK TOPICS COUNT:", execute_query("SELECT COUNT(*) AS c FROM topics", fetch_one=True))


    featured = get_featured_topics()          # NOT affected by search/sort
    topics = get_all_topics(q=q, sort=sort)       # affected by search/sort

    # debug output
    print("FEATURED RETURNED", featured)
    print("TOPICS RETURNED", topics)

    return render_template(
        "storyboard/main_topics.html",
        featured=featured,
        topics=topics,
        q=q,
        sort=sort
    )


