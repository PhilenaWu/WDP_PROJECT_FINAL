import os
from werkzeug.utils import secure_filename
from flask import current_app
from PIL import Image
from datetime import datetime

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def save_profile_picture(file, user_id):
    """Save and resize profile picture"""
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        filename = f"user_{user_id}_profile.{ext}"
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        img = Image.open(file)
        img.thumbnail((400, 400))
        img.save(filepath)
        
        return filename
    return None

def calculate_age(dob):
    """Calculate age from date of birth"""
    today = datetime.today()
    if isinstance(dob, str):
        dob = datetime.strptime(dob, '%Y-%m-%d').date()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    return age

def get_age_group(age):
    """Determine age group from age"""
    if age < 13:
        return None
    elif 13 <= age <= 20:
        return 'youth'
    elif 21 <= age <= 59:
        return 'adult'
    else:
        return 'elderly'
