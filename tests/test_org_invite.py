from unittest.mock import patch
from datetime import datetime, timedelta
from app.models.organization_invite import OrganizationInvite
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.extensions import db

OWNER_TOKEN = 'owner-api-token'


def auth(token=OWNER_TOKEN):
    return {'Authorization': f'Bearer {token}'}


class TestPostOrgInvite:
    def test_unauthenticated_returns_401(self, client, org_with_owner):
        with patch('app.auth.generate_auth_url', return_value='https://mock'):
            response = client.post(f'/org/{org_with_owner}/invite',
                                   json={'invitee_email': 'x@x.com'})
        assert response.status_code == 401

    def test_missing_invitee_email_returns_400(self, client, authed_user, org_with_owner):
        response = client.post(f'/org/{org_with_owner}/invite', json={}, headers=auth())
        assert response.status_code == 400

    def test_employee_cannot_invite_returns_403(self, client, app, authed_user, org_with_owner):
        with app.app_context():
            member = OrganizationMember.query.filter_by(user_id=authed_user.id).first()
            member.role = 'employee'
            db.session.commit()
        response = client.post(f'/org/{org_with_owner}/invite',
                               json={'invitee_email': 'x@x.com'},
                               headers=auth())
        assert response.status_code == 403

    def test_manager_cannot_invite_manager_returns_403(self, client, app, authed_user, org_with_owner):
        with app.app_context():
            member = OrganizationMember.query.filter_by(user_id=authed_user.id).first()
            member.role = 'manager'
            db.session.commit()
        response = client.post(f'/org/{org_with_owner}/invite',
                               json={'invitee_email': 'x@x.com', 'role': 'manager'},
                               headers=auth())
        assert response.status_code == 403

    def test_invitee_already_in_org_returns_400(self, client, app, authed_user, org_with_owner):
        with app.app_context():
            existing = User(email='taken@x.com', token='t', refresh_token='r',
                            token_uri='u', client_id='c', client_secret='s', scopes='sc')
            db.session.add(existing)
            db.session.flush()
            db.session.add(OrganizationMember(org_id=org_with_owner, user_id=existing.id,
                                              role='employee', priority=1))
            db.session.commit()
        response = client.post(f'/org/{org_with_owner}/invite',
                               json={'invitee_email': 'taken@x.com'},
                               headers=auth())
        assert response.status_code == 400
        assert 'already belongs' in response.json['error']

    def test_duplicate_pending_invite_returns_400(self, client, app, authed_user, org_with_owner):
        with app.app_context():
            exp = datetime.utcnow() + timedelta(hours=24)
            db.session.add(OrganizationInvite(
                org_id=org_with_owner, invited_email='new@x.com',
                token='existingtok', role='employee', priority=1, expires_at=exp,
            ))
            db.session.commit()
        response = client.post(f'/org/{org_with_owner}/invite',
                               json={'invitee_email': 'new@x.com'},
                               headers=auth())
        assert response.status_code == 400
        assert 'pending' in response.json['error']

    def test_valid_invite_creates_record_and_sends_email(self, client, app, authed_user, org_with_owner):
        with patch('app.org.routes.send_invite_email') as mock_email:
            response = client.post(f'/org/{org_with_owner}/invite',
                                   json={'invitee_email': 'new@x.com', 'role': 'employee', 'priority': 2},
                                   headers=auth())
        assert response.status_code == 200
        mock_email.assert_called_once()
        with app.app_context():
            invite = OrganizationInvite.query.filter_by(invited_email='new@x.com').first()
            assert invite is not None
            assert invite.role == 'employee'
            assert invite.priority == 2
