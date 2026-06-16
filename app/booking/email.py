import os
from flask_mail import Message
from app.extensions import mail


def send_confirmation_email(guest_email: str, guest_name: str, token: str) -> None:
    base_url = os.getenv('BOOKING_CONFIRM_BASE_URL', 'http://localhost:5000')
    confirm_url = f'{base_url}/confirm-booking/{token}'
    msg = Message(
        subject='Confirm your appointment booking',
        recipients=[guest_email],
        body=(
            f'Hi {guest_name},\n\n'
            f'Please confirm your appointment by clicking the link below:\n\n'
            f'{confirm_url}\n\n'
            f'This link expires in 24 hours.\n'
        ),
    )
    mail.send(msg)
