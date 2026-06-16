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
