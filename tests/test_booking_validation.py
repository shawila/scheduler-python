from datetime import datetime
from unittest.mock import patch
from app.booking.validation import is_slot_aligned, validate_booking_duration, check_mx_record

START = datetime(2024, 8, 1, 11, 0, 0)


class TestIsSlotAligned:
    def test_on_hour_is_aligned(self):
        assert is_slot_aligned(datetime(2024, 8, 1, 9, 0, 0)) is True

    def test_on_half_hour_is_aligned(self):
        assert is_slot_aligned(datetime(2024, 8, 1, 9, 30, 0)) is True

    def test_at_15_minutes_is_not_aligned(self):
        assert is_slot_aligned(datetime(2024, 8, 1, 9, 15, 0)) is False

    def test_at_45_minutes_is_not_aligned(self):
        assert is_slot_aligned(datetime(2024, 8, 1, 9, 45, 0)) is False


class TestValidateBookingDuration:
    def test_valid_single_slot(self):
        valid, _ = validate_booking_duration(START, datetime(2024, 8, 1, 11, 30, 0))
        assert valid is True

    def test_valid_three_hours(self):
        valid, _ = validate_booking_duration(START, datetime(2024, 8, 1, 14, 0, 0))
        assert valid is True

    def test_end_before_start_is_invalid(self):
        valid, error = validate_booking_duration(START, datetime(2024, 8, 1, 10, 30, 0))
        assert valid is False
        assert 'after' in error

    def test_same_start_and_end_is_invalid(self):
        valid, _ = validate_booking_duration(START, START)
        assert valid is False

    def test_duration_not_multiple_of_slot_is_invalid(self):
        valid, error = validate_booking_duration(START, datetime(2024, 8, 1, 11, 45, 0))
        assert valid is False
        assert 'multiple' in error

    def test_duration_exceeding_max_is_invalid(self):
        valid, error = validate_booking_duration(START, datetime(2024, 8, 1, 14, 30, 0))
        assert valid is False
        assert '180' in error


class TestCheckMxRecord:
    def test_domain_with_mx_record_returns_true(self):
        with patch('app.booking.validation.dns.resolver.resolve') as mock_resolve:
            mock_resolve.return_value = ['mx1.example.com']
            assert check_mx_record('guest@example.com') is True

    def test_domain_without_mx_record_returns_false(self):
        with patch('app.booking.validation.dns.resolver.resolve', side_effect=Exception('NXDOMAIN')):
            assert check_mx_record('guest@notarealdomain.xyz') is False

    def test_dns_timeout_returns_false(self):
        with patch('app.booking.validation.dns.resolver.resolve', side_effect=Exception('Timeout')):
            assert check_mx_record('guest@example.com') is False


from unittest.mock import call
from app.booking.email import send_confirmation_email


class TestSendConfirmationEmail:
    def test_sends_to_guest_email(self):
        with patch('app.booking.email.mail') as mock_mail:
            send_confirmation_email('guest@example.com', 'John Doe', 'abc123token')
            mock_mail.send.assert_called_once()
            message = mock_mail.send.call_args[0][0]
            assert message.recipients == ['guest@example.com']

    def test_subject_contains_confirm(self):
        with patch('app.booking.email.mail') as mock_mail:
            send_confirmation_email('guest@example.com', 'John Doe', 'abc123token')
            message = mock_mail.send.call_args[0][0]
            assert 'Confirm' in message.subject

    def test_body_contains_confirmation_link_with_token(self):
        with patch('app.booking.email.mail') as mock_mail:
            send_confirmation_email('guest@example.com', 'John Doe', 'abc123token')
            message = mock_mail.send.call_args[0][0]
            assert 'abc123token' in message.body
            assert '/confirm-booking/' in message.body
