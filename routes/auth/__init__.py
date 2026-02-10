from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user, current_user
from models import User
from datetime import datetime, timedelta
import re

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """About You: main signup step (GET renders form, POST handles submission)."""
    if request.method == 'POST':
        from database import get_db

        # get birthday + calculate age
        birthday_str = request.form.get('birthday', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        display_name = request.form.get('display_name', '').strip()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        location_enabled = request.form.get('location_enabled') == 'on'

        user_data = {
            'username': username,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'display_name': display_name,
            'phone': phone,
            'birthday': birthday_str
        }

        # Validate required fields
        if not all([first_name, last_name, username, email, password, phone, birthday_str]):
            return render_template('auth/signup.html',
                user=user_data,
                error="All required fields must be filled.",
                location_enabled=location_enabled
            )

        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return render_template('auth/signup.html',
                user=user_data,
                error="Please enter a valid email address.",
                location_enabled=location_enabled
            )

        # Calculate age from birthday
        age_category = None
        age = None
        if birthday_str:
            try:
                birthday = datetime.strptime(birthday_str, '%Y-%m-%d')
                today = datetime.now()
                age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))

                if age < 13:
                    return render_template('auth/signup.html',
                        user=user_data,
                        error="You must be at least 13 years old to sign up.",
                        location_enabled=location_enabled
                    )

                if age < 60:
                    age_category = 'youth'
                else:
                    age_category = 'elderly'
            except ValueError:
                return render_template('auth/signup.html',
                    user=user_data,
                    error="Invalid date format. Please enter a valid birthday.",
                    location_enabled=location_enabled
                )

        # Try to check existing users and insert into database
        try:
            # Check if email already exists
            if User.get_by_email(email):
                return render_template('auth/signup.html',
                    user=user_data,
                    error="Email already registered. Please use a different one.",
                    location_enabled=location_enabled
                )

            # Check if username already exists
            if User.get_by_username(username):
                return render_template('auth/signup.html',
                    user=user_data,
                    error="Username already taken. Please use a different one.",
                    location_enabled=location_enabled
                )

            # Insert into database
            conn = get_db()
            cur = conn.cursor(dictionary=True)

            cur.execute("""
                INSERT INTO users 
                (email, username, password_hash, first_name, last_name, display_name, 
                 phone_number, date_of_birth, age_group, location_enabled)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                email,
                username,
                password,
                first_name,
                last_name,
                display_name,
                phone,
                birthday_str,
                age_category,
                1 if location_enabled else 0
            ))

            user_id = cur.lastrowid
            conn.commit()
            cur.close()
            conn.close()

            # Store user ID in session and log the user in
            session['user_id'] = user_id
            session['signup_email'] = email

            try:
                user = User.get_by_id(user_id)
                if user:
                    login_user(user)
            except Exception:
                pass

            # Redirect to homepage after completing About You
            return redirect(url_for('main.home'))

        except Exception as e:
            error_msg = str(e)
            print(f"Signup error: {error_msg}")
            # If host resolution fails, provide clearer guidance
            if 'Unknown MySQL server host' in error_msg or 'getaddrinfo failed' in error_msg:
                guidance = (
                    "Could not reach MySQL host.\n"
                    "Please verify the hostname in your Config (Config.MYSQL_HOST),\n"
                    "ensure DNS resolves it or try the database IP address, and confirm port/network access."
                )
                return render_template('auth/signup.html', user=user_data, error=guidance)

            return render_template('auth/signup.html',
                user=user_data,
                error=f"An error occurred while creating your account: {error_msg[:200]}",
                location_enabled=location_enabled
            )

    # GET: render the About You / signup form
    return render_template('auth/signup.html', user={})


def allowed_file(filename, allowed_extensions):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions





@auth_bp.route('/signup2', methods=['GET', 'POST'])
def signup_step2():
    """Handle the second signup step - can be interests, connections, etc."""
    if 'user_id' not in session:
        return redirect(url_for('auth.signup'))
    
    # Placeholder for step 2 - redirect to home
    return redirect(url_for('main.home'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    lockout_seconds = None
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('auth/login.html', error="Username and password required.")

        # Session recording the number of failed attempts
        failed_attempts = session.get('failed_attempts', 0)
        lockout_time = session.get('lockout_time')

        if lockout_time:
            lockout_time = datetime.fromisoformat(lockout_time)  # string to datetime
            if datetime.now() < lockout_time:
                remaining_seconds = int((lockout_time - datetime.now()).total_seconds())
                return render_template('auth/login.html', 
                    error="Too many failed attempts.", 
                    lockout_seconds=remaining_seconds)
            else:
                session.pop('failed_attempts', None)
                session.pop('lockout_time', None)
                failed_attempts = 0

        # Check credentials
        user = User.get_by_username(username)

        if user and user.check_password(password):
            # Successful login - clear attempts
            session.pop('failed_attempts', None)
            session.pop('lockout_time', None)
            login_user(user)
            
            return redirect(url_for('main.home'))
        else:
            # Failed login - increment counter
            failed_attempts += 1
            session['failed_attempts'] = failed_attempts
            
            if failed_attempts >= 3:
                # Lock out for 20 seconds
                lockout_time = datetime.now() + timedelta(seconds=20)
                session['lockout_time'] = lockout_time.isoformat()  # datetime to string
                return render_template('auth/login.html', 
                    error="Too many failed attempts.", 
                    lockout_seconds=20)
            else:
                remaining_attempts = 3 - failed_attempts
                return render_template('auth/login.html', 
                    error=f"Invalid username or password. {remaining_attempts} attempt(s) remaining.")

    # GET request - check if already locked out
    lockout_time = session.get('lockout_time')
    
    if lockout_time:
        lockout_time = datetime.fromisoformat(lockout_time)
        if datetime.now() < lockout_time:
            remaining_seconds = int((lockout_time - datetime.now()).total_seconds())
            return render_template('auth/login.html',
                error="Too many failed attempts.",
                lockout_seconds=remaining_seconds)
        else:
            session.pop('failed_attempts', None)
            session.pop('lockout_time', None)
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))
