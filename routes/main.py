from flask import Blueprint, render_template,request 
from flask_login import login_required, current_user

from topics import get_featured_topics, get_all_topics

main_bp = Blueprint('main', __name__)

@main_bp.route('/home')
@login_required
def home():
    """Main home page with events"""
    return render_template('main/home.html', user=current_user)


@main_bp.route('/storyboard', methods=['GET'])
@login_required
def storyboard():
    q = (request.args.get("q") or "").strip()
    sort = (request.args.get("sort") or "").strip().lower()

    featured = get_featured_topics()
    topics = get_all_topics(q=q, sort=sort)

    result_count = len(topics)  # ✅ ADD THIS

    return render_template(
        'storyboard/main_topics.html',
        user=current_user,
        featured=featured,
        topics=topics,
        q=q,
        sort=sort,
        result_count=result_count   # ✅ PASS IT
    )
