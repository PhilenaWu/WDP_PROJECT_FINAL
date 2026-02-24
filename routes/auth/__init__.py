from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from flask_login import login_user, logout_user, current_user, login_required
from models import User
from datetime import datetime, timedelta
import re
import regex
import secrets
import smtplib
import requests
from email.message import EmailMessage
from urllib.parse import urlencode
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

auth_bp = Blueprint('auth', __name__)

GMAIL_EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@gmail\.com$'
NAME_ONLY_PATTERN = r"^[\p{L} .'-]+$"
PASSWORD_PATTERN = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$'
SIGNUP_DRAFT_KEY = 'signup_draft'
GOOGLE_OAUTH_STATE_KEY = 'google_oauth_state'

GOOGLE_TRANSLATE_LANGUAGES = [
    ('af', 'Afrikaans'),
    ('sq', 'Albanian'),
    ('am', 'Amharic'),
    ('ar', 'Arabic'),
    ('hy', 'Armenian'),
    ('as', 'Assamese'),
    ('ay', 'Aymara'),
    ('az', 'Azerbaijani'),
    ('bm', 'Bambara'),
    ('eu', 'Basque'),
    ('be', 'Belarusian'),
    ('bn', 'Bengali'),
    ('bho', 'Bhojpuri'),
    ('bs', 'Bosnian'),
    ('bg', 'Bulgarian'),
    ('ca', 'Catalan'),
    ('ceb', 'Cebuano'),
    ('zh-CN', 'Chinese (Simplified)'),
    ('zh-TW', 'Chinese (Traditional)'),
    ('co', 'Corsican'),
    ('hr', 'Croatian'),
    ('cs', 'Czech'),
    ('da', 'Danish'),
    ('dv', 'Dhivehi'),
    ('doi', 'Dogri'),
    ('nl', 'Dutch'),
    ('en', 'English'),
    ('eo', 'Esperanto'),
    ('et', 'Estonian'),
    ('ee', 'Ewe'),
    ('fil', 'Filipino'),
    ('fi', 'Finnish'),
    ('fr', 'French'),
    ('fy', 'Frisian'),
    ('gl', 'Galician'),
    ('ka', 'Georgian'),
    ('de', 'German'),
    ('el', 'Greek'),
    ('gn', 'Guarani'),
    ('gu', 'Gujarati'),
    ('ht', 'Haitian Creole'),
    ('ha', 'Hausa'),
    ('haw', 'Hawaiian'),
    ('he', 'Hebrew'),
    ('hi', 'Hindi'),
    ('hmn', 'Hmong'),
    ('hu', 'Hungarian'),
    ('is', 'Icelandic'),
    ('ig', 'Igbo'),
    ('ilo', 'Ilocano'),
    ('id', 'Indonesian'),
    ('ga', 'Irish'),
    ('it', 'Italian'),
    ('ja', 'Japanese'),
    ('jv', 'Javanese'),
    ('kn', 'Kannada'),
    ('kk', 'Kazakh'),
    ('km', 'Khmer'),
    ('rw', 'Kinyarwanda'),
    ('gom', 'Konkani'),
    ('ko', 'Korean'),
    ('kri', 'Krio'),
    ('ku', 'Kurdish (Kurmanji)'),
    ('ckb', 'Kurdish (Sorani)'),
    ('ky', 'Kyrgyz'),
    ('lo', 'Lao'),
    ('la', 'Latin'),
    ('lv', 'Latvian'),
    ('ln', 'Lingala'),
    ('lt', 'Lithuanian'),
    ('lg', 'Luganda'),
    ('lb', 'Luxembourgish'),
    ('mk', 'Macedonian'),
    ('mai', 'Maithili'),
    ('mg', 'Malagasy'),
    ('ms', 'Malay'),
    ('ml', 'Malayalam'),
    ('mt', 'Maltese'),
    ('mi', 'Maori'),
    ('mr', 'Marathi'),
    ('mni-Mtei', 'Meiteilon (Manipuri)'),
    ('lus', 'Mizo'),
    ('mn', 'Mongolian'),
    ('my', 'Myanmar (Burmese)'),
    ('ne', 'Nepali'),
    ('no', 'Norwegian'),
    ('or', 'Odia (Oriya)'),
    ('om', 'Oromo'),
    ('ps', 'Pashto'),
    ('fa', 'Persian'),
    ('pl', 'Polish'),
    ('pt', 'Portuguese'),
    ('pa', 'Punjabi'),
    ('qu', 'Quechua'),
    ('ro', 'Romanian'),
    ('ru', 'Russian'),
    ('sm', 'Samoan'),
    ('sa', 'Sanskrit'),
    ('gd', 'Scots Gaelic'),
    ('nso', 'Sepedi'),
    ('sr', 'Serbian'),
    ('st', 'Sesotho'),
    ('sn', 'Shona'),
    ('sd', 'Sindhi'),
    ('si', 'Sinhala'),
    ('sk', 'Slovak'),
    ('sl', 'Slovenian'),
    ('so', 'Somali'),
    ('es', 'Spanish'),
    ('su', 'Sundanese'),
    ('sw', 'Swahili'),
    ('sv', 'Swedish'),
    ('tg', 'Tajik'),
    ('ta', 'Tamil'),
    ('tt', 'Tatar'),
    ('te', 'Telugu'),
    ('th', 'Thai'),
    ('ti', 'Tigrinya'),
    ('ts', 'Tsonga'),
    ('tr', 'Turkish'),
    ('tk', 'Turkmen'),
    ('ak', 'Twi'),
    ('uk', 'Ukrainian'),
    ('ur', 'Urdu'),
    ('ug', 'Uyghur'),
    ('uz', 'Uzbek'),
    ('vi', 'Vietnamese'),
    ('cy', 'Welsh'),
    ('xh', 'Xhosa'),
    ('yi', 'Yiddish'),
    ('yo', 'Yoruba'),
    ('zu', 'Zulu'),
]

GOOGLE_TRANSLATE_LANGUAGE_CODES = {
    code.lower(): code for code, _ in GOOGLE_TRANSLATE_LANGUAGES
}

GOOGLE_TRANSLATE_LANGUAGE_ALIASES = {
    'zh': 'zh-CN',
    'zh-cn': 'zh-CN',
    'zh-hans': 'zh-CN',
    'zh-tw': 'zh-TW',
    'zh-hant': 'zh-TW',
    'iw': 'he',
}

# Gmail's SMTP server with TLS encryption on port 587.
def is_valid_gmail(email):
    normalized = (email or '').strip().lower()
    return bool(re.match(GMAIL_EMAIL_PATTERN, normalized))


def is_valid_name(name):
    normalized = (name or '').strip()
    return bool(regex.match(NAME_ONLY_PATTERN, normalized))


def is_valid_password(password):
    normalized = password or ''
    return bool(re.match(PASSWORD_PATTERN, normalized))


def _get_signup_draft():
    return dict(session.get(SIGNUP_DRAFT_KEY) or {})


def _set_signup_draft(data):
    session[SIGNUP_DRAFT_KEY] = data
    session.modified = True


def _clear_signup_draft():
    session.pop(SIGNUP_DRAFT_KEY, None)


def _signup_has_account_seed(draft):
    if not draft.get('username') or not draft.get('email'):
        return False
    if draft.get('signup_method') == 'google':
        return True
    return bool(draft.get('password'))


def _generate_unique_username(email, preferred_username=None):
    base_raw = preferred_username or (email or '').split('@')[0]
    base = re.sub(r'[^A-Za-z0-9_]', '', base_raw or '')
    if not base:
        base = 'user'
    if not re.match(r'^[A-Za-z]', base):
        base = f'u{base}'
    base = base[:20]
    if len(base) < 3:
        base = (base + 'user')[:3]

    candidate = base
    suffix = 1
    while User.get_by_username(candidate):
        suffix_str = str(suffix)
        max_base_len = 20 - len(suffix_str)
        candidate = f"{base[:max_base_len]}{suffix_str}"
        suffix += 1
    return candidate


def _google_oauth_settings():
    client_id = (current_app.config.get('GOOGLE_OAUTH_CLIENT_ID') or '').strip()
    client_secret = (current_app.config.get('GOOGLE_OAUTH_CLIENT_SECRET') or '').strip()
    redirect_uri = (current_app.config.get('GOOGLE_OAUTH_REDIRECT_URI') or '').strip()

    if not redirect_uri:
        redirect_uri = url_for('auth.signup_google_callback', _external=True)
    return client_id, client_secret, redirect_uri


def _serialize_selected_interests(selected_slugs):
    cleaned_slugs = [s.strip() for s in (selected_slugs or []) if (s or '').strip()]
    unique_slugs = list(dict.fromkeys(cleaned_slugs))[:3]
    return ','.join(unique_slugs)

#system generates a unique, time-sensitive token and 
#sends a secure reset link to their registered email 
def generate_reset_token(email):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='password-reset-salt')


def verify_reset_token(token, max_age):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        return serializer.loads(token, salt='password-reset-salt', max_age=max_age)
    except (SignatureExpired, BadSignature):
        return None


def send_password_reset_email(recipient_email, reset_link):
    mail_username = current_app.config.get('MAIL_USERNAME')
    mail_password = (current_app.config.get('MAIL_APP_PASSWORD') or '').replace(' ', '')
    mail_server = current_app.config.get('MAIL_SERVER')
    mail_port = current_app.config.get('MAIL_PORT')
    use_tls = current_app.config.get('MAIL_USE_TLS', True)

    if not mail_username or not mail_password:
        raise ValueError('MAIL_USERNAME and MAIL_APP_PASSWORD must be configured.')

    msg = EmailMessage()
    msg['Subject'] = 'Genlink Password Reset'
    msg['From'] = mail_username
    msg['To'] = recipient_email
    msg.set_content(
        f"""Hello,

We received a request to reset your Genlink password.

Click the link below to set a new password:
{reset_link}

This link expires in 30 minutes.

If you did not request this, you can ignore this email.
"""
    )

    with smtplib.SMTP(mail_server, mail_port, timeout=30) as server:
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()

        try:
            server.login(mail_username, mail_password)
            server.send_message(msg)
            return
        except smtplib.SMTPNotSupportedError:
            pass

    if str(mail_server).strip().lower() == 'smtp.gmail.com':
        with smtplib.SMTP_SSL(mail_server, 465, timeout=30) as ssl_server:
            ssl_server.ehlo()
            ssl_server.login(mail_username, mail_password)
            ssl_server.send_message(msg)
        return

    raise ValueError('SMTP server does not advertise AUTH. Check MAIL_SERVER/MAIL_PORT or enable SMTP AUTH on the provider.')


@auth_bp.route('/feedback', methods=['GET', 'POST'])
@login_required
def feedback():
    from database import execute_query

    if request.method == 'POST':
        from deep_translator import GoogleTranslator
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        feedback_type = request.form.get('feedback_type', '').strip()
        feedback_text = request.form.get('feedback_text', '').strip()

        # Translate Chinese input to English
        def translate_if_chinese(text):
            if text:
                try:
                    # If contains Chinese characters, translate
                    if any('\u4e00' <= c <= '\u9fff' for c in text):
                        return GoogleTranslator(source='auto', target='en').translate(text)
                except Exception:
                    pass
            return text

        full_name = translate_if_chinese(full_name)
        feedback_type = translate_if_chinese(feedback_type)
        feedback_text = translate_if_chinese(feedback_text)

        if not full_name or not email or not feedback_type or not feedback_text:
            return render_template(
                'auth/feedbackform.html',
                error='Please fill in all fields.',
                form_data=request.form,
                editing=False,
                action_url=url_for('auth.feedback'),
            )

        if not is_valid_name(full_name):
            return render_template(
                'auth/feedbackform.html',
                error='Full name can only contain letters and spaces.',
                form_data=request.form,
                editing=False,
                action_url=url_for('auth.feedback'),
            )

        if not is_valid_gmail(email):
            return render_template(
                'auth/feedbackform.html',
                error='Please enter a valid Gmail address ending with @gmail.com.',
                form_data=request.form,
                editing=False,
                action_url=url_for('auth.feedback'),
            )

        if feedback_type not in {'Positive', 'Negative'}:
            return render_template(
                'auth/feedbackform.html',
                error='Please select a valid feedback type.',
                form_data=request.form,
                editing=False,
                action_url=url_for('auth.feedback'),
            )

        execute_query(
            """
            INSERT INTO feedback (user_id, full_name, email, feedback_type, feedback_text)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (current_user.id, full_name, email, feedback_type, feedback_text),
            commit=True
        )

        flash('Thank you! Your feedback has been submitted.', 'success')
        return redirect(url_for('main.home'))

    return render_template(
        'auth/feedbackform.html',
        form_data={},
        editing=False,
        action_url=url_for('auth.feedback')
    )


@auth_bp.route('/feedback/history', methods=['GET'])
@login_required
def feedback_history():
    from database import execute_query

    feedback_entries = execute_query(
        """
        SELECT id, full_name, email, feedback_type, feedback_text
        FROM feedback
        WHERE user_id = %s
        ORDER BY id DESC
        """,
        (current_user.id,),
        fetch_all=True,
    ) or []

    return render_template('auth/feedback_history.html', feedback_entries=feedback_entries)


@auth_bp.route('/feedback/<int:feedback_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_feedback(feedback_id):
    from database import execute_query

    feedback_entry = execute_query(
        """
        SELECT id, full_name, email, feedback_type, feedback_text
        FROM feedback
        WHERE id = %s AND user_id = %s
        """,
        (feedback_id, current_user.id),
        fetch_one=True,
    )

    if not feedback_entry:
        flash('Feedback entry not found.', 'error')
        return redirect(url_for('auth.feedback_history'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        feedback_type = request.form.get('feedback_type', '').strip()
        feedback_text = request.form.get('feedback_text', '').strip()

        if not full_name or not email or not feedback_type or not feedback_text:
            return render_template(
                'auth/feedbackform.html',
                error='Please fill in all fields.',
                form_data=request.form,
                editing=True,
                action_url=url_for('auth.edit_feedback', feedback_id=feedback_id),
                feedback_id=feedback_id,
            )

        if not is_valid_name(full_name):
            return render_template(
                'auth/feedbackform.html',
                error='Full name can only contain letters and spaces.',
                form_data=request.form,
                editing=True,
                action_url=url_for('auth.edit_feedback', feedback_id=feedback_id),
                feedback_id=feedback_id,
            )

        if not is_valid_gmail(email):
            return render_template(
                'auth/feedbackform.html',
                error='Please enter a valid Gmail address ending with @gmail.com.',
                form_data=request.form,
                editing=True,
                action_url=url_for('auth.edit_feedback', feedback_id=feedback_id),
                feedback_id=feedback_id,
            )

        if feedback_type not in {'Positive', 'Negative'}:
            return render_template(
                'auth/feedbackform.html',
                error='Please select a valid feedback type.',
                form_data=request.form,
                editing=True,
                action_url=url_for('auth.edit_feedback', feedback_id=feedback_id),
                feedback_id=feedback_id,
            )

        execute_query(
            """
            UPDATE feedback
            SET full_name = %s, email = %s, feedback_type = %s, feedback_text = %s
            WHERE id = %s AND user_id = %s
            """,
            (full_name, email, feedback_type, feedback_text, feedback_id, current_user.id),
            commit=True,
        )

        flash('Feedback updated successfully.', 'success')
        return redirect(url_for('auth.feedback_history'))

    return render_template(
        'auth/feedbackform.html',
        form_data=feedback_entry,
        editing=True,
        action_url=url_for('auth.edit_feedback', feedback_id=feedback_id),
        feedback_id=feedback_id,
    )


@auth_bp.route('/feedback/<int:feedback_id>/delete', methods=['POST'])
@login_required
def delete_feedback(feedback_id):
    from database import execute_query

    feedback_entry = execute_query(
        "SELECT id FROM feedback WHERE id = %s AND user_id = %s",
        (feedback_id, current_user.id),
        fetch_one=True,
    )

    if not feedback_entry:
        flash('Feedback entry not found.', 'error')
        return redirect(url_for('auth.feedback_history'))

    execute_query(
        "DELETE FROM feedback WHERE id = %s AND user_id = %s",
        (feedback_id, current_user.id),
        commit=True,
    )

    flash('Feedback deleted successfully.', 'success')
    return redirect(url_for('auth.feedback_history'))


@auth_bp.route('/feedback/retrieve-email', methods=['GET'])
@login_required
def retrieve_feedback_email():
    return {
        'email': current_user.email or '',
        'first_name': getattr(current_user, 'first_name', '') or '',
        'last_name': getattr(current_user, 'last_name', '') or ''
    }, 200


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            return render_template('auth/forgotpassword.html', error='Please enter your email address.')

        if not is_valid_gmail(email):
            return render_template('auth/forgotpassword.html', error='Please use a valid Gmail address ending with @gmail.com.')

        user = User.get_by_email(email)
        if not user:
            return render_template('auth/forgotpassword.html', error='No account found with that email address.')

        token = generate_reset_token(user.email)
        reset_link = url_for('auth.reset_password', token=token, _external=True)
        try:
            send_password_reset_email(user.email, reset_link)
        except smtplib.SMTPAuthenticationError:
            return render_template(
                'auth/forgotpassword.html',
                error='Gmail login failed. Check MAIL_USERNAME and Gmail app password in config.py.'
            )
        except Exception as e:
            return render_template(
                'auth/forgotpassword.html',
                error=f'Could not send reset email: {str(e)[:180]}'
            )

        flash('A password reset link has been sent to your email.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgotpassword.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    max_age = current_app.config.get('RESET_TOKEN_MAX_AGE_SECONDS', 1800)
    email = verify_reset_token(token, max_age)

    if not email:
        flash('This password reset link is invalid or has expired.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not password or not confirm_password:
            return render_template('auth/resetpassword.html', token=token, error='Please fill in both password fields.')

        if password != confirm_password:
            return render_template('auth/resetpassword.html', token=token, error='Passwords do not match.')

        password_pattern = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,}$'
        if not re.match(password_pattern, password):
            return render_template(
                'auth/resetpassword.html',
                token=token,
                error='Password must be at least 8 characters and include 1 lowercase, 1 uppercase, 1 number, and 1 special character.'
            )

        from database import execute_query

        existing_user = execute_query(
            'SELECT password_hash FROM users WHERE email = %s',
            (email,),
            fetch_one=True
        )

        if existing_user and existing_user.get('password_hash') == password:
            return render_template(
                'auth/resetpassword.html',
                token=token,
                error='Please enter a new password different from your current one.'
            )

        execute_query(
            'UPDATE users SET password_hash = %s, password_reset_count = password_reset_count + 1 WHERE email = %s',
            (password, email),
            commit=True
        )

        flash('Your password has been reset successfully. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/resetpassword.html', token=token)

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """Signup Step 1: account credentials."""
    draft = _get_signup_draft()

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        user_data = {
            'email': email,
        }

        if not all([email, password, confirm_password]):
            return render_template(
                'auth/signup.html',
                user=user_data,
                error="Email, password and confirm password are required.",
            )

        if not is_valid_gmail(email):
            return render_template(
                'auth/signup.html',
                user=user_data,
                error="Please enter a valid Gmail address ending with @gmail.com.",
            )

        if not is_valid_password(password):
            return render_template(
                'auth/signup.html',
                user=user_data,
                error="Password must be at least 8 characters and include 1 lowercase, 1 uppercase, 1 number, and 1 special character.",
            )

        if password != confirm_password:
            return render_template(
                'auth/signup.html',
                user=user_data,
                error="Passwords do not match.",
            )

        if User.get_by_email(email):
            return render_template(
                'auth/signup.html',
                user=user_data,
                error="Email already registered. Please use a different one.",
            )

        draft.update(
            {
                'email': email,
                'password': password,
                'signup_method': request.form.get('signup_method', 'email'),
            }
        )
        _set_signup_draft(draft)
        return redirect(url_for('auth.signup_step2'))

    if request.args.get('preserve') != '1':
        _clear_signup_draft()
        draft = {}

    return render_template('auth/signup.html', user=draft)


@auth_bp.route('/signup/google', methods=['GET'])
def signup_google():
    client_id, client_secret, redirect_uri = _google_oauth_settings()
    if not client_id or not client_secret:
        flash('Google OAuth is not configured. Add GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in your environment.', 'error')
        return redirect(url_for('auth.signup'))

    state = secrets.token_urlsafe(24)
    session[GOOGLE_OAUTH_STATE_KEY] = state

    query = urlencode(
        {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'offline',
            'prompt': 'select_account',
            'state': state,
        }
    )
    return redirect(f'https://accounts.google.com/o/oauth2/v2/auth?{query}')


@auth_bp.route('/login/google', methods=['GET'])
def login_google():
    return redirect(url_for('auth.signup_google'))


@auth_bp.route('/signup/google/callback', methods=['GET'])
def signup_google_callback():
    state = request.args.get('state', '')
    code = request.args.get('code', '')
    expected_state = session.pop(GOOGLE_OAUTH_STATE_KEY, None)

    if not state or not expected_state or state != expected_state:
        flash('Google sign up failed due to invalid state. Please try again.', 'error')
        return redirect(url_for('auth.signup'))

    if not code:
        flash('Google sign up cancelled or failed. Please try again.', 'error')
        return redirect(url_for('auth.signup'))

    client_id, client_secret, redirect_uri = _google_oauth_settings()

    try:
        token_resp = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            },
            timeout=15,
        )
        token_resp.raise_for_status()
        token_json = token_resp.json()
        access_token = token_json.get('access_token')
        if not access_token:
            raise ValueError('Missing access token from Google.')

        userinfo_resp = requests.get(
            'https://openidconnect.googleapis.com/v1/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=15,
        )
        userinfo_resp.raise_for_status()
        profile = userinfo_resp.json()

        email = (profile.get('email') or '').strip().lower()
        if not email:
            raise ValueError('Google account did not provide an email.')

        if profile.get('email_verified') is False:
            raise ValueError('Google email is not verified. Please verify your Google account email first.')

        if not is_valid_gmail(email):
            raise ValueError('Only Gmail addresses are allowed for this app.')

        existing_user = User.get_by_email(email)
        if existing_user:
            session.pop('failed_attempts', None)
            session.pop('lockout_time', None)
            login_user(existing_user)
            flash('Signed in with Google.', 'success')
            return redirect(url_for('main.home'))

        preferred_username = (profile.get('preferred_username') or '').strip()
        username = _generate_unique_username(email, preferred_username=preferred_username)

        draft = _get_signup_draft()
        draft.update(
            {
                'signup_method': 'google',
                'email': email,
                'username': username,
                'password': '',
                'first_name': (profile.get('given_name') or '').strip(),
                'last_name': (profile.get('family_name') or '').strip(),
                'display_name': (profile.get('name') or '').strip(),
            }
        )
        _set_signup_draft(draft)
        return redirect(url_for('auth.signup_step2'))

    except Exception as exc:
        flash(f'Google sign up failed: {str(exc)[:160]}', 'error')
        return redirect(url_for('auth.signup'))


@auth_bp.route('/signup/step2', methods=['GET', 'POST'])
def signup_step2():
    """Signup Step 2: profile details."""
    draft = _get_signup_draft()
    if not draft.get('email'):
        return redirect(url_for('auth.signup'))

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        username = request.form.get('username', '').strip()
        display_name = request.form.get('display_name', '').strip()
        phone = request.form.get('phone', '').strip()
        birthday_str = request.form.get('birthday', '').strip()

        user_data = {
            'first_name': first_name,
            'last_name': last_name,
            'username': username,
            'display_name': display_name,
            'phone': phone,
            'birthday': birthday_str,
        }

        if not all([first_name, last_name, username, display_name, birthday_str]):
            return render_template(
                'auth/signup_step2.html',
                user=user_data,
                error='All required fields must be filled.',
            )

        if not is_valid_name(first_name) or not is_valid_name(last_name):
            return render_template(
                'auth/signup_step2.html',
                user=user_data,
                error='First and last name can only contain letters and spaces.',
            )

        if not re.match(r'^[A-Za-z][A-Za-z0-9_]{2,19}$', username):
            return render_template(
                'auth/signup_step2.html',
                user=user_data,
                error='Username must be 3-20 characters, start with a letter, and contain only letters, numbers, or underscore.',
            )

        existing_user = User.get_by_username(username)
        if existing_user:
            return render_template(
                'auth/signup_step2.html',
                user=user_data,
                error='Username already taken. Please use a different one.',
            )

        if phone and not re.match(r'^\d{8}$', phone):
            return render_template(
                'auth/signup_step2.html',
                user=user_data,
                error='Phone number must be exactly 8 digits.',
            )

        age_category = None
        try:
            birthday = datetime.strptime(birthday_str, '%Y-%m-%d')
            today = datetime.now()
            age = today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))

            if age < 13:
                return render_template(
                    'auth/signup_step2.html',
                    user=user_data,
                    error='You must be at least 13 years old to sign up.',
                )

            if age < 60:
                age_category = 'youth'
            else:
                age_category = 'elderly'

        except ValueError:
            return render_template(
                'auth/signup_step2.html',
                user=user_data,
                error='Invalid date format. Please enter a valid birthday.',
            )

        draft.update(
            {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'display_name': display_name,
                'phone': phone,
                'birthday': birthday_str,
                'age_category': age_category,
            }
        )
        _set_signup_draft(draft)
        return redirect(url_for('auth.signup_step3'))

    return render_template('auth/signup_step2.html', user=draft)


@auth_bp.route('/signup/step3', methods=['GET', 'POST'])
def signup_step3():
    """Signup Step 3: interests from storyboard categories (max 3)."""
    draft = _get_signup_draft()
    required_keys = ['first_name', 'last_name', 'username', 'display_name', 'email', 'birthday']
    if not all(draft.get(k) for k in required_keys):
        return redirect(url_for('auth.signup'))

    from topics import get_featured_topics, get_all_topics
    from database import get_db

    topic_map = {}
    for topic in (get_featured_topics() or []):
        slug = (topic.get('slug') or '').strip()
        if slug:
            topic_map[slug] = topic
    for topic in (get_all_topics() or []):
        slug = (topic.get('slug') or '').strip()
        if slug and slug not in topic_map:
            topic_map[slug] = topic

    topic_options = sorted(topic_map.values(), key=lambda item: (item.get('title') or '').lower())

    if request.method == 'POST':
        selected_slugs = request.form.getlist('interests')
        selected_slugs = [s.strip() for s in selected_slugs if (s or '').strip()]
        selected_slugs = list(dict.fromkeys(selected_slugs))

        valid_slug_set = {t.get('slug') for t in topic_options}
        selected_slugs = [slug for slug in selected_slugs if slug in valid_slug_set]

        if not selected_slugs:
            return render_template(
                'auth/signup_step3.html',
                error='Please select at least 1 interest.',
                topic_options=topic_options,
                selected_interests=[],
            )

        if len(selected_slugs) > 3:
            return render_template(
                'auth/signup_step3.html',
                error='You can select up to 3 interests only.',
                topic_options=topic_options,
                selected_interests=selected_slugs,
            )

        try:
            conn = get_db()
            cur = conn.cursor(dictionary=True)

            password_to_store = draft.get('password')
            if not password_to_store:
                password_to_store = f"google_oauth_{secrets.token_urlsafe(24)}"

            cur.execute(
                """
                INSERT INTO users
                (email, username, password_hash, first_name, last_name, display_name,
                 phone_number, date_of_birth, age_group, location_enabled, interests)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    draft.get('email'),
                    draft.get('username'),
                    password_to_store,
                    draft.get('first_name'),
                    draft.get('last_name'),
                    draft.get('display_name'),
                    draft.get('phone') or None,
                    draft.get('birthday'),
                    draft.get('age_category'),
                    0,
                    _serialize_selected_interests(selected_slugs),
                ),
            )

            user_id = cur.lastrowid
            conn.commit()
            cur.close()

            user = User.get_by_id(user_id)

            session['user_id'] = user_id
            session['signup_email'] = draft.get('email')

            if user:
                login_user(user)

            _clear_signup_draft()
            return redirect(url_for('main.home'))

        except Exception as e:
            error_msg = str(e)
            if 'Unknown MySQL server host' in error_msg or 'getaddrinfo failed' in error_msg:
                guidance = (
                    "Could not reach MySQL host.\n"
                    "Please verify the hostname in your Config (Config.MYSQL_HOST),\n"
                    "ensure DNS resolves it or try the database IP address, and confirm port/network access."
                )
                return render_template(
                    'auth/signup_step3.html',
                    error=guidance,
                    topic_options=topic_options,
                    selected_interests=selected_slugs,
                )

            return render_template(
                'auth/signup_step3.html',
                error=f"An error occurred while creating your account: {error_msg[:200]}",
                topic_options=topic_options,
                selected_interests=selected_slugs,
            )

    selected_from_draft = draft.get('interests') or []
    return render_template(
        'auth/signup_step3.html',
        topic_options=topic_options,
        selected_interests=selected_from_draft,
    )

@auth_bp.route('/signup2', methods=['GET'])
def signup_step2_legacy():
    return redirect(url_for('auth.signup_step2'))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            return render_template('auth/login.html', error="Username and password required.")

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

        user = User.get_by_username(username)

        if user and user.check_password(password):
            session.pop('failed_attempts', None)
            session.pop('lockout_time', None)
            login_user(user)
            
            return redirect(url_for('main.home'))
        else:
            failed_attempts += 1
            session['failed_attempts'] = failed_attempts
            
            if failed_attempts >= 3:
                # Lock out for 10 seconds after 3 failed attempts
                lockout_time = datetime.now() + timedelta(seconds=10)
                session['lockout_time'] = lockout_time.isoformat()  # datetime to string
                return render_template('auth/login.html', 
                    error="Too many failed attempts.", 
                    lockout_seconds=10)
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


@auth_bp.route('/settings')
@login_required
def settings():
    return redirect(url_for('auth.appearance_settings'))


@auth_bp.route('/language', methods=['GET'])
@login_required
def language_settings():
    raw_language = (getattr(current_user, 'language', None) or 'en').strip()

    # Check exact match first, then alias, then fallback
    valid_codes = {code for code, _ in GOOGLE_TRANSLATE_LANGUAGES}
    if raw_language in valid_codes:
        normalized = raw_language
    else:
        normalized = GOOGLE_TRANSLATE_LANGUAGE_ALIASES.get(raw_language.lower())
        if not normalized or normalized not in valid_codes:
            lc = raw_language.lower()
            normalized = next((code for code in valid_codes if code.lower() == lc), 'en')

    return render_template(
        'auth/language.html',
        language_options=GOOGLE_TRANSLATE_LANGUAGES,
        current_language=normalized,
    )


@auth_bp.route('/language/update', methods=['POST'])
@login_required
def update_language():
    from database import execute_query

    data = request.get_json(silent=True) or request.form
    raw_language = (data.get('language') or 'en').strip()

    valid_codes = {code for code, _ in GOOGLE_TRANSLATE_LANGUAGES}

    # 1. Exact match
    if raw_language in valid_codes:
        language = raw_language
    else:
        # 2. Alias match
        language = GOOGLE_TRANSLATE_LANGUAGE_ALIASES.get(raw_language.lower())
        if not language or language not in valid_codes:
            # 3. Case-insensitive scan
            lc = raw_language.lower()
            language = next((code for code in valid_codes if code.lower() == lc), 'en')

    execute_query(
        "UPDATE users SET language = %s WHERE id = %s",
        (language, current_user.id),
        commit=True,
    )

    return ('', 204)


@auth_bp.route('/appearance')
@login_required
def appearance_settings():
    return render_template('auth/appearance.html')


@auth_bp.route('/appearance/update', methods=['POST'])
@login_required
def update_appearance():
    from database import get_db

    try:
        data = request.get_json(silent=True) or request.form

        theme = (data.get('theme') or 'light').strip().lower()
        db_theme = 'darkmode' if theme == 'dark' else 'lightmode'

        try:
            text_size = int(data.get('text_size', 16))
        except (TypeError, ValueError):
            text_size = 16
        text_size = max(12, min(48, text_size))

        font_style_raw = (data.get('font_style') or 'poppins').strip().lower()
        font_db_map = {
            'poppins': 'Poppins',
            'arial': 'Arial',
            'verdana': 'Verdana',
            'tahoma': 'Tahoma',
            'trebuchet': 'Trebuchet MS',
            'georgia': 'Georgia',
            'times': 'Times New Roman',
            'courier': 'Courier New'
        }
        font_style = font_db_map.get(font_style_raw, 'Poppins')

        font_weight_raw = str(data.get('font_weight', '500')).strip()
        boldness_map = {
            '300': 'light',
            '500': 'medium',
            '700': 'dark'
        }
        boldness = boldness_map.get(font_weight_raw, 'medium')

        conn = get_db()
        cur = conn.cursor(dictionary=True)

        try:
            cur.execute(
                """
                SELECT id
                FROM appearance
                WHERE user_id = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (current_user.id,)
            )
            latest_row = cur.fetchone()

            if latest_row:
                keep_id = latest_row.get('id')
                cur.execute(
                    """
                    UPDATE appearance
                    SET theme = %s, text_size = %s, font_style = %s, boldness = %s
                    WHERE id = %s
                    """,
                    (db_theme, text_size, font_style, boldness, keep_id)
                )

                cur.execute(
                    """
                    DELETE FROM appearance
                    WHERE user_id = %s AND id <> %s
                    """,
                    (current_user.id, keep_id)
                )
            else:
                cur.execute(
                    """
                    INSERT INTO appearance (user_id, theme, text_size, font_style, boldness)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (current_user.id, db_theme, text_size, font_style, boldness)
                )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()

        return {'success': True}, 200
    except Exception as e:
        return {'success': False, 'error': str(e)[:200]}, 500


@auth_bp.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    if request.method == 'POST':
        logout_user()
        session.clear()
        return redirect(url_for('index'))

    return render_template('auth/logout.html')


@auth_bp.route('/logout-now', methods=['GET'])
@login_required
def logout_now():
    logout_user()
    session.clear()
    return redirect(url_for('index'))


@auth_bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    from database import get_db

    user_id = current_user.id
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    try:
        cur.execute("SELECT DATABASE() AS db_name")
        db_row = cur.fetchone() or {}
        db_name = db_row.get('db_name')

        cleanup_targets = []

        if db_name:
            cur.execute(
                """
                SELECT TABLE_NAME, COLUMN_NAME
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s
                  AND REFERENCED_TABLE_NAME = 'users'
                  AND REFERENCED_COLUMN_NAME = 'id'
                """,
                (db_name,)
            )
            for row in cur.fetchall() or []:
                table_name = row.get('TABLE_NAME')
                column_name = row.get('COLUMN_NAME')
                if table_name and column_name:
                    cleanup_targets.append((table_name, column_name))

            cur.execute(
                """
                SELECT TABLE_NAME, COLUMN_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND COLUMN_NAME = 'user_id'
                """,
                (db_name,)
            )
            for row in cur.fetchall() or []:
                table_name = row.get('TABLE_NAME')
                column_name = row.get('COLUMN_NAME')
                if table_name and column_name:
                    cleanup_targets.append((table_name, column_name))

        unique_targets = set(cleanup_targets)

        for table_name, column_name in sorted(unique_targets):
            if table_name == 'users' and column_name == 'id':
                continue
            cur.execute(
                f"DELETE FROM `{table_name}` WHERE `{column_name}` = %s",
                (user_id,)
            )

        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        conn.commit()
    except Exception as exc:
        conn.rollback()
        flash(f'Could not delete account: {str(exc)[:200]}', 'error')
        return redirect(url_for('auth.logout'))
    finally:
        cur.close()

    logout_user()
    session.clear()
    return redirect(url_for('index'))
