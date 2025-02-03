from flask import Blueprint, redirect, url_for, session, request, jsonify
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from app.models.customer import Customer
from app.extensions import db
import os

main_bp = Blueprint('main', __name__)

# Disable the HTTPS requirement for OAuth when running locally
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

CLIENT_SECRETS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]
REDIRECT_URI = "http://localhost:5000/callback"

flow = Flow.from_client_secrets_file(
    CLIENT_SECRETS_FILE,
    scopes=SCOPES,
    redirect_uri=REDIRECT_URI
)

@main_bp.route('/')
def index():
    # Redirect customer to the Google OAuth consent screen
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    session['state'] = state
    return redirect(authorization_url)

@main_bp.route('/callback')
def callback():
    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials

    # Extract customer email from credentials (requires Google People API or parsing ID token)
    customer_email = 'salah.hawila@gmail.com'  # You should implement a proper way to retrieve this

    # Check if customer exists in the database
    customer = Customer.query.filter_by(email=customer_email).first()
    if not customer:
        # Create a new customer entry if not found
        customer = Customer(
            email=customer_email,
            token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=credentials.token_uri,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            scopes=','.join(credentials.scopes)
        )
        db.session.add(customer)
    else:
        # Update existing customer tokens
        customer.token = credentials.token
        customer.refresh_token = credentials.refresh_token
        customer.token_uri = credentials.token_uri
        customer.client_id = credentials.client_id
        customer.client_secret = credentials.client_secret
        customer.scopes = ','.join(credentials.scopes)

    db.session.commit()

    return "Google Calendar Connected Successfully!"

@main_bp.route('/get-busy-hours', methods=['GET'])
def get_busy_hours():
    customer_email = request.args.get('email')
    customer = Customer.query.filter_by(email=customer_email).first()

    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    # Use the stored credentials to access the Google Calendar API
    from google.oauth2.credentials import Credentials
    credentials = Credentials(
        token=customer.token,
        refresh_token=customer.refresh_token,
        token_uri=customer.token_uri,
        client_id=customer.client_id,
        client_secret=customer.client_secret,
        scopes=customer.scopes.split(',')
    )

    service = build('calendar', 'v3', credentials=credentials)

    # Fetch busy hours (implement based on your use case)
    events_result = service.events().list(
        calendarId='primary', timeMin='2024-08-01T00:00:00Z',
        timeMax='2024-08-01T23:59:59Z',
        maxResults=10, singleEvents=True,
        orderBy='startTime').execute()

    events = events_result.get('items', [])
    busy_hours = [{'start': event['start']['dateTime'], 'end': event['end']['dateTime']} for event in events]

    return jsonify(busy_hours)

