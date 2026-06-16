from datetime import datetime
from app.extensions import db


class PendingBooking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    confirmation_token = db.Column(db.String(100), unique=True, nullable=False)
    store_email = db.Column(db.String(120), nullable=False)
    guest_email = db.Column(db.String(120), nullable=False)
    guest_name = db.Column(db.String(200), nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    def __repr__(self):
        return f'<PendingBooking {self.guest_email} @ {self.start_datetime}>'
