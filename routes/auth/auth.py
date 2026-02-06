from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_login import login_user, logout_user, current_user
from models import User

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        if not all([email, username, password, confirm_password]):
            flash('All fields are required', 'error')
            return render_template('auth/signup.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/signup.html')
        
        if len(password) < 8:
            flash('Password must be at least 8 characters', 'error')
            return render_template('auth/signup.html')
        
        # Check if user exists
        if User.get_by_email(email):
            flash('Email already registered', 'error')
            return render_template('auth/signup.html')
        
        if User.get_by_username(username):
            flash('Username already taken', 'error')
            return render_template('auth/signup.html')
        
        # Store in session for multi-step form
        session['signup_data'] = {
            'email': email,
            'username': username,
            'password': password
        }
        
        return redirect(url_for('auth.signup_loading'))
    
    return render_template('auth/signup.html')


@auth_bp.route('/signup/loading')
def signup_loading():
    if 'signup_data' not in session:
        return redirect(url_for('auth.signup'))
    return render_template('auth/signup_loading.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.get_by_username(username)
        
        if user and user.check_password(password):
            login_user(user)
            
            if not user.profile_completed:
                return redirect(url_for('profile.setup'))
            
            return redirect(url_for('main.home'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))
