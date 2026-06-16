from app.extensions import db


class OrganizationMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    org_id = db.Column(db.Integer, db.ForeignKey('organization.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')
    priority = db.Column(db.Integer, nullable=False, default=1)

    org = db.relationship('Organization', backref='members')
    user = db.relationship('User', backref=db.backref('org_member', uselist=False))

    def __repr__(self):
        return f'<OrganizationMember user_id={self.user_id} role={self.role}>'
