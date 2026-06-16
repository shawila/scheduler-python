from app.extensions import db


class OrganizationInvite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    invited_email = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')
    priority = db.Column(db.Integer, nullable=False, default=1)
    expires_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('org_id', 'invited_email', name='uq_org_invite_org_email'),
    )

    def __repr__(self):
        return f'<OrganizationInvite {self.invited_email} org_id={self.org_id}>'
