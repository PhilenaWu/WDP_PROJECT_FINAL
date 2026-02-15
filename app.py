from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from flask import Flask, redirect, url_for, render_template
from flask_socketio import SocketIO
from flask_login import LoginManager, current_user
from flask_session import Session
from config import Config
from database import execute_query, init_db
from models import User
import os

socketio = SocketIO()

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
    from routes.events import events_bp
    from routes.messaging import messaging_bp
    from routes.connections import connections_bp
    from routes.topics_routes import bp_topics
    from routes.storyboard import storyboard_bp
    app.register_blueprint(storyboard_bp)


    app.register_blueprint(bp_topics)

    
    app.register_blueprint(messaging_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(profile_bp, url_prefix='/profile')
    app.register_blueprint(main_bp)
    app.register_blueprint(events_bp, url_prefix='/events')
    app.register_blueprint(connections_bp, url_prefix='/connections')
    
    @app.route('/')
    def index():
        return redirect(url_for('main.home'))

    @app.context_processor
    def inject_appearance_pref():
        default_pref = {
            'theme': 'light',
            'textSize': 16,
            'fontStyle': 'poppins',
            'fontWeight': '500'
        }

        if not getattr(current_user, 'is_authenticated', False):
            return {'appearance_pref': default_pref}

        try:
            appearance = execute_query(
                "SELECT theme, text_size, font_style, boldness FROM appearance WHERE user_id = %s",
                (current_user.id,),
                fetch_one=True
            )

            if not appearance:
                return {'appearance_pref': default_pref}

            font_key_map = {
                'poppins': 'poppins',
                'arial': 'arial',
                'verdana': 'verdana',
                'tahoma': 'tahoma',
                'trebuchet ms': 'trebuchet',
                'georgia': 'georgia',
                'times new roman': 'times',
                'courier new': 'courier'
            }

            font_style = (appearance.get('font_style') or 'Poppins').strip().lower()
            boldness = (appearance.get('boldness') or 'medium').strip().lower()
            boldness_map = {
                'light': '300',
                'medium': '500',
                'dark': '700'
            }

            pref = {
                'theme': 'dark' if appearance.get('theme') == 'darkmode' else 'light',
                'textSize': int(appearance.get('text_size') or 16),
                'fontStyle': font_key_map.get(font_style, 'poppins'),
                'fontWeight': boldness_map.get(boldness, '500')
            }

            return {'appearance_pref': pref}
        except Exception:
            return {'appearance_pref': default_pref}

    @app.route("/storyboard")
    def storyboard():
        return render_template("storyboard/main_topics.html")

    
    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('static/uploads', exist_ok=True)

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

    @app.template_filter('format_time')
    def format_time(value, offset_hours=8):
        from datetime import datetime, timedelta
        if value is None:
            return ''
        if isinstance(value, str):
            try:
                value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return value
        return (value + timedelta(hours=offset_hours)).strftime('%I:%M %p')
    
    # Initialize Socket.IO with app
    socketio.init_app(app)

    # Register Socket.IO events
    from routes.socketio_events import register_socketio_events
    register_socketio_events(socketio, app)

    return app

if __name__ == '__main__':
    app = create_app()
    socketio.run(app, debug=True)
