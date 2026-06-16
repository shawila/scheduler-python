import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from app.extensions import db
from app.models.pending_booking import PendingBooking


VALID_PAYLOAD = {
    'store_email': 'store@example.com',
    'guest_email': 'guest@example.com',
    'guest_name': 'John Doe',
    'date': '2024-08-01',
    'start_time': '11:00',
    'end_time': '12:30',
}


def mock_free_service():
    service = MagicMock()
    service.freebusy().query().execute.return_value = {
        'calendars': {'primary': {'busy': []}}
    }
    return service


class TestPostBook:
    def test_missing_fields_returns_400(self, client, store):
        response = client.post('/book', json={'store_email': 'store@example.com'})
        assert response.status_code == 400
        assert 'Missing' in response.json['error']

    def test_invalid_date_format_returns_400(self, client, store):
        payload = {**VALID_PAYLOAD, 'date': 'not-a-date'}
        response = client.post('/book', json=payload)
        assert response.status_code == 400

    def test_unaligned_start_time_returns_400(self, client, store):
        payload = {**VALID_PAYLOAD, 'start_time': '11:15'}
        response = client.post('/book', json=payload)
        assert response.status_code == 400
        assert 'aligned' in response.json['error']

    def test_end_before_start_returns_400(self, client, store):
        payload = {**VALID_PAYLOAD, 'start_time': '12:00', 'end_time': '11:00'}
        response = client.post('/book', json=payload)
        assert response.status_code == 400

    def test_duration_not_multiple_of_slot_returns_400(self, client, store):
        payload = {**VALID_PAYLOAD, 'start_time': '11:00', 'end_time': '11:45'}
        response = client.post('/book', json=payload)
        assert response.status_code == 400
        assert 'multiple' in response.json['error']

    def test_duration_exceeding_max_returns_400(self, client, store):
        payload = {**VALID_PAYLOAD, 'start_time': '11:00', 'end_time': '14:30'}
        response = client.post('/book', json=payload)
        assert response.status_code == 400
        assert '180' in response.json['error']

    def test_store_not_found_returns_400(self, client, store):
        payload = {**VALID_PAYLOAD, 'store_email': 'unknown@example.com'}
        response = client.post('/book', json=payload)
        assert response.status_code == 400
        assert 'Store not found' in response.json['error']

    def test_mx_check_failure_returns_400(self, client, store):
        with patch('app.booking.routes.check_mx_record', return_value=False):
            response = client.post('/book', json=VALID_PAYLOAD)
        assert response.status_code == 400
        assert 'email domain' in response.json['error']

    def test_slot_already_taken_returns_409(self, client, store):
        busy_service = MagicMock()
        busy_service.freebusy().query().execute.return_value = {
            'calendars': {'primary': {'busy': [
                {'start': '2024-08-01T11:00:00Z', 'end': '2024-08-01T12:00:00Z'}
            ]}}
        }
        with patch('app.booking.routes.check_mx_record', return_value=True), \
             patch('app.booking.routes.build', return_value=busy_service):
            response = client.post('/book', json=VALID_PAYLOAD)
        assert response.status_code == 409

    def test_valid_request_creates_pending_booking(self, client, app, store):
        with patch('app.booking.routes.check_mx_record', return_value=True), \
             patch('app.booking.routes.build', return_value=mock_free_service()), \
             patch('app.booking.routes.send_confirmation_email') as mock_email:
            response = client.post('/book', json=VALID_PAYLOAD)

        assert response.status_code == 200
        assert 'guest@example.com' in response.json['message']
        mock_email.assert_called_once()

        with app.app_context():
            pending = PendingBooking.query.filter_by(guest_email='guest@example.com').first()
            assert pending is not None
            assert pending.store_email == 'store@example.com'


from app.models.booking import Booking


def make_pending(app, token='valid-token-abc', expires_hours=24):
    with app.app_context():
        pending = PendingBooking(
            confirmation_token=token,
            store_email='store@example.com',
            guest_email='guest@example.com',
            guest_name='John Doe',
            start_datetime=datetime(2024, 8, 1, 11, 0, 0),
            end_datetime=datetime(2024, 8, 1, 12, 30, 0),
            expires_at=datetime.utcnow() + timedelta(hours=expires_hours),
        )
        db.session.add(pending)
        db.session.commit()


def mock_calendar_service(event_id='google_event_123'):
    service = MagicMock()
    service.events().insert().execute.return_value = {
        'id': event_id,
        'summary': 'Appointment',
        'start': {'dateTime': '2024-08-01T11:00:00Z'},
        'end': {'dateTime': '2024-08-01T12:30:00Z'},
        'htmlLink': 'https://calendar.google.com/event?eid=abc',
    }
    return service


class TestConfirmBooking:
    def test_unknown_token_returns_404(self, client, store):
        response = client.get('/confirm-booking/nonexistent-token')
        assert response.status_code == 404

    def test_expired_token_returns_410(self, client, app, store):
        make_pending(app, token='expired-token', expires_hours=-1)
        response = client.get('/confirm-booking/expired-token')
        assert response.status_code == 410

    def test_valid_token_returns_200_with_event_details(self, client, app, store):
        make_pending(app)
        with patch('app.booking.routes.build', return_value=mock_calendar_service()):
            response = client.get('/confirm-booking/valid-token-abc')
        assert response.status_code == 200
        assert response.json['event_id'] == 'google_event_123'
        assert 'html_link' in response.json

    def test_valid_token_saves_booking_record(self, client, app, store):
        make_pending(app)
        with patch('app.booking.routes.build', return_value=mock_calendar_service()):
            client.get('/confirm-booking/valid-token-abc')
        with app.app_context():
            booking = Booking.query.filter_by(guest_email='guest@example.com').first()
            assert booking is not None
            assert booking.google_event_id == 'google_event_123'

    def test_valid_token_deletes_pending_booking(self, client, app, store):
        make_pending(app)
        with patch('app.booking.routes.build', return_value=mock_calendar_service()):
            client.get('/confirm-booking/valid-token-abc')
        with app.app_context():
            pending = PendingBooking.query.filter_by(confirmation_token='valid-token-abc').first()
            assert pending is None

    def test_google_event_created_with_guest_as_attendee(self, client, app, store):
        make_pending(app)
        service = mock_calendar_service()
        with patch('app.booking.routes.build', return_value=service):
            client.get('/confirm-booking/valid-token-abc')
        insert_call_kwargs = service.events().insert.call_args[1]
        event_body = insert_call_kwargs['body']
        assert any(a['email'] == 'guest@example.com' for a in event_body['attendees'])
        assert insert_call_kwargs['sendUpdates'] == 'all'
