from flask_login import UserMixin
from database import execute_query
from datetime import datetime

class User(UserMixin):
    def __init__(self, user_data):
        """Initialize user from database dictionary"""
        self.id = user_data.get('id')
        self.email = user_data.get('email')
        self.username = user_data.get('username')
        self.password_hash = user_data.get('password_hash')
        self.user_type = user_data.get('user_type', 'user')
        
        self.first_name = user_data.get('first_name')
        self.last_name = user_data.get('last_name')
        self.display_name = user_data.get('display_name')
        self.date_of_birth = user_data.get('date_of_birth')
        self.phone_number = user_data.get('phone_number')
        self.profile_picture = user_data.get('profile_picture')
        
        self.age_group = user_data.get('age_group')
        self.location_enabled = user_data.get('location_enabled', False)
        self.latitude = user_data.get('latitude')
        self.longitude = user_data.get('longitude')
        
        self.profile_completed = user_data.get('profile_completed', False)
        self.language = user_data.get('language', 'en')
        self.created_at = user_data.get('created_at')
    
    @staticmethod
    def get_by_id(user_id):
        """Get user by ID"""
        query = "SELECT * FROM users WHERE id = %s"
        result = execute_query(query, (user_id,), fetch_one=True)
        return User(result) if result else None
    
    @staticmethod
    def get_by_email(email):
        """Get user by email"""
        query = "SELECT * FROM users WHERE email = %s"
        result = execute_query(query, (email,), fetch_one=True)
        return User(result) if result else None
    
    @staticmethod
    def get_by_username(username):
        """Get user by username"""
        query = "SELECT * FROM users WHERE username = %s"
        result = execute_query(query, (username,), fetch_one=True)
        return User(result) if result else None
    
    @staticmethod
    def create_user(email, username, password):
        """Create new user"""
        query = """
            INSERT INTO users (email, username, password_hash)
            VALUES (%s, %s, %s)
        """
        user_id = execute_query(query, (email, username, password), commit=True)
        return user_id
    
    def check_password(self, password):
        """Check if password matches"""
        return self.password_hash == password
    
    def update_profile(self, data):
        """Update user profile"""
        query = """
            UPDATE users SET
                first_name = %s,
                last_name = %s,
                display_name = %s,
                date_of_birth = %s,
                phone_number = %s,
                age_group = %s,
                location_enabled = %s,
                profile_picture = %s
            WHERE id = %s
        """
        execute_query(query, (
            data.get('first_name'),
            data.get('last_name'),
            data.get('display_name'),
            data.get('date_of_birth'),
            data.get('phone_number'),
            data.get('age_group'),
            data.get('location_enabled', False),
            data.get('profile_picture'),
            self.id
        ), commit=True)
    
    def mark_profile_completed(self):
        """Mark profile as completed"""
        query = "UPDATE users SET profile_completed = TRUE WHERE id = %s"
        execute_query(query, (self.id,), commit=True)
        self.profile_completed = True
    
    def get_interests(self):
        """Get user's interests"""
        query = """
            SELECT i.* FROM interests i
            JOIN user_interests ui ON i.id = ui.interest_id
            WHERE ui.user_id = %s
        """
        return execute_query(query, (self.id,), fetch_all=True)
    
    def set_interests(self, interest_ids):
        """Set user interests (replaces existing)"""
        # Delete existing interests
        delete_query = "DELETE FROM user_interests WHERE user_id = %s"
        execute_query(delete_query, (self.id,), commit=True)
        
        # Insert new interests
        if interest_ids:
            insert_query = "INSERT INTO user_interests (user_id, interest_id) VALUES (%s, %s)"
            from database import get_db
            db = get_db()
            cursor = db.cursor()
            for interest_id in interest_ids:
                cursor.execute(insert_query, (self.id, interest_id))
            db.commit()
            cursor.close()


class Interest:
    @staticmethod
    def get_all():
        """Get all interests"""
        query = "SELECT * FROM interests ORDER BY name"
        return execute_query(query, fetch_all=True)
    
    @staticmethod
    def get_by_id(interest_id):
        """Get interest by ID"""
        query = "SELECT * FROM interests WHERE id = %s"
        return execute_query(query, (interest_id,), fetch_one=True)
