from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from app.models.organization_invite import OrganizationInvite
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.extensions import db


def make_invite(app, org_id, email='invitee@example.com', token='invite-tok', hours=24):
    with app.app_context():
        invite = OrganizationInvite(
            org_id=org_id,
            invited_email=email,
            token=token,
            role='employee',
            priority=1,
            expires_at=datetime.utcnow() + timedelta(hours=hours),
        )
        db.session.add(invite)
        db.session.commit()


def mock_join_oauth(email='invitee@example.com'):
    mock_creds = MagicMock()
    mock_creds.token = 'gtoken'
    mock_creds.refresh_token = 'rtoken'
    mock_creds.token_uri = 'https://oauth2.googleapis.com/token'
    mock_creds.client_id = 'cid'
    mock_creds.client_secret = 'csecret'
    mock_creds.scopes = ['https://www.googleapis.com/auth/calendar']

    mock_flow = MagicMock()
    mock_flow.credentials = mock_creds

    mock_oauth2 = MagicMock()
    mock_oauth2.userinfo().get().execute.return_value = {'email': email}
    return mock_flow, mock_oauth2


class TestJoinOrg:
    def test_invalid_token_returns_404(self, client, org_with_owner):
        response = client.get(f'/org/{org_with_owner}/join/nonexistent')
        assert response.status_code == 404

    def test_expired_token_returns_410(self, client, app, org_with_owner):
        make_invite(app, org_with_owner, token='expired-tok', hours=-1)
        response = client.get(f'/org/{org_with_owner}/join/expired-tok')
        assert response.status_code == 410

    def test_org_mismatch_returns_400(self, client, app, org_with_owner):
        make_invite(app, org_with_owner, token='mismatch-tok')
        response = client.get(f'/org/99999/join/mismatch-tok')
        assert response.status_code == 400

    def test_valid_token_redirects_to_google(self, client, app, org_with_owner):
        make_invite(app, org_with_owner, token='valid-tok')
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ('https://accounts.google.com/mock', 'state')
        with patch('app.org.routes.build_oauth_flow', return_value=mock_flow):
            response = client.get(f'/org/{org_with_owner}/join/valid-tok')
        assert response.status_code == 302
        assert 'accounts.google.com' in response.headers['Location']


class TestJoinCallback:
    def test_no_invite_in_session_returns_400(self, client):
        response = client.get('/org/join-callback')
        assert response.status_code == 400

    def test_email_mismatch_returns_400(self, client, app, org_with_owner):
        make_invite(app, org_with_owner, token='mismatch-tok', email='correct@example.com')
        mock_flow, mock_oauth2 = mock_join_oauth(email='wrong@example.com')
        with client.session_transaction() as sess:
            sess['org_invite_token'] = 'mismatch-tok'
        with patch('app.org.routes.build_oauth_flow', return_value=mock_flow), \
             patch('app.org.routes.build', return_value=mock_oauth2):
            response = client.get('/org/join-callback?code=fake')
        assert response.status_code == 400
        assert 'mismatch' in response.json['error'].lower()

    def test_already_in_different_org_returns_400(self, client, app, org_with_owner):
        from app.models.organization import Organization
        with app.app_context():
            other_org = Organization(name='Other', google_calendar_id='other-cal')
            db.session.add(other_org)
            db.session.flush()
            existing = User(email='taken@example.com', token='t', refresh_token='r',
                            token_uri='u', client_id='c', client_secret='s', scopes='sc')
            db.session.add(existing)
            db.session.flush()
            db.session.add(OrganizationMember(org_id=other_org.id, user_id=existing.id,
                                              role='employee', priority=1))
            db.session.add(OrganizationInvite(
                org_id=org_with_owner, invited_email='taken@example.com',
                token='other-org-tok', role='employee', priority=1,
                expires_at=datetime.utcnow() + timedelta(hours=24),
            ))
            db.session.commit()

        mock_flow, mock_oauth2 = mock_join_oauth(email='taken@example.com')
        with client.session_transaction() as sess:
            sess['org_invite_token'] = 'other-org-tok'
        with patch('app.org.routes.build_oauth_flow', return_value=mock_flow), \
             patch('app.org.routes.build', return_value=mock_oauth2):
            response = client.get('/org/join-callback?code=fake')
        assert response.status_code == 400
        assert 'another org' in response.json['error']

    def test_valid_callback_creates_user_and_member(self, client, app, org_with_owner):
        make_invite(app, org_with_owner, token='good-tok', email='newbie@example.com')
        mock_flow, mock_oauth2 = mock_join_oauth(email='newbie@example.com')
        mock_cal = MagicMock()
        mock_cal.acl.return_value.insert.return_value.execute.return_value = {}
        with client.session_transaction() as sess:
            sess['org_invite_token'] = 'good-tok'
        with patch('app.org.routes.build_oauth_flow', return_value=mock_flow), \
             patch('app.org.routes.build', side_effect=[mock_oauth2, mock_cal]):
            response = client.get('/org/join-callback?code=fake')
        assert response.status_code == 200
        assert 'token' in response.json
        with app.app_context():
            user = User.query.filter_by(email='newbie@example.com').first()
            assert user is not None
            member = OrganizationMember.query.filter_by(user_id=user.id).first()
            assert member is not None
            assert member.org_id == org_with_owner
            assert OrganizationInvite.query.filter_by(token='good-tok').first() is None

    def test_relink_same_org_updates_credentials(self, client, app, org_with_owner):
        with app.app_context():
            existing = User(email='returning@example.com', token='old', refresh_token='r',
                            token_uri='u', client_id='c', client_secret='s', scopes='sc')
            db.session.add(existing)
            db.session.flush()
            db.session.add(OrganizationMember(org_id=org_with_owner, user_id=existing.id,
                                              role='employee', priority=1))
            db.session.add(OrganizationInvite(
                org_id=org_with_owner, invited_email='returning@example.com',
                token='relink-tok', role='employee', priority=1,
                expires_at=datetime.utcnow() + timedelta(hours=24),
            ))
            db.session.commit()

        mock_flow, mock_oauth2 = mock_join_oauth(email='returning@example.com')
        with client.session_transaction() as sess:
            sess['org_invite_token'] = 'relink-tok'
        with patch('app.org.routes.build_oauth_flow', return_value=mock_flow), \
             patch('app.org.routes.build', return_value=mock_oauth2):
            response = client.get('/org/join-callback?code=fake')
        assert response.status_code == 200
        with app.app_context():
            user = User.query.filter_by(email='returning@example.com').first()
            assert user.token == 'gtoken'
