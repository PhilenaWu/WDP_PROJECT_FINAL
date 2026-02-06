from flask import Blueprint, render_template
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/home')
@login_required
def home():
    """Main home page with events"""
    # Get user's interests
    interests = current_user.get_interests()
    
    return render_template('main/home.html', user=current_user, interests=interests)
