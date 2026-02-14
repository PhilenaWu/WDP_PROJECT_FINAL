from flask import Blueprint, redirect, url_for, render_template, request, flash
from flask_login import login_required, current_user
from datetime import datetime
from database import execute_query
from models import User
from utils import save_profile_picture, calculate_age, get_age_group
import re

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    return redirect(url_for('main.home'))


@profile_bp.route('/interests', methods=['GET', 'POST'])
def interests():
    return redirect(url_for('main.home'))

@profile_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        display_name = request.form.get('display_name', '').strip()
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        phone_number = request.form.get('phone_number', '').strip()
        date_of_birth_str = request.form.get('date_of_birth', '').strip()
        new_password = request.form.get('password', '').strip()

        gmail_pattern = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'
        if not re.match(gmail_pattern, email):
            flash('Please enter a valid Gmail address ending with @gmail.com.', 'error')
            return render_template('auth/profile.html', user=user, dob_value=_format_dob(user))

        if email != (user.email or '').lower():
            existing_email_user = User.get_by_email(email)
            if existing_email_user and existing_email_user.id != user.id:
                flash('Email already registered. Please use a different Gmail address.', 'error')
                return render_template('auth/profile.html', user=user, dob_value=_format_dob(user))

        if username and username != user.username:
            existing_user = User.get_by_username(username)
            if existing_user:
                flash('Username already taken. Please choose another.', 'error')
                return render_template('auth/profile.html', user=user, dob_value=_format_dob(user))

        date_of_birth = user.date_of_birth
        age_group = user.age_group
        if date_of_birth_str:
            try:
                date_of_birth = datetime.strptime(date_of_birth_str, '%Y-%m-%d').date()
                age = calculate_age(date_of_birth)
                age_group = get_age_group(age)
            except ValueError:
                flash('Invalid date format. Please use YYYY-MM-DD.', 'error')
                return render_template('auth/profile.html', user=user, dob_value=_format_dob(user))

        profile_picture = request.files.get('profile_picture')
        profile_picture_filename = user.profile_picture
        if profile_picture and profile_picture.filename:
            saved_filename = save_profile_picture(profile_picture, user.id)
            if saved_filename:
                profile_picture_filename = saved_filename

        password_hash = user.password_hash if not new_password else new_password

        execute_query(
            """
            UPDATE users SET
                username = %s,
                email = %s,
                password_hash = %s,
                display_name = %s,
                first_name = %s,
                last_name = %s,
                phone_number = %s,
                date_of_birth = %s,
                age_group = %s,
                profile_picture = %s
            WHERE id = %s
            """,
            (
                username or user.username,
                email,
                password_hash,
                display_name,
                first_name,
                last_name,
                phone_number,
                date_of_birth,
                age_group,
                profile_picture_filename,
                user.id,
            ),
            commit=True,
        )

        user.username = username or user.username
        user.email = email
        user.display_name = display_name
        user.first_name = first_name
        user.last_name = last_name
        user.phone_number = phone_number
        user.date_of_birth = date_of_birth
        user.age_group = age_group
        user.profile_picture = profile_picture_filename
        if new_password:
            user.password_hash = new_password

        flash('Profile updated successfully.', 'success')

    return render_template('auth/profile.html', user=user, dob_value=_format_dob(user))


def _format_dob(user):
    date_of_birth = user.date_of_birth
    if hasattr(date_of_birth, 'strftime'):
        return date_of_birth.strftime('%Y-%m-%d')
    return date_of_birth or ''
