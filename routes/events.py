from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Event, EventRegistration, EventSubmission, User
from datetime import datetime
from config import Config

events_bp = Blueprint('events', __name__)


@events_bp.route('/')
@login_required
def events_home():
    """Main events page with carousel, navigation, and my events"""
    upcoming_events = Event.get_all_upcoming()
    my_events = Event.get_user_registered_events(current_user.id)
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
                return render_template('events/submit_event.html', form_data=request.form)
            
            # Validate event summary length (max 150 characters)
            if len(event_summary) > 150:
                flash('Event summary must be 150 characters or less', 'error')
                return render_template('events/submit_event.html', form_data=request.form)
            
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
            return render_template('events/submit_event.html', form_data=request.form)
    
    return render_template('events/submit_event.html', form_data={})


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
        # Update logic here (similar to submit_event)
        flash('Submission updated successfully', 'success')
        return redirect(url_for('events.my_submissions'))
    
    return render_template('events/edit_submission.html', submission=submission)


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
            
            # Optionally create event from submission
            # You can add event creation logic here
            
            flash('Submission approved', 'success')
        
        elif action == 'reject':
            EventSubmission.update_status(submission_id, 'rejected', current_user.id, admin_notes)
            flash('Submission rejected', 'success')
        
        return redirect(url_for('events.admin_submissions'))
    
    return render_template('events/admin_review.html', submission=submission)


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
                'created_by': current_user.id
            })
            
            flash('Event created successfully!', 'success')
            return redirect(url_for('events.events_home'))
        
        except Exception as e:
            print(f"Event creation error: {e}")
            flash(f'Error creating event: {str(e)}', 'error')
            return render_template('events/admin_create_event.html', submission=submission, form_data=request.form)
    
    return render_template('events/admin_create_event.html', submission=submission, form_data={})
