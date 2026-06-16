from datetime import datetime
from app.extensions import db


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_event_id = db.Column(db.String(200), nullable=False)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    admin_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    guest_email = db.Column(db.String(120), nullable=False)
    guest_name = db.Column(db.String(200), nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    org = db.relationship('Organization')
    admin = db.relationship('User')

    def __repr__(self):
        return f'<Booking {self.guest_email} @ {self.start_datetime}>'
