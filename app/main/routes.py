from datetime import datetime
from flask import Blueprint, redirect, session, request, jsonify
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from app.models.customer import Customer
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


def _credentials_from_customer(customer):
    return Credentials(
        token=customer.token,
        refresh_token=customer.refresh_token,
        token_uri=customer.token_uri,
        client_id=customer.client_id,
        client_secret=customer.client_secret,
        scopes=customer.scopes.split(','),
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
    customer_email = user_info['email']

    customer = Customer.query.filter_by(email=customer_email).first()
    token_data = dict(
        token=credentials.token,
        refresh_token=credentials.refresh_token,
        token_uri=credentials.token_uri,
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        scopes=','.join(credentials.scopes),
    )

    if not customer:
        customer = Customer(email=customer_email, **token_data)
        db.session.add(customer)
    else:
        for key, value in token_data.items():
            setattr(customer, key, value)

    db.session.commit()
    return "Google Calendar Connected Successfully!"


@main_bp.route('/get-busy-hours', methods=['GET'])
def get_busy_hours():
    customer_email = request.args.get('email')
    date_str = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))

    if not customer_email:
        return jsonify({'error': 'email parameter is required'}), 400

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    customer = Customer.query.filter_by(email=customer_email).first()
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    credentials = _credentials_from_customer(customer)
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
