from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from flask import current_app
from database import execute_query
from swearwords_filter import swearwords_filter
from datetime import datetime, timedelta

# Store online users: {user_id: True}
online_users = {}


def register_socketio_events(socketio, app):

    @socketio.on('connect')
    def handle_connect():
        if current_user.is_authenticated:
            online_users[current_user.id] = True
            join_room(f'user_{current_user.id}')
            emit('user_status', {
                'user_id': current_user.id,
                'status': 'online'
            }, broadcast=True)

    @socketio.on('disconnect')
    def handle_disconnect():
        if current_user.is_authenticated:
            online_users.pop(current_user.id, None)
            leave_room(f'user_{current_user.id}')
            emit('user_status', {
                'user_id': current_user.id,
                'status': 'offline'
            }, broadcast=True)

    @socketio.on('send_message')
    def handle_send_message(data):
        if not current_user.is_authenticated:
            emit('message_error', {'message': 'Not logged in'})
            return

        user_id = current_user.id
        receiver_id = data.get('receiver_id')
        group_id = data.get('group_id')
        content = data.get('message', '').strip()
        message_type = data.get('message_type', 'text')

        if not content:
            emit('message_error', {'message': 'Message cannot be empty'})
            return

        if len(content) > 5000:
            emit('message_error', {'message': 'Message too long (max 5000 characters)'})
            return

        # Profanity filter
        if message_type == 'text':
            has_swear, matched = swearwords_filter.contains_swearwords(content)
            if has_swear:
                emit('message_error', {'message': swearwords_filter.get_error_message(matched)})
                return

        with app.app_context():
            # Save to database
            msg_id = execute_query("""
                INSERT INTO messages (sender_id, receiver_id, group_id, message_type, content)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                user_id,
                int(receiver_id) if receiver_id else None,
                int(group_id) if group_id else None,
                message_type,
                content
            ), commit=True)

            # Format timestamp (UTC+8)
            now = datetime.utcnow() + timedelta(hours=8)
            timestamp = now.strftime('%I:%M %p')

            sender = execute_query(
                "SELECT display_name, username FROM users WHERE id = %s",
                (user_id,), fetch_one=True
            )
            sender_name = (sender['display_name'] or sender['username']) if sender else 'Unknown'

        message_data = {
            'id': msg_id,
            'sender_id': user_id,
            'receiver_id': int(receiver_id) if receiver_id else None,
            'group_id': int(group_id) if group_id else None,
            'message': content,
            'message_type': message_type,
            'timestamp': timestamp,
            'sender_display_name': sender_name,
            'is_read': False
        }

        if receiver_id:
            # Direct message: send to both sender and receiver rooms
            emit('new_message', message_data, room=f'user_{user_id}')
            emit('new_message', message_data, room=f'user_{int(receiver_id)}')
        elif group_id:
            # Group message: send to all group members
            with app.app_context():
                members = execute_query(
                    "SELECT user_id FROM group_members WHERE group_id = %s",
                    (int(group_id),), fetch_all=True
                ) or []
            for member in members:
                emit('new_message', message_data, room=f'user_{member["user_id"]}')

    @socketio.on('typing')
    def handle_typing(data):
        if not current_user.is_authenticated:
            return
        receiver_id = data.get('receiver_id')
        if receiver_id:
            emit('typing', {'sender_id': current_user.id}, room=f'user_{int(receiver_id)}')

    @socketio.on('stop_typing')
    def handle_stop_typing(data):
        if not current_user.is_authenticated:
            return
        receiver_id = data.get('receiver_id')
        if receiver_id:
            emit('stop_typing', {'sender_id': current_user.id}, room=f'user_{int(receiver_id)}')

    @socketio.on('message_read')
    def handle_message_read(data):
        if not current_user.is_authenticated:
            return
        message_id = data.get('message_id')
        sender_id = data.get('sender_id')

        if message_id:
            with app.app_context():
                execute_query(
                    "UPDATE messages SET is_read = TRUE WHERE id = %s",
                    (message_id,), commit=True
                )
            if sender_id:
                emit('message_read', {
                    'message_id': message_id
                }, room=f'user_{int(sender_id)}')

    @socketio.on('check_online')
    def handle_check_online(data):
        user_id = data.get('user_id')
        if user_id:
            is_online = int(user_id) in online_users
            emit('user_status', {
                'user_id': int(user_id),
                'status': 'online' if is_online else 'offline'
            })