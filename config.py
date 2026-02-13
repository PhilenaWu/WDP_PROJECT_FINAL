import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this'
    
    # MySQL Database
    MYSQL_HOST = os.environ.get('MYSQL_HOST') or 'mainline.proxy.rlwy.net'
    MYSQL_USER = os.environ.get('MYSQL_USER') or 'root'
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD') or  # Remember to delete PASSWORD!!
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE') or 'railway'
    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 27748))
    
    # Session
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    
    # File uploads
    UPLOAD_FOLDER = 'static/uploads/profile_pics'
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    