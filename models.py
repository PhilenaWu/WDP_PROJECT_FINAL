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


class Event:
    """Model for approved events"""
    
    @staticmethod
    def get_all_upcoming(limit=None):
        """Get all upcoming events"""
        query = """
            SELECT e.*, 
                   (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as current_participants
            FROM events e 
            WHERE e.status = 'upcoming' AND e.event_date >= CURDATE()
            ORDER BY e.event_date ASC, e.start_time ASC
        """
        if limit:
            query += f" LIMIT {limit}"
        return execute_query(query, fetch_all=True)
    
    @staticmethod
    def get_by_id(event_id):
        """Get event by ID"""
        query = """
            SELECT e.*,
                   (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as current_participants
            FROM events e 
            WHERE e.id = %s
        """
        return execute_query(query, (event_id,), fetch_one=True)
    
    @staticmethod
    def create(data):
        """Create new event"""
        query = """
            INSERT INTO events 
            (title, description, event_date, start_time, end_time, location, location_address,
             latitude, longitude, image_url, max_participants, event_type, age_group, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        return execute_query(query, (
            data['title'], data['description'], data['event_date'], data['start_time'],
            data['end_time'], data['location'], data.get('location_address'),
            data.get('latitude'), data.get('longitude'), data.get('image_url'),
            data.get('max_participants'), data.get('event_type'), data.get('age_group'),
            data.get('created_by')
        ), commit=True)
    
    @staticmethod
    def get_user_registered_events(user_id):
        """Get events user is registered for"""
        query = """
            SELECT e.*, er.registered_at,
                   (SELECT COUNT(*) FROM event_registrations WHERE event_id = e.id) as current_participants
            FROM events e
            JOIN event_registrations er ON e.id = er.event_id
            WHERE er.user_id = %s AND e.event_date >= CURDATE()
            ORDER BY e.event_date ASC, e.start_time ASC
        """
        return execute_query(query, (user_id,), fetch_all=True)
    
    @staticmethod
    def is_user_registered(event_id, user_id):
        """Check if user is registered for event"""
        query = "SELECT id FROM event_registrations WHERE event_id = %s AND user_id = %s"
        result = execute_query(query, (event_id, user_id), fetch_one=True)
        return result is not None


class EventRegistration:
    """Model for event registrations"""
    
    @staticmethod
    def create(data):
        """Create new event registration"""
        query = """
            INSERT INTO event_registrations 
            (event_id, user_id, full_name, email, phone_number, confirmed)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        return execute_query(query, (
            data['event_id'], data['user_id'], data['full_name'],
            data['email'], data['phone_number'], data.get('confirmed', True)
        ), commit=True)
    
    @staticmethod
    def cancel_registration(event_id, user_id):
        """Cancel event registration"""
        query = "DELETE FROM event_registrations WHERE event_id = %s AND user_id = %s"
        return execute_query(query, (event_id, user_id), commit=True)
    
    @staticmethod
    def get_by_event(event_id):
        """Get all registrations for an event"""
        query = """
            SELECT er.*, u.username, u.email as user_email
            FROM event_registrations er
            JOIN users u ON er.user_id = u.id
            WHERE er.event_id = %s
            ORDER BY er.registered_at DESC
        """
        return execute_query(query, (event_id,), fetch_all=True)


class EventSubmission:
    """Model for user-submitted events pending approval"""
    
    @staticmethod
    def create(data):
        """Create new event submission"""
        query = """
            INSERT INTO event_submissions 
            (user_id, organizer_name, organizer_dob, organizer_age_group, organizer_email,
             organizer_phone, organizer_location, event_title, event_summary, event_type,
             preferred_date, expected_participants, why_meaningful, previous_experience,
             accessibility_considerations)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        return execute_query(query, (
            data['user_id'], data['organizer_name'], data.get('organizer_dob'),
            data.get('organizer_age_group'), data['organizer_email'], data['organizer_phone'],
            data.get('organizer_location'), data['event_title'], data['event_summary'],
            data['event_type'], data['preferred_date'], data['expected_participants'],
            data['why_meaningful'], data.get('previous_experience'),
            data['accessibility_considerations']
        ), commit=True)
    
    @staticmethod
    def get_by_user(user_id):
        """Get all submissions by user"""
        query = """
            SELECT * FROM event_submissions 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """
        return execute_query(query, (user_id,), fetch_all=True)
    
    @staticmethod
    def get_by_id(submission_id):
        """Get submission by ID"""
        query = "SELECT * FROM event_submissions WHERE id = %s"
        return execute_query(query, (submission_id,), fetch_one=True)
    
    @staticmethod
    def get_all_pending():
        """Get all pending submissions (for admin)"""
        query = """
            SELECT es.*, u.username, u.email as user_email
            FROM event_submissions es
            JOIN users u ON es.user_id = u.id
            WHERE es.status = 'pending'
            ORDER BY es.created_at ASC
        """
        return execute_query(query, fetch_all=True)
    
    @staticmethod
    def get_all():
        """Get all submissions (for admin)"""
        query = """
            SELECT es.*, u.username, u.email as user_email
            FROM event_submissions es
            JOIN users u ON es.user_id = u.id
            ORDER BY es.created_at DESC
        """
        return execute_query(query, fetch_all=True)
    
    @staticmethod
    def update_status(submission_id, status, admin_id, admin_notes=None):
        """Update submission status"""
        query = """
            UPDATE event_submissions 
            SET status = %s, reviewed_by = %s, reviewed_at = NOW(), admin_notes = %s
            WHERE id = %s
        """
        return execute_query(query, (status, admin_id, admin_notes, submission_id), commit=True)
    
    @staticmethod
    def delete(submission_id):
        """Delete submission"""
        query = "DELETE FROM event_submissions WHERE id = %s"
        return execute_query(query, (submission_id,), commit=True)
