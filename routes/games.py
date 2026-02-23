from flask import Blueprint, render_template
from flask_login import login_required


games_bp = Blueprint("games", __name__, url_prefix="/games")


@games_bp.route("/", methods=["GET"])
@login_required
def index():
    return render_template("games/index.html")
