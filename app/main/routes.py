from datetime import datetime
from flask import Blueprint, redirect, session, request, jsonify
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from app.google_calendar import credentials_from_user
from app.models.user import User
from app.extensions import db
import os

main_bp = Blueprint('main', __name__)

# Allow HTTP for OAuth only in development
if os.getenv('FLASK_ENV') == 'development':
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]
REDIRECT_URI = "http://localhost:5000/callback"


def _build_flow():
    return Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )


@main_bp.route('/')
def index():
    flow = _build_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
    )
    session['state'] = state
    return redirect(authorization_url)


@main_bp.route('/callback')
def callback():
    flow = _build_flow()
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    oauth2_client = build('oauth2', 'v2', credentials=credentials)
    user_info = oauth2_client.userinfo().get().execute()
    user_email = user_info['email']

    user = User.query.filter_by(email=user_email).first()
    token_data = dict(
        token=credentials.token,
        refresh_token=credentials.refresh_token,
        token_uri=credentials.token_uri,
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        scopes=','.join(credentials.scopes),
    )

    if not user:
        user = User(email=user_email, **token_data)
        db.session.add(user)
    else:
        for key, value in token_data.items():
            setattr(user, key, value)

    db.session.commit()
    return "Google Calendar Connected Successfully!"


@main_bp.route('/get-busy-hours', methods=['GET'])
def get_busy_hours():
    user_email = request.args.get('email')
    date_str = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))

    if not user_email:
        return jsonify({'error': 'email parameter is required'}), 400

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    user = User.query.filter_by(email=user_email).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    credentials = credentials_from_user(user)
    service = build('calendar', 'v3', credentials=credentials)

    time_min = date.strftime('%Y-%m-%dT00:00:00Z')
    time_max = date.strftime('%Y-%m-%dT23:59:59Z')

    events_result = service.events().list(
        calendarId='primary',
        timeMin=time_min,
        timeMax=time_max,
        maxResults=50,
        singleEvents=True,
        orderBy='startTime',
    ).execute()

    events = events_result.get('items', [])
    busy_hours = [
        {'start': e['start']['dateTime'], 'end': e['end']['dateTime']}
        for e in events
        if 'dateTime' in e.get('start', {})
    ]

    return jsonify(busy_hours)
