from flask import Flask, app, redirect, url_for,render_template
from flask_login import LoginManager
from flask_session import Session
from config import Config
from database import init_db, close_db
from models import User
import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(__file__), 'sessions')  # Or any path like './sessions'
    Session(app)
    
    # Initialize database
    init_db(app)
    
    # Flask-Login setup
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.get_by_id(int(user_id))
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.profile import profile_bp
    from routes.main import main_bp
    from routes.topics_routes import bp_topics
    from routes.storyboard import storyboard_bp
    app.register_blueprint(storyboard_bp)


    app.register_blueprint(bp_topics)

    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(main_bp)
    
    @app.route('/')
    def index():
        return redirect(url_for('main.home'))

    @app.route("/storyboard")
    def storyboard():
        return render_template("storyboard/main_topics.html")

    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Quick DNS check for DB host to provide early feedback in logs
    try:
        import socket
        host = app.config.get('MYSQL_HOST')
        if host:
            try:
                resolved = socket.gethostbyname(host)
                print(f"MySQL host '{host}' resolves to {resolved}")
            except Exception as e:
                print(f"Warning: cannot resolve MySQL host '{host}': {e}")
                print("If you see DB connection errors, verify Config.MYSQL_HOST and network access.")
    except Exception:
        pass

    return app



    


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
