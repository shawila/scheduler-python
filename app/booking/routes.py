import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from googleapiclient.discovery import build
from app.extensions import db
from app.models.customer import Customer
from app.models.pending_booking import PendingBooking
from app.models.booking import Booking
from app.google_calendar import credentials_from_customer
from app.booking.validation import is_slot_aligned, validate_booking_duration, check_mx_record
from app.booking.email import send_confirmation_email

booking_bp = Blueprint('booking', __name__)


@booking_bp.route('/book', methods=['POST'])
def book():
    data = request.get_json() or {}

    required = ['store_email', 'guest_email', 'guest_name', 'date', 'start_time', 'end_time']
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({'error': f'Missing fields: {", ".join(missing)}'}), 400

    try:
        date = datetime.strptime(data['date'], '%Y-%m-%d')
        start_time = datetime.strptime(data['start_time'], '%H:%M')
        end_time = datetime.strptime(data['end_time'], '%H:%M')
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    start_dt = datetime(date.year, date.month, date.day, start_time.hour, start_time.minute)
    end_dt = datetime(date.year, date.month, date.day, end_time.hour, end_time.minute)

    if not is_slot_aligned(start_dt):
        return jsonify({'error': 'Times must be aligned to 30-minute slots (minutes must be 00 or 30)'}), 400

    valid, error = validate_booking_duration(start_dt, end_dt)
    if not valid:
        return jsonify({'error': error}), 400

    customer = Customer.query.filter_by(email=data['store_email']).first()
    if not customer:
        return jsonify({'error': 'Store not found'}), 400

    if not check_mx_record(data['guest_email']):
        return jsonify({'error': 'Could not verify guest email domain'}), 400

    credentials = credentials_from_customer(customer)
    service = build('calendar', 'v3', credentials=credentials)
    freebusy = service.freebusy().query(body={
        'timeMin': start_dt.isoformat() + 'Z',
        'timeMax': end_dt.isoformat() + 'Z',
        'timeZone': 'UTC',
        'items': [{'id': 'primary'}],
    }).execute()

    if freebusy['calendars']['primary'].get('busy'):
        return jsonify({'error': 'Requested time slot is not available'}), 409

    token = secrets.token_urlsafe(32)
    pending = PendingBooking(
        confirmation_token=token,
        store_email=data['store_email'],
        guest_email=data['guest_email'],
        guest_name=data['guest_name'],
        start_datetime=start_dt,
        end_datetime=end_dt,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.session.add(pending)
    db.session.commit()

    send_confirmation_email(data['guest_email'], data['guest_name'], token)

    return jsonify({'message': f'Confirmation email sent to {data["guest_email"]}'}), 200


@booking_bp.route('/confirm-booking/<token>', methods=['GET'])
def confirm_booking(token):
    pending = PendingBooking.query.filter_by(confirmation_token=token).first()
    if not pending:
        return jsonify({'error': 'Invalid confirmation token'}), 404

    if pending.expires_at < datetime.utcnow():
        return jsonify({'error': 'Confirmation link has expired'}), 410

    customer = Customer.query.filter_by(email=pending.store_email).first()
    credentials = credentials_from_customer(customer)
    service = build('calendar', 'v3', credentials=credentials)

    event_body = {
        'summary': 'Appointment',
        'start': {'dateTime': pending.start_datetime.isoformat() + 'Z', 'timeZone': 'UTC'},
        'end': {'dateTime': pending.end_datetime.isoformat() + 'Z', 'timeZone': 'UTC'},
        'attendees': [{'email': pending.guest_email, 'displayName': pending.guest_name}],
    }
    created_event = service.events().insert(
        calendarId='primary',
        body=event_body,
        sendUpdates='all',
    ).execute()

    booking = Booking(
        google_event_id=created_event['id'],
        store_email=pending.store_email,
        guest_email=pending.guest_email,
        guest_name=pending.guest_name,
        start_datetime=pending.start_datetime,
        end_datetime=pending.end_datetime,
    )
    db.session.add(booking)
    db.session.delete(pending)
    db.session.commit()

    return jsonify({
        'event_id': created_event['id'],
        'title': created_event['summary'],
        'start': created_event['start']['dateTime'],
        'end': created_event['end']['dateTime'],
        'html_link': created_event.get('htmlLink'),
    }), 200
