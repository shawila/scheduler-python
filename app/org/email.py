import os
from flask_mail import Message
from app.extensions import mail


def send_invite_email(invited_email: str, org_name: str, org_uid: int, token: str) -> None:
    base_url = os.getenv('BOOKING_CONFIRM_BASE_URL', 'http://localhost:5000')
    join_url = f'{base_url}/org/{org_uid}/join/{token}'
    msg = Message(
        subject=f"You've been invited to join {org_name}",
        recipients=[invited_email],
        body=(
            f'You have been invited to join {org_name}.\n\n'
            f'Click the link below to accept:\n\n'
            f'{join_url}\n\n'
            f'This link expires in 24 hours.\n'
        ),
    )
    mail.send(msg)
