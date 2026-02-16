from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from database import execute_query
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from swearwords_filter import swearwords_filter
import os

messaging_bp = Blueprint('messaging', __name__)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav', 'mp4', 'mov', 'webm'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==================== CONTACTS CRUD ====================

@messaging_bp.route('/contacts')
@login_required
def view_contacts():
    """RETRIEVE - View all contacts"""
    user_id = current_user.id

    contacts = execute_query("""
        SELECT c.*,
               u.display_name AS contact_display_name,
               u.username     AS contact_username,
               u.age_group    AS contact_age_group,
               u.profile_picture AS contact_profile_picture
        FROM contacts c
        JOIN users u ON c.contact_user_id = u.id
        WHERE c.user_id = %s
        ORDER BY c.is_favorite DESC, u.display_name ASC
    """, (user_id,), fetch_all=True) or []

    existing_ids = [c['contact_user_id'] for c in contacts]

    if existing_ids:
        ph = ','.join(['%s'] * len(existing_ids))
        available_users = execute_query(
            f"SELECT id, display_name, username, age_group FROM users WHERE id != %s AND id NOT IN ({ph}) ORDER BY display_name",
            (user_id, *existing_ids), fetch_all=True
        ) or []
    else:
        available_users = execute_query(
            "SELECT id, display_name, username, age_group FROM users WHERE id != %s ORDER BY display_name",
            (user_id,), fetch_all=True
        ) or []

    return render_template('messaging/contacts.html', contacts=contacts, available_users=available_users)


@messaging_bp.route('/contacts/add', methods=['POST'])
@login_required
def add_contact():
    """CREATE - Add new contact with validation"""
    user_id = current_user.id
    contact_user_id = request.form.get('contact_user_id')
    nickname = request.form.get('nickname', '').strip()

    if not contact_user_id:
        flash('Please select a user to add', 'error')
        return redirect(url_for('messaging.view_contacts'))

    contact_user = execute_query("SELECT * FROM users WHERE id = %s", (contact_user_id,), fetch_one=True)
    if not contact_user:
        flash('User not found', 'error')
        return redirect(url_for('messaging.view_contacts'))

    if int(contact_user_id) == user_id:
        flash('You cannot add yourself as a contact', 'error')
        return redirect(url_for('messaging.view_contacts'))

    existing = execute_query(
        "SELECT id FROM contacts WHERE user_id = %s AND contact_user_id = %s",
        (user_id, contact_user_id), fetch_one=True
    )
    if existing:
        flash('This user is already in your contacts', 'error')
        return redirect(url_for('messaging.view_contacts'))

    if nickname and (len(nickname) < 2 or len(nickname) > 50):
        flash('Nickname must be between 2 and 50 characters', 'error')
        return redirect(url_for('messaging.view_contacts'))

    execute_query(
        "INSERT INTO contacts (user_id, contact_user_id, nickname) VALUES (%s, %s, %s)",
        (user_id, contact_user_id, nickname if nickname else None), commit=True
    )

    display_name = contact_user.get('display_name') or contact_user.get('username')
    flash(f'Successfully added {display_name} to contacts!', 'success')
    return redirect(url_for('messaging.view_contacts'))


@messaging_bp.route('/contacts/<int:contact_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_contact(contact_id):
    """UPDATE - Edit contact with validation"""
    user_id = current_user.id

    contact = execute_query("""
        SELECT c.*, u.display_name AS contact_display_name, u.username AS contact_username
        FROM contacts c JOIN users u ON c.contact_user_id = u.id
        WHERE c.id = %s AND c.user_id = %s
    """, (contact_id, user_id), fetch_one=True)

    if not contact:
        flash('Contact not found', 'error')
        return redirect(url_for('messaging.view_contacts'))

    if request.method == 'POST':
        nickname = request.form.get('nickname', '').strip()
        is_favorite = request.form.get('is_favorite') == 'on'

        if nickname and (len(nickname) < 2 or len(nickname) > 50):
            flash('Nickname must be between 2 and 50 characters', 'error')
            return render_template('messaging/edit_contact.html', contact=contact)

        execute_query(
            "UPDATE contacts SET nickname = %s, is_favorite = %s WHERE id = %s",
            (nickname if nickname else None, is_favorite, contact_id), commit=True
        )
        flash('Contact updated successfully!', 'success')
        return redirect(url_for('messaging.view_contacts'))

    return render_template('messaging/edit_contact.html', contact=contact)


@messaging_bp.route('/contacts/<int:contact_id>/delete', methods=['POST'])
@login_required
def delete_contact(contact_id):
    """DELETE - Remove contact"""
    user_id = current_user.id

    contact = execute_query("""
        SELECT c.*, u.display_name AS contact_display_name
        FROM contacts c JOIN users u ON c.contact_user_id = u.id
        WHERE c.id = %s AND c.user_id = %s
    """, (contact_id, user_id), fetch_one=True)

    if not contact:
        flash('Contact not found', 'error')
        return redirect(url_for('messaging.view_contacts'))

    execute_query("DELETE FROM contacts WHERE id = %s", (contact_id,), commit=True)
    flash(f'Successfully removed {contact["contact_display_name"]} from contacts', 'success')
    return redirect(url_for('messaging.view_contacts'))


# ==================== GROUPS CRUD ====================

@messaging_bp.route('/groups')
@login_required
def view_groups():
    """RETRIEVE - View all groups user is member of"""
    user_id = current_user.id

    groups = execute_query("""
        SELECT g.*,
               (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) AS member_count
        FROM `groups` g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = %s AND g.is_active = TRUE
        ORDER BY g.name
    """, (user_id,), fetch_all=True) or []

    return render_template('messaging/groups.html', groups=groups)


@messaging_bp.route('/groups/create', methods=['GET', 'POST'])
@login_required
def create_group():
    """CREATE - Create new group with validation"""
    user_id = current_user.id

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        member_ids = request.form.getlist('members')

        contacts = execute_query("""
            SELECT c.*, u.display_name AS contact_display_name, u.username AS contact_username
            FROM contacts c JOIN users u ON c.contact_user_id = u.id
            WHERE c.user_id = %s
        """, (user_id,), fetch_all=True) or []

        if not name:
            flash('Group name is required', 'error')
            return render_template('messaging/create_group.html', contacts=contacts)

        if len(name) < 3 or len(name) > 100:
            flash('Group name must be between 3 and 100 characters', 'error')
            return render_template('messaging/create_group.html', contacts=contacts)

        if description and len(description) > 500:
            flash('Description must not exceed 500 characters', 'error')
            return render_template('messaging/create_group.html', contacts=contacts)

        if not member_ids:
            flash('Please select at least one member for the group', 'error')
            return render_template('messaging/create_group.html', contacts=contacts)

        ph = ','.join(['%s'] * len(member_ids))
        members = execute_query(
            f"SELECT id FROM users WHERE id IN ({ph})",
            tuple(member_ids), fetch_all=True
        ) or []
        if len(members) != len(member_ids):
            flash('Some selected users do not exist', 'error')
            return render_template('messaging/create_group.html', contacts=contacts)

        group_id = execute_query(
            "INSERT INTO `groups` (name, description, created_by) VALUES (%s, %s, %s)",
            (name, description if description else None, user_id), commit=True
        )

        execute_query(
            "INSERT INTO group_members (group_id, user_id, is_admin) VALUES (%s, %s, TRUE)",
            (group_id, user_id), commit=True
        )

        for mid in member_ids:
            execute_query(
                "INSERT INTO group_members (group_id, user_id, is_admin) VALUES (%s, %s, FALSE)",
                (group_id, int(mid)), commit=True
            )

        flash(f'Group "{name}" created successfully!', 'success')
        return redirect(url_for('messaging.view_groups'))

    contacts = execute_query("""
        SELECT c.*, u.display_name AS contact_display_name, u.username AS contact_username
        FROM contacts c JOIN users u ON c.contact_user_id = u.id
        WHERE c.user_id = %s
    """, (user_id,), fetch_all=True) or []

    return render_template('messaging/create_group.html', contacts=contacts)


@messaging_bp.route('/groups/<int:group_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_group(group_id):
    """UPDATE - Edit group with validation"""
    user_id = current_user.id

    group = execute_query("SELECT * FROM `groups` WHERE id = %s AND is_active = TRUE", (group_id,), fetch_one=True)
    if not group:
        flash('Group not found', 'error')
        return redirect(url_for('messaging.view_groups'))

    membership = execute_query(
        "SELECT * FROM group_members WHERE group_id = %s AND user_id = %s AND is_admin = TRUE",
        (group_id, user_id), fetch_one=True
    )
    if not membership:
        flash('Only group admins can edit group details', 'error')
        return redirect(url_for('messaging.view_groups'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()

        if not name:
            flash('Group name is required', 'error')
            return render_template('messaging/edit_group.html', group=group)
        if len(name) < 3 or len(name) > 100:
            flash('Group name must be between 3 and 100 characters', 'error')
            return render_template('messaging/edit_group.html', group=group)
        if description and len(description) > 500:
            flash('Description must not exceed 500 characters', 'error')
            return render_template('messaging/edit_group.html', group=group)

        execute_query(
            "UPDATE `groups` SET name = %s, description = %s WHERE id = %s",
            (name, description if description else None, group_id), commit=True
        )
        flash('Group updated successfully!', 'success')
        return redirect(url_for('messaging.chat_group', group_id=group_id))

    return render_template('messaging/edit_group.html', group=group)


@messaging_bp.route('/groups/<int:group_id>/delete', methods=['POST'])
@login_required
def delete_group(group_id):
    """DELETE - Soft delete group"""
    user_id = current_user.id

    group = execute_query("SELECT * FROM `groups` WHERE id = %s", (group_id,), fetch_one=True)
    if not group:
        flash('Group not found', 'error')
        return redirect(url_for('messaging.view_groups'))

    if group['created_by'] != user_id:
        flash('Only the group creator can delete this group', 'error')
        return redirect(url_for('messaging.view_groups'))

    execute_query("UPDATE `groups` SET is_active = FALSE WHERE id = %s", (group_id,), commit=True)
    flash(f'Group "{group["name"]}" has been deleted', 'success')
    return redirect(url_for('messaging.view_groups'))


# ==================== MESSAGES CRUD ====================

@messaging_bp.route('/chat/<int:contact_id>')
@login_required
def chat_direct(contact_id):
    """RETRIEVE - View direct messages with a contact"""
    user_id = current_user.id

    contact_user = execute_query("SELECT * FROM users WHERE id = %s", (contact_id,), fetch_one=True)
    if not contact_user:
        flash('User not found', 'error')
        return redirect(url_for('messaging.view_contacts'))

    messages = execute_query("""
        SELECT m.*, u.display_name AS sender_display_name
        FROM messages m JOIN users u ON m.sender_id = u.id
        WHERE ((m.sender_id = %s AND m.receiver_id = %s)
            OR (m.sender_id = %s AND m.receiver_id = %s))
            AND m.is_deleted = FALSE
        ORDER BY m.created_at ASC
    """, (user_id, contact_id, contact_id, user_id), fetch_all=True) or []

    execute_query(
        "UPDATE messages SET is_read = TRUE WHERE sender_id = %s AND receiver_id = %s AND is_read = FALSE",
        (contact_id, user_id), commit=True
    )

    return render_template('messaging/chat_direct.html', contact=contact_user, messages=messages)


@messaging_bp.route('/chat/group/<int:group_id>')
@login_required
def chat_group(group_id):
    """RETRIEVE - View group messages"""
    user_id = current_user.id

    group = execute_query("SELECT * FROM `groups` WHERE id = %s AND is_active = TRUE", (group_id,), fetch_one=True)
    if not group:
        flash('Group not found', 'error')
        return redirect(url_for('messaging.view_groups'))

    membership = execute_query(
        "SELECT * FROM group_members WHERE group_id = %s AND user_id = %s",
        (group_id, user_id), fetch_one=True
    )
    if not membership:
        flash('You are not a member of this group', 'error')
        return redirect(url_for('messaging.view_groups'))

    mc = execute_query("SELECT COUNT(*) AS cnt FROM group_members WHERE group_id = %s", (group_id,), fetch_one=True)
    group['member_count'] = mc['cnt'] if mc else 0

    messages = execute_query("""
        SELECT m.*, u.display_name AS sender_display_name
        FROM messages m JOIN users u ON m.sender_id = u.id
        WHERE m.group_id = %s AND m.is_deleted = FALSE
        ORDER BY m.created_at ASC
    """, (group_id,), fetch_all=True) or []

    return render_template('messaging/chat_group.html',
                           group=group, messages=messages,
                           is_admin=membership['is_admin'] if membership else False)


@messaging_bp.route('/message/send', methods=['POST'])
@login_required
def send_message():
    """CREATE - Send message with validation"""
    user_id = current_user.id
    receiver_id = request.form.get('receiver_id')
    group_id = request.form.get('group_id')
    content = request.form.get('content', '').strip()
    message_type = request.form.get('message_type', 'text')

    if not receiver_id and not group_id:
        flash('Invalid message recipient', 'error')
        return redirect(url_for('messaging.view_contacts'))

    if receiver_id and group_id:
        flash('Message cannot be sent to both user and group', 'error')
        return redirect(url_for('messaging.view_contacts'))

    if message_type == 'text' and not content:
        flash('Message content cannot be empty', 'error')
        if receiver_id:
            return redirect(url_for('messaging.chat_direct', contact_id=receiver_id))
        return redirect(url_for('messaging.chat_group', group_id=group_id))

    if message_type == 'text' and len(content) > 5000:
        flash('Message is too long (maximum 5000 characters)', 'error')
        if receiver_id:
            return redirect(url_for('messaging.chat_direct', contact_id=receiver_id))
        return redirect(url_for('messaging.chat_group', group_id=group_id))

    if message_type == 'text':
        has_swear, matched = swearwords_filter.contains_swearwords(content)
        if has_swear:
            flash(swearwords_filter.get_error_message(matched), 'error')
            if receiver_id:
                return redirect(url_for('messaging.chat_direct', contact_id=receiver_id))
            return redirect(url_for('messaging.chat_group', group_id=group_id))

    file_path = None
    if message_type in ['image', 'voice', 'video']:
        if 'file' not in request.files:
            flash(f'No {message_type} file uploaded', 'error')
            if receiver_id:
                return redirect(url_for('messaging.chat_direct', contact_id=receiver_id))
            return redirect(url_for('messaging.chat_group', group_id=group_id))

        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            if receiver_id:
                return redirect(url_for('messaging.chat_direct', contact_id=receiver_id))
            return redirect(url_for('messaging.chat_group', group_id=group_id))

        if file and allowed_file(file.filename):
            filename = secure_filename(f"{user_id}_{datetime.now().timestamp()}_{file.filename}")
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            content = f"{message_type.capitalize()} file"
        else:
            flash('Invalid file type', 'error')
            if receiver_id:
                return redirect(url_for('messaging.chat_direct', contact_id=receiver_id))
            return redirect(url_for('messaging.chat_group', group_id=group_id))

    if receiver_id:
        receiver = execute_query("SELECT id FROM users WHERE id = %s", (receiver_id,), fetch_one=True)
        if not receiver:
            flash('Recipient not found', 'error')
            return redirect(url_for('messaging.view_contacts'))

    if group_id:
        mem = execute_query(
            "SELECT id FROM group_members WHERE group_id = %s AND user_id = %s",
            (group_id, user_id), fetch_one=True
        )
        if not mem:
            flash('You are not a member of this group', 'error')
            return redirect(url_for('messaging.view_groups'))

    message_id = execute_query("""
        INSERT INTO messages (sender_id, receiver_id, group_id, message_type, content, file_path)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        user_id,
        int(receiver_id) if receiver_id else None,
        int(group_id) if group_id else None,
        message_type, content, file_path
    ), commit=True)

    # Emit realtime update for media messages sent through HTTP upload path.
    socketio = current_app.extensions.get('socketio')
    if socketio:
        sender = execute_query(
            "SELECT display_name, username FROM users WHERE id = %s",
            (user_id,), fetch_one=True
        )
        sender_name = (sender['display_name'] or sender['username']) if sender else 'Unknown'
        timestamp = (datetime.utcnow() + timedelta(hours=8)).strftime('%I:%M %p')
        file_url = None
        if file_path:
            file_url = url_for(
                'static',
                filename=file_path.replace('static/', '').replace('\\', '/')
            )

        message_data = {
            'id': message_id,
            'sender_id': user_id,
            'receiver_id': int(receiver_id) if receiver_id else None,
            'group_id': int(group_id) if group_id else None,
            'message': content,
            'message_type': message_type,
            'timestamp': timestamp,
            'sender_display_name': sender_name,
            'is_read': False,
            'file_path': file_url
        }

        if receiver_id:
            socketio.emit('new_message', message_data, room=f'user_{user_id}')
            socketio.emit('new_message', message_data, room=f'user_{int(receiver_id)}')
        elif group_id:
            members = execute_query(
                "SELECT user_id FROM group_members WHERE group_id = %s",
                (int(group_id),), fetch_all=True
            ) or []
            for member in members:
                socketio.emit('new_message', message_data, room=f'user_{member["user_id"]}')


    if receiver_id:
        return redirect(url_for('messaging.chat_direct', contact_id=receiver_id))
    return redirect(url_for('messaging.chat_group', group_id=group_id))


@messaging_bp.route('/message/<int:message_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_message(message_id):
    """UPDATE - Edit message with validation"""
    user_id = current_user.id

    message = execute_query("SELECT * FROM messages WHERE id = %s AND is_deleted = FALSE", (message_id,), fetch_one=True)
    if not message:
        flash('Message not found', 'error')
        return redirect(url_for('messaging.view_contacts'))
    if message['sender_id'] != user_id:
        flash('You can only edit your own messages', 'error')
        return redirect(url_for('messaging.view_contacts'))
    if message['message_type'] != 'text':
        flash('You can only edit text messages', 'error')
        return redirect(url_for('messaging.view_contacts'))

    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        if not content:
            flash('Message content cannot be empty', 'error')
            return render_template('messaging/edit_message.html', message=message)
        if len(content) > 5000:
            flash('Message is too long (maximum 5000 characters)', 'error')
            return render_template('messaging/edit_message.html', message=message)

        has_swear, matched = swearwords_filter.contains_swearwords(content)
        if has_swear:
            flash(swearwords_filter.get_error_message(matched), 'error')
            return render_template('messaging/edit_message.html', message=message)

        execute_query(
            "UPDATE messages SET content = %s, updated_at = %s WHERE id = %s",
            (content, datetime.utcnow(), message_id), commit=True
        )
        flash('Message updated successfully!', 'success')

        if message['receiver_id']:
            return redirect(url_for('messaging.chat_direct', contact_id=message['receiver_id']))
        return redirect(url_for('messaging.chat_group', group_id=message['group_id']))

    return render_template('messaging/edit_message.html', message=message)


@messaging_bp.route('/message/<int:message_id>/delete', methods=['POST'])
@login_required
def delete_message(message_id):
    """DELETE - Soft delete message"""
    user_id = current_user.id

    message = execute_query("SELECT * FROM messages WHERE id = %s", (message_id,), fetch_one=True)
    if not message:
        flash('Message not found', 'error')
        return redirect(url_for('messaging.view_contacts'))
    if message['sender_id'] != user_id:
        flash('You can only delete your own messages', 'error')
        return redirect(url_for('messaging.view_contacts'))

    execute_query("UPDATE messages SET is_deleted = TRUE WHERE id = %s", (message_id,), commit=True)
    socketio = current_app.extensions.get('socketio')
    socketio = current_app.extensions.get('socketio')
    if socketio:
        payload = {'message_id': message_id}
        if message['receiver_id']:
            socketio.emit('message_deleted', payload, room=f'user_{user_id}')
            socketio.emit('message_deleted', payload, room=f'user_{int(message["receiver_id"])}')
        elif message['group_id']:
            members = execute_query(
                "SELECT user_id FROM group_members WHERE group_id = %s",
                (message['group_id'],), fetch_all=True
            ) or []
            for member in members:
                socketio.emit('message_deleted', payload, room=f'user_{member["user_id"]}')

    flash('Message deleted successfully!', 'success')

    if message['receiver_id']:
        return redirect(url_for('messaging.chat_direct', contact_id=message['receiver_id']))
    return redirect(url_for('messaging.chat_group', group_id=message['group_id']))
