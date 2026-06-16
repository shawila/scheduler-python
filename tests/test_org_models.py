import pytest
from datetime import datetime, timedelta
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.organization_invite import OrganizationInvite
from app.models.user import User
from app.extensions import db


def make_user(app, email='a@example.com'):
    with app.app_context():
        u = User(
            email=email, token='t', refresh_token='r',
            token_uri='u', client_id='c', client_secret='s', scopes='sc',
        )
        db.session.add(u)
        db.session.commit()
        return u.id


class TestOrganizationModel:
    def test_organization_can_be_created(self, app):
        with app.app_context():
            org = Organization(name='Acme', google_calendar_id='cal123')
            db.session.add(org)
            db.session.commit()
            assert Organization.query.count() == 1

    def test_organization_member_unique_per_user(self, app):
        uid = make_user(app)
        with app.app_context():
            org1 = Organization(name='Org1', google_calendar_id='c1')
            org2 = Organization(name='Org2', google_calendar_id='c2')
            db.session.add_all([org1, org2])
            db.session.flush()
            db.session.add(OrganizationMember(org_id=org1.id, user_id=uid, role='owner', priority=1))
            db.session.commit()
            db.session.add(OrganizationMember(org_id=org2.id, user_id=uid, role='employee', priority=1))
            with pytest.raises(Exception):
                db.session.commit()

    def test_organization_invite_unique_per_org_and_email(self, app):
        with app.app_context():
            org = Organization(name='Org', google_calendar_id='cx')
            db.session.add(org)
            db.session.flush()
            exp = datetime.utcnow() + timedelta(hours=24)
            db.session.add(OrganizationInvite(
                org_id=org.id, invited_email='x@y.com',
                token='tok1', role='employee', priority=1, expires_at=exp,
            ))
            db.session.commit()
            db.session.add(OrganizationInvite(
                org_id=org.id, invited_email='x@y.com',
                token='tok2', role='employee', priority=1, expires_at=exp,
            ))
            with pytest.raises(Exception):
                db.session.commit()

    def test_user_api_token_field_exists(self, app):
        with app.app_context():
            u = User(
                email='b@b.com', token='t', refresh_token='r',
                token_uri='u', client_id='c', client_secret='s',
                scopes='sc', api_token='mytoken',
            )
            db.session.add(u)
            db.session.commit()
            assert User.query.filter_by(api_token='mytoken').first() is not None
