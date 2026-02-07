import mysql.connector
from flask import g
from config import Config

def get_db():
    """Get database connection"""
    if 'db' not in g:
        g.db = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            port=Config.MYSQL_PORT
        )
    return g.db

def close_db(e=None):
    """Close database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db(app):
    """Initialize database"""
    app.teardown_appcontext(close_db)

def execute_query(query, params=None, fetch_one=False, fetch_all=False, commit=False):
    """Execute a database query"""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    
    try:
        cursor.execute(query, params or ())
        
        if commit:
            db.commit()
            return cursor.lastrowid
        
        if fetch_one:
            result = cursor.fetchone()
            cursor.close()
            return result
        
        if fetch_all:
            result = cursor.fetchall()
            cursor.close()
            return result
        
        cursor.close()
        return None
        
    except Exception as e:
        if commit:
            db.rollback()
        cursor.close()
        raise e
