from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from flask_login import login_required, current_user, login_user
from models import User, Interest
from utils import save_profile_picture, calculate_age, get_age_group
from datetime import datetime

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """Step 2: About You - Profile Setup"""
    if 'signup_data' not in session and not current_user.is_authenticated:
        return redirect(url_for('auth.signup'))
    
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        display_name = request.form.get('display_name')
        dob_str = request.form.get('date_of_birth')
        phone_number = request.form.get('phone_number')
        location_enabled = request.form.get('location_enabled') == 'on'
        profile_picture = request.files.get('profile_picture')
        
        # Parse date of birth
        try:
            dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        except:
            flash('Invalid date format', 'error')
            return render_template('auth/profile_setup.html')
        
        # Calculate age and validate
        age = calculate_age(dob)
        
        if age < 13:
            flash('You must be at least 13 years old to sign up', 'error')
            return render_template('auth/profile_setup.html')
        
        # Determine age group
        age_group = get_age_group(age)
        
        # If new signup, create user
        if 'signup_data' in session:
            signup_data = session['signup_data']
            user_id = User.create_user(
                signup_data['email'],
                signup_data['username'],
                signup_data['password']
            )
            
            # Get the newly created user
            user = User.get_by_id(user_id)
            
            # Update profile
            profile_pic_filename = None
            if profile_picture:
                profile_pic_filename = save_profile_picture(profile_picture, user_id)
            
            user.update_profile({
                'first_name': first_name,
                'last_name': last_name,
                'display_name': display_name,
                'date_of_birth': dob,
                'phone_number': phone_number,
                'age_group': age_group,
                'location_enabled': location_enabled,
                'profile_picture': profile_pic_filename
            })
            
            # Login user
            login_user(user)
            
            # Clear signup session data
            session.pop('signup_data', None)
        
        # If existing user updating profile
        elif current_user.is_authenticated:
            profile_pic_filename = current_user.profile_picture
            if profile_picture:
                profile_pic_filename = save_profile_picture(profile_picture, current_user.id)
            
            current_user.update_profile({
                'first_name': first_name,
                'last_name': last_name,
                'display_name': display_name,
                'date_of_birth': dob,
                'phone_number': phone_number,
                'age_group': age_group,
                'location_enabled': location_enabled,
                'profile_picture': profile_pic_filename
            })
        
        return redirect(url_for('profile.interests'))
    
    return render_template('auth/profile_setup.html')


@profile_bp.route('/interests', methods=['GET', 'POST'])
@login_required
def interests():
    """Step 3: Interest Selection"""
    all_interests = Interest.get_all()
    
    if request.method == 'POST':
        selected_ids = request.form.getlist('interests')
        
        if len(selected_ids) < 2:
            flash('Please select at least 2 interests', 'error')
            return render_template('auth/interests.html', interests=all_interests)
        
        # Convert to integers
        selected_ids = [int(id) for id in selected_ids]
        
        # Save interests
        current_user.set_interests(selected_ids)
        
        return redirect(url_for('profile.connections'))
    
    return render_template('auth/interests.html', interests=all_interests)


@profile_bp.route('/connections', methods=['GET', 'POST'])
@login_required
def connections():
    """Step 4: Connections (Placeholder)"""
    if request.method == 'POST':
        # Mark profile as completed
        current_user.mark_profile_completed()
        
        return redirect(url_for('main.home'))
    
    return render_template('auth/connections.html')


@profile_bp.route('/calculate-age', methods=['POST'])
def calculate_age_ajax():
    """AJAX endpoint to calculate age group"""
    dob_str = request.json.get('date_of_birth')
    
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        age = calculate_age(dob)
        
        if age < 13:
            return jsonify({'valid': False, 'message': 'Must be at least 13 years old'})
        
        age_group_name = get_age_group(age)
        age_group_display = age_group_name.capitalize() if age_group_name else ''
        
        return jsonify({'valid': True, 'age': age, 'age_group': age_group_display})
    except:
        return jsonify({'valid': False, 'message': 'Invalid date'})
