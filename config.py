import os
from datetime import timedelta

class Config:
    # All configuration values are loaded from .env file
    # Make sure to create a .env file in the project root with required environment variables
    
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
    
    # MySQL Database
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'mainline.proxy.rlwy.net')
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE', 'railway') 

    MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 27748))
    
    # Session
    SESSION_TYPE = 'filesystem'
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    
    # File uploads
    UPLOAD_FOLDER = 'static/uploads/profile_pics'
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    # Email Configuration (Gmail SMTP)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_APP_PASSWORD = os.environ.get('MAIL_APP_PASSWORD', '')

    # Password reset token
    RESET_TOKEN_MAX_AGE_SECONDS = int(os.environ.get('RESET_TOKEN_MAX_AGE_SECONDS', 1800))
    
    # Google Maps API
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY') or ''
    
    # Google Gemini AI Image Generation
    GOOGLE_GENAI_API_KEY = os.environ.get('GOOGLE_GENAI_API_KEY') or ''
    
