from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Event, EventRegistration, EventSubmission, User
from datetime import datetime, timedelta
import re
import os
import base64
from google import genai
from werkzeug.utils import secure_filename
from pathlib import Path
from config import Config

events_bp = Blueprint('events', __name__)


def is_valid_phone(phone):
    return bool(re.fullmatch(r'[89]\d{7}', phone))


def is_valid_email(email):
    return bool(re.fullmatch(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', email))


def parse_date(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def get_singapore_today():
    return (datetime.utcnow() + timedelta(hours=8)).date()


def is_at_least_13(dob_date, today_date):
    age = today_date.year - dob_date.year - ((today_date.month, today_date.day) < (dob_date.month, dob_date.day))
    return age >= 13


def is_valid_preferred_date(preferred_date, today_date):
    min_date = today_date + timedelta(days=7)
    return preferred_date >= min_date


@events_bp.route('/')
@login_required
def events_home():
    """Main events page with carousel, navigation, and my events"""
    upcoming_events = Event.get_all_upcoming()
    my_events = Event.get_user_registered_events(current_user.id)
    
    # Get IDs of events user is already registered for
    registered_event_ids = set([event['id'] for event in my_events]) if my_events else set()
    
    # Filter out events user is already registered for from upcoming events
    if upcoming_events:
        upcoming_events = [event for event in upcoming_events if event['id'] not in registered_event_ids]
    
    # Convert timedelta objects to strings for JSON serialization in template
    if upcoming_events:
        for event in upcoming_events:
            if event.get('start_time'):
                event['start_time'] = str(event['start_time'])
            if event.get('end_time'):
                event['end_time'] = str(event['end_time'])
    
    if my_events:
        for event in my_events:
            if event.get('start_time'):
                event['start_time'] = str(event['start_time'])
            if event.get('end_time'):
                event['end_time'] = str(event['end_time'])
    
    return render_template('events/events_home.html',
                         upcoming_events=upcoming_events,
                         my_events=my_events,
                         maps_api_key=Config.GOOGLE_MAPS_API_KEY)


@events_bp.route('/event/<int:event_id>')
@login_required
def event_details(event_id):
    """Get event details for modal"""
    event = Event.get_by_id(event_id)
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    # Convert timedelta objects to strings for JSON serialization
    if event.get('start_time'):
        event['start_time'] = str(event['start_time'])
    if event.get('end_time'):
        event['end_time'] = str(event['end_time'])
    if event.get('event_date'):
        event['event_date'] = event['event_date'].isoformat() if hasattr(event['event_date'], 'isoformat') else str(event['event_date'])
    
    is_registered = Event.is_user_registered(event_id, current_user.id)
    return jsonify({
        'event': event,
        'is_registered': is_registered
    })


@events_bp.route('/signup/<int:event_id>', methods=['GET', 'POST'])
@login_required
def signup_event(event_id):
    """Event signup form"""
    event = Event.get_by_id(event_id)
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('events.events_home'))
    
    # Check if already registered
    if Event.is_user_registered(event_id, current_user.id):
        flash('You are already registered for this event', 'info')
        return redirect(url_for('events.events_home'))
    
    # Check if event is full
    if event.get('max_participants') and event.get('current_participants', 0) >= event['max_participants']:
        flash('This event is full', 'error')
        return redirect(url_for('events.events_home'))
    
    if request.method == 'POST':
        # Validate required fields
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        confirmed = request.form.get('confirmed') == 'on'
        
        if not all([full_name, email, phone]):
            flash('All fields are required', 'error')
            return render_template('events/signup_form.html', event=event)

        if not is_valid_email(email):
            flash('Please provide a valid email address', 'error')
            return render_template('events/signup_form.html', event=event)

        if not is_valid_phone(phone):
            flash('Phone number must be 8 digits and start with 8 or 9', 'error')
            return render_template('events/signup_form.html', event=event)
        
        if not confirmed:
            flash('Please confirm your availability', 'error')
            return render_template('events/signup_form.html', event=event)
        
        try:
            # Create registration
            EventRegistration.create({
                'event_id': event_id,
                'user_id': current_user.id,
                'full_name': full_name,
                'email': email,
                'phone_number': phone,
                'confirmed': confirmed
            })
            
            flash('Successfully registered for the event!', 'success')
            return redirect(url_for('events.events_home'))
        
        except Exception as e:
            print(f"Registration error: {e}")
            flash('Error registering for event. Please try again.', 'error')
            return render_template('events/signup_form.html', event=event)
    
    return render_template('events/signup_form.html', event=event)


@events_bp.route('/optout/<int:event_id>', methods=['POST'])
@login_required
def optout_event(event_id):
    """Cancel event registration"""
    try:
        EventRegistration.cancel_registration(event_id, current_user.id)
        flash('Successfully cancelled your registration', 'success')
    except Exception as e:
        print(f"Opt-out error: {e}")
        flash('Error cancelling registration', 'error')
    
    return redirect(url_for('events.events_home'))


@events_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit_event():
    """Event submission form for users"""
    if request.method == 'POST':
        try:
            # Organizer info
            organizer_name = request.form.get('organizer_name', '').strip()
            organizer_dob = request.form.get('organizer_dob', '').strip()
            organizer_age_group = request.form.get('organizer_age_group', '').strip()
            organizer_email = request.form.get('organizer_email', '').strip()
            organizer_phone = request.form.get('organizer_phone', '').strip()
            organizer_location = request.form.get('organizer_location', '').strip()
            
            # Event details
            event_title = request.form.get('event_title', '').strip()
            event_summary = request.form.get('event_summary', '').strip()
            event_type = request.form.get('event_type', '').strip()
            preferred_date = request.form.get('preferred_date', '').strip()
            expected_participants = request.form.get('expected_participants', '').strip()
            
            # Additional info
            why_meaningful = request.form.get('why_meaningful', '').strip()
            previous_experience = request.form.get('previous_experience', '').strip()
            accessibility = request.form.get('accessibility', '').strip()
            
            # Validate required fields
            required_fields = {
                'organizer_name': organizer_name,
                'organizer_dob': organizer_dob,
                'organizer_email': organizer_email,
                'organizer_phone': organizer_phone,
                'event_title': event_title,
                'event_summary': event_summary,
                'event_type': event_type,
                'preferred_date': preferred_date,
                'expected_participants': expected_participants,
                'why_meaningful': why_meaningful,
                'accessibility': accessibility
            }
            
            missing_fields = [k for k, v in required_fields.items() if not v]
            if missing_fields:
                flash('Please fill in all required fields', 'error')
                return render_template('events/submit_event.html', form_data=request.form, user_language=current_user.language or 'en')

            if not is_valid_email(organizer_email):
                flash('Please provide a valid email address', 'error')
                return render_template('events/submit_event.html', form_data=request.form, user_language=current_user.language or 'en')

            if not is_valid_phone(organizer_phone):
                flash('Phone number must be 8 digits and start with 8 or 9', 'error')
                return render_template('events/submit_event.html', form_data=request.form, user_language=current_user.language or 'en')

            dob_date = parse_date(organizer_dob)
            if not dob_date:
                flash('Please provide a valid date of birth', 'error')
                return render_template('events/submit_event.html', form_data=request.form, user_language=current_user.language or 'en')

            today_date = get_singapore_today()
            if not is_at_least_13(dob_date, today_date):
                flash('You must be at least 13 years old to create an event', 'error')
                return render_template('events/submit_event.html', form_data=request.form, user_language=current_user.language or 'en')

            preferred_date_value = parse_date(preferred_date)
            if not preferred_date_value:
                flash('Please provide a valid preferred date', 'error')
                return render_template('events/submit_event.html', form_data=request.form, user_language=current_user.language or 'en')

            if not is_valid_preferred_date(preferred_date_value, today_date):
                flash('Preferred date must be at least 1 week from today', 'error')
                return render_template('events/submit_event.html', form_data=request.form, user_language=current_user.language or 'en')
            
            # Validate event summary length (max 150 characters)
            if len(event_summary) > 150:
                flash('Event summary must be 150 characters or less', 'error')
                return render_template('events/submit_event.html', form_data=request.form, user_language=current_user.language or 'en')
            # Handle submission image upload (optional)
            image_url = None
            if 'submission_image' in request.files:
                file = request.files['submission_image']
                if file and file.filename:
                    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
                    filename = secure_filename(file.filename)
                    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                    if file_ext in allowed_extensions:
                        unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                        upload_dir = os.path.join('static', 'uploads', 'events')
                        os.makedirs(upload_dir, exist_ok=True)
                        filepath = os.path.join(upload_dir, unique_filename)
                        file.save(filepath)
                        image_url = f'/static/uploads/events/{unique_filename}'
                    else:
                        flash('Invalid file type. Please upload PNG, JPG, JPEG, or GIF.', 'error')
                        return render_template('events/submit_event.html', form_data=request.form, user_language=current_user.language or 'en')

            # Create submission
            EventSubmission.create({
                'user_id': current_user.id,
                'organizer_name': organizer_name,
                'organizer_dob': organizer_dob if organizer_dob else None,
                'organizer_age_group': organizer_age_group if organizer_age_group else None,
                'organizer_email': organizer_email,
                'organizer_phone': organizer_phone,
                'organizer_location': organizer_location if organizer_location else None,
                'event_title': event_title,
                'event_summary': event_summary,
                'event_type': event_type,
                'image_url': image_url,
                'preferred_date': preferred_date,
                'expected_participants': expected_participants,
                'why_meaningful': why_meaningful,
                'previous_experience': previous_experience if previous_experience else None,
                'accessibility_considerations': accessibility
            })
            
            flash('Event submission successful! We will review it within 3-5 business days.', 'success')
            return redirect(url_for('events.my_submissions'))
        
        except Exception as e:
            print(f"Submission error: {e}")
            flash(f'Error submitting event: {str(e)}', 'error')
            return render_template('events/submit_event.html', form_data=request.form, user_language=current_user.language or 'en')
    
    return render_template('events/submit_event.html', form_data={}, user_language=current_user.language or 'en')


@events_bp.route('/my-submissions')
@login_required
def my_submissions():
    """View user's event submissions"""
    submissions = EventSubmission.get_by_user(current_user.id)
    return render_template('events/my_submissions.html', submissions=submissions)


@events_bp.route('/submissions/<int:submission_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_submission(submission_id):
    """Edit event submission (only if pending)"""
    submission = EventSubmission.get_by_id(submission_id)
    
    if not submission:
        flash('Submission not found', 'error')
        return redirect(url_for('events.my_submissions'))
    
    # Check ownership
    if submission['user_id'] != current_user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('events.my_submissions'))
    
    # Can only edit pending submissions
    if submission['status'] != 'pending':
        flash('Cannot edit submissions that have been reviewed', 'error')
        return redirect(url_for('events.my_submissions'))
    
    if request.method == 'POST':
        try:
            # Organizer info
            organizer_name = request.form.get('organizer_name', '').strip()
            organizer_dob = request.form.get('organizer_dob', '').strip()
            organizer_age_group = request.form.get('organizer_age_group', '').strip()
            organizer_email = request.form.get('organizer_email', '').strip()
            organizer_phone = request.form.get('organizer_phone', '').strip()
            organizer_location = request.form.get('organizer_location', '').strip()
            
            # Event details
            event_title = request.form.get('event_title', '').strip()
            event_summary = request.form.get('event_summary', '').strip()
            event_type = request.form.get('event_type', '').strip()
            preferred_date = request.form.get('preferred_date', '').strip()
            expected_participants = request.form.get('expected_participants', '').strip()
            
            # Additional info
            why_meaningful = request.form.get('why_meaningful', '').strip()
            previous_experience = request.form.get('previous_experience', '').strip()
            accessibility = request.form.get('accessibility', '').strip()
            
            # Validate required fields
            required_fields = {
                'organizer_name': organizer_name,
                'organizer_dob': organizer_dob,
                'organizer_email': organizer_email,
                'organizer_phone': organizer_phone,
                'event_title': event_title,
                'event_summary': event_summary,
                'event_type': event_type,
                'preferred_date': preferred_date,
                'expected_participants': expected_participants,
                'why_meaningful': why_meaningful,
                'accessibility': accessibility
            }
            
            missing_fields = [k for k, v in required_fields.items() if not v]
            if missing_fields:
                flash('Please fill in all required fields', 'error')
                return render_template('events/edit_submission.html', submission=submission, user_language=current_user.language or 'en')

            if not is_valid_email(organizer_email):
                flash('Please provide a valid email address', 'error')
                return render_template('events/edit_submission.html', submission=submission, user_language=current_user.language or 'en')

            if not is_valid_phone(organizer_phone):
                flash('Phone number must be 8 digits and start with 8 or 9', 'error')
                return render_template('events/edit_submission.html', submission=submission, user_language=current_user.language or 'en')

            dob_date = parse_date(organizer_dob)
            if not dob_date:
                flash('Please provide a valid date of birth', 'error')
                return render_template('events/edit_submission.html', submission=submission, user_language=current_user.language or 'en')

            today_date = get_singapore_today()
            if not is_at_least_13(dob_date, today_date):
                flash('You must be at least 13 years old to create an event', 'error')
                return render_template('events/edit_submission.html', submission=submission, user_language=current_user.language or 'en')

            preferred_date_value = parse_date(preferred_date)
            if not preferred_date_value:
                flash('Please provide a valid preferred date', 'error')
                return render_template('events/edit_submission.html', submission=submission, user_language=current_user.language or 'en')

            if not is_valid_preferred_date(preferred_date_value, today_date):
                flash('Preferred date must be at least 1 week from today', 'error')
                return render_template('events/edit_submission.html', submission=submission, user_language=current_user.language or 'en')
            
            # Validate event summary length (max 150 characters)
            if len(event_summary) > 150:
                flash('Event summary must be 150 characters or less', 'error')
                return render_template('events/edit_submission.html', submission=submission, user_language=current_user.language or 'en')
            
            # Handle new/updated submission image
            image_url = submission.get('image_url') if submission else None
            if 'submission_image' in request.files:
                file = request.files['submission_image']
                if file and file.filename:
                    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
                    filename = secure_filename(file.filename)
                    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                    if file_ext in allowed_extensions:
                        unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                        upload_dir = os.path.join('static', 'uploads', 'events')
                        os.makedirs(upload_dir, exist_ok=True)
                        filepath = os.path.join(upload_dir, unique_filename)
                        file.save(filepath)
                        image_url = f'/static/uploads/events/{unique_filename}'
                    else:
                        flash('Invalid file type. Please upload PNG, JPG, JPEG, or GIF.', 'error')
                        return render_template('events/edit_submission.html', submission=submission, user_language=current_user.language or 'en')

            # Update submission
            EventSubmission.update(submission_id, {
                'organizer_name': organizer_name,
                'organizer_dob': organizer_dob if organizer_dob else None,
                'organizer_age_group': organizer_age_group if organizer_age_group else None,
                'organizer_email': organizer_email,
                'organizer_phone': organizer_phone,
                'organizer_location': organizer_location if organizer_location else None,
                'event_title': event_title,
                'event_summary': event_summary,
                'event_type': event_type,
                'preferred_date': preferred_date,
                'expected_participants': expected_participants,
                'why_meaningful': why_meaningful,
                'previous_experience': previous_experience if previous_experience else None,
                'accessibility_considerations': accessibility,
                'image_url': image_url
            })
            
            flash('Submission updated successfully!', 'success')
            return redirect(url_for('events.my_submissions'))
        
        except Exception as e:
            print(f"Update error: {e}")
            flash(f'Error updating submission: {str(e)}', 'error')
            return render_template('events/edit_submission.html', submission=submission, user_language=current_user.language or 'en')
    
    return render_template('events/edit_submission.html', submission=submission, user_language=current_user.language or 'en')


@events_bp.route('/submissions/<int:submission_id>/delete', methods=['POST'])
@login_required
def delete_submission(submission_id):
    """Delete event submission"""
    submission = EventSubmission.get_by_id(submission_id)
    
    if not submission:
        flash('Submission not found', 'error')
        return redirect(url_for('events.my_submissions'))
    
    # Check ownership or admin
    if submission['user_id'] != current_user.id and current_user.user_type != 'admin':
        flash('Unauthorized access', 'error')
        return redirect(url_for('events.my_submissions'))
    
    try:
        EventSubmission.delete(submission_id)
        flash('Submission deleted successfully', 'success')
    except Exception as e:
        print(f"Delete error: {e}")
        flash('Error deleting submission', 'error')
    
    return redirect(url_for('events.my_submissions'))


# Admin routes
@events_bp.route('/admin/submissions')
@login_required
def admin_submissions():
    """Admin view of all event submissions"""
    if current_user.user_type != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('events.events_home'))
    
    submissions = EventSubmission.get_all()
    return render_template('events/admin_submissions.html', submissions=submissions)


@events_bp.route('/admin/submissions/<int:submission_id>/review', methods=['GET', 'POST'])
@login_required
def admin_review_submission(submission_id):
    """Admin review and approve/reject submission"""
    if current_user.user_type != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('events.events_home'))
    
    submission = EventSubmission.get_by_id(submission_id)
    if not submission:
        flash('Submission not found', 'error')
        return redirect(url_for('events.admin_submissions'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        admin_notes = request.form.get('admin_notes', '').strip()
        
        if action == 'approve':
            # Update status
            EventSubmission.update_status(submission_id, 'approved', current_user.id, admin_notes)
            
            # Create event from approved submission
            try:
                    Event.create({
                        'title': submission['event_title'],
                        'description': submission['event_summary'],
                        'event_date': submission['preferred_date'],
                        'start_time': '09:00:00',  # Default time, can be customized
                        'end_time': '17:00:00',    # Default time, can be customized
                        'location': submission['organizer_location'] or 'TBA',
                        'location_address': submission['organizer_location'],
                        'latitude': None,
                        'longitude': None,
                        'image_url': submission.get('image_url'),
                        'max_participants': 50,  # Default, parse from expected_participants if needed
                        'event_type': submission['event_type'],
                        'age_group': submission['organizer_age_group'],
                        'created_by': current_user.id
                    })
                    flash('Submission approved and event created!', 'success')
            except Exception as e:
                    print(f"Event creation error: {e}")
                    flash('Submission approved but event creation failed. Please create manually.', 'warning')
            
        elif action == 'reject':
            EventSubmission.update_status(submission_id, 'rejected', current_user.id, admin_notes)
            flash('Submission rejected', 'success')
        
        elif action == 'revoke':
            # Revoke the approval, changing status back to pending
            EventSubmission.update_status(submission_id, 'pending', current_user.id, 'Approval revoked by admin')
            flash('Submission approval revoked and returned to pending', 'info')
        
        return redirect(url_for('events.admin_submissions'))
    
    return render_template('events/admin_review.html', submission=submission)


@events_bp.route('/api/generate-ai-image', methods=['POST'])
@login_required
def generate_ai_image():
    """Generate AI image using Google Gemini 2.5 Flash Image"""
    if current_user.user_type != 'admin':
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    try:
        data = request.get_json()
        title = data.get('title', '').strip()
        event_type = data.get('event_type', '').strip()
        event_date = data.get('event_date', '').strip()
        start_time = data.get('start_time', '').strip()
        end_time = data.get('end_time', '').strip()
        location = data.get('location', '').strip()
        
        if not title:
            return jsonify({'success': False, 'error': 'Event title is required'}), 400
        
        # Build detailed prompt with event information
        prompt_parts = []
        
        # Main event description
        if event_type:
            prompt_parts.append(f"A {event_type} event for {title}")
        else:
            prompt_parts.append(f"An event for {title}")
        
        # Add timing details if provided
        if event_date:
            prompt_parts.append(f"scheduled for {event_date}")
        
        if start_time and end_time:
            prompt_parts.append(f"from {start_time} to {end_time}")
        elif start_time:
            prompt_parts.append(f"starting at {start_time}")
        
        # Add location if provided
        if location:
            prompt_parts.append(f"taking place in {location}")
        
        # Combine all parts and add styling
        prompt = ", ".join(prompt_parts) + ", professional event poster style, vibrant colors, inviting atmosphere"
        
        # Initialize Google Genai client
        client = genai.Client(api_key=Config.GOOGLE_GENAI_API_KEY)
        
        # Generate image using Gemini 2.5 Flash Image
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt
        )
        
        print(f"DEBUG: Response type: {type(response)}")
        print(f"DEBUG: Response: {response}")
        
        # Extract image from response
        # Gemini returns the image in the response parts
        if response and hasattr(response, 'candidates') and response.candidates:
            print(f"DEBUG: Found {len(response.candidates)} candidates")
            
            for candidate_idx, candidate in enumerate(response.candidates):
                print(f"DEBUG: Candidate {candidate_idx}: {candidate}")
                
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        print(f"DEBUG: Found {len(candidate.content.parts)} parts")
                        
                        for part_idx, part in enumerate(candidate.content.parts):
                            print(f"DEBUG: Part {part_idx} type: {type(part)}, has inline_data: {hasattr(part, 'inline_data')}")
                            
                            if hasattr(part, 'inline_data') and part.inline_data:
                                print(f"DEBUG: inline_data type: {type(part.inline_data)}")
                                
                                # Get image bytes directly from Blob object
                                # Google Genai Blob has 'data' attribute with raw bytes
                                if hasattr(part.inline_data, 'data'):
                                    image_data = part.inline_data.data
                                    print(f"DEBUG: Image data type: {type(image_data)}, length: {len(image_data) if image_data else 0}")
                                    
                                    # Check if it's already bytes or if it's base64 string
                                    if isinstance(image_data, bytes):
                                        # Already in bytes format
                                        image_bytes = image_data
                                        print(f"DEBUG: Using direct bytes")
                                    elif isinstance(image_data, str):
                                        # It's a base64 string, decode it
                                        try:
                                            image_bytes = base64.b64decode(image_data)
                                            print(f"DEBUG: Decoded from base64")
                                        except Exception as decode_error:
                                            print(f"DEBUG: Decode error: {decode_error}")
                                            continue
                                    else:
                                        print(f"DEBUG: Unknown data type, skipping")
                                        continue
                                else:
                                    print(f"DEBUG: No 'data' attribute found")
                                    continue
                                
                                # Create uploads directory if it doesn't exist
                                upload_dir = Path('static/uploads/events')
                                upload_dir.mkdir(parents=True, exist_ok=True)
                                
                                # Generate unique filename
                                filename = f"ai_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secure_filename(title[:30])}.png"
                                filepath = upload_dir / filename
                                
                                with open(filepath, 'wb') as f:
                                    f.write(image_bytes)
                                
                                print(f"DEBUG: Saved image to {filepath}, size: {len(image_bytes)} bytes")
                                
                                image_url = f'/static/uploads/events/{filename}'
                                
                                return jsonify({
                                    'success': True,
                                    'image_url': image_url,
                                    'prompt': prompt
                                })
            
            return jsonify({'success': False, 'error': 'No image data found in response parts'}), 500
        else:
            print(f"DEBUG: No candidates in response")
            return jsonify({'success': False, 'error': 'No candidates in API response'}), 500
            
    except Exception as e:
        error_str = str(e)
        print(f"Gemini API error: {e}")
        
        # Handle specific error types with user-friendly messages
        if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'quota' in error_str.lower():
            return jsonify({
                'success': False, 
                'error': 'API quota limit reached. Please try again later or check your Google AI billing plan.'
            }), 429
        elif '401' in error_str or 'UNAUTHENTICATED' in error_str:
            return jsonify({
                'success': False, 
                'error': 'Invalid API key. Please check your GOOGLE_GENAI_API_KEY configuration.'
            }), 401
        elif '403' in error_str or 'PERMISSION_DENIED' in error_str:
            return jsonify({
                'success': False, 
                'error': 'API access denied. Please ensure your API key has proper permissions.'
            }), 403
        else:
            return jsonify({'success': False, 'error': f'AI service error: {error_str[:200]}'}), 500


@events_bp.route('/admin/events/create', methods=['GET', 'POST'])
@login_required
def admin_create_event():
    """Admin create event (from approved submission or manually)"""
    if current_user.user_type != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('events.events_home'))
    
    submission_id = request.args.get('from_submission')
    submission = None
    
    if submission_id:
        submission = EventSubmission.get_by_id(submission_id)
    
    if request.method == 'POST':
        try:
            # Get form data
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            event_date = request.form.get('event_date', '').strip()
            start_time = request.form.get('start_time', '').strip()
            end_time = request.form.get('end_time', '').strip()
            location = request.form.get('location', '').strip()
            location_address = request.form.get('location_address', '').strip()
            max_participants = request.form.get('max_participants', '').strip()
            event_type = request.form.get('event_type', '').strip()
            
            # Validate required fields
            if not all([title, description, event_date, start_time, end_time, location]):
                flash('Please fill in all required fields', 'error')
                return render_template('events/admin_create_event.html', submission=submission, form_data=request.form)
            
            # Handle image upload or AI-generated image
            image_url = None
            
            # Check if AI-generated image URL is provided
            ai_image_url = request.form.get('ai_image_url', '').strip()
            if ai_image_url:
                image_url = ai_image_url
            else:
                # Check if manual file upload
                if 'image' in request.files:
                    file = request.files['image']
                    if file and file.filename:
                        # Validate file
                        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
                        filename = secure_filename(file.filename)
                        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                        
                        if file_ext in allowed_extensions:
                            # Create unique filename
                            unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
                            
                            # Ensure upload directory exists
                            upload_dir = os.path.join('static', 'uploads', 'events')
                            os.makedirs(upload_dir, exist_ok=True)
                            
                            # Save file
                            filepath = os.path.join(upload_dir, unique_filename)
                            file.save(filepath)
                            
                            image_url = f'/static/uploads/events/{unique_filename}'
                        else:
                            flash('Invalid file type. Please upload PNG, JPG, JPEG, or GIF.', 'error')
                            return render_template('events/admin_create_event.html', submission=submission, form_data=request.form)
            
            # Create event
            Event.create({
                'title': title,
                'description': description,
                'event_date': event_date,
                'start_time': start_time,
                'end_time': end_time,
                'location': location,
                'location_address': location_address,
                'max_participants': int(max_participants) if max_participants else None,
                'event_type': event_type,
                'image_url': image_url,
                'created_by': current_user.id
            })
            
            flash('Event created successfully!', 'success')
            return redirect(url_for('events.events_home'))
        
        except Exception as e:
            print(f"Event creation error: {e}")
            flash(f'Error creating event: {str(e)}', 'error')
            return render_template('events/admin_create_event.html', submission=submission, form_data=request.form)
    
    return render_template('events/admin_create_event.html', submission=submission, form_data={})



