from unittest.mock import patch, MagicMock
from app.models.user import User
from app.extensions import db


def make_mock_oauth(email='admin@example.com'):
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


class TestCallback:
    def test_callback_returns_bearer_token(self, client):
        mock_flow, mock_oauth2 = make_mock_oauth()
        with patch('app.main.routes.build_oauth_flow', return_value=mock_flow), \
             patch('app.main.routes.build', return_value=mock_oauth2):
            response = client.get('/callback?code=fake&state=fake')
        assert response.status_code == 200
        assert 'token' in response.json
        assert len(response.json['token']) > 10

    def test_callback_stores_api_token_on_user(self, client, app):
        mock_flow, mock_oauth2 = make_mock_oauth()
        with patch('app.main.routes.build_oauth_flow', return_value=mock_flow), \
             patch('app.main.routes.build', return_value=mock_oauth2):
            response = client.get('/callback?code=fake&state=fake')
        with app.app_context():
            user = User.query.filter_by(email='admin@example.com').first()
            assert user is not None
            assert user.api_token == response.json['token']

    def test_index_route_removed(self, client):
        response = client.get('/')
        assert response.status_code == 404


class TestRequireAuth:
    def test_missing_token_returns_401_with_auth_url(self, client):
        with patch('app.auth.generate_auth_url', return_value='https://accounts.google.com/mock'):
            response = client.post('/org/register', json={'org_name': 'Test'})
        assert response.status_code == 401
        assert 'auth_url' in response.json
        assert response.json['auth_url'] == 'https://accounts.google.com/mock'

    def test_invalid_token_returns_401(self, client):
        with patch('app.auth.generate_auth_url', return_value='https://mock'):
            response = client.post(
                '/org/register',
                json={'org_name': 'Test'},
                headers={'Authorization': 'Bearer invalid-token'},
            )
        assert response.status_code == 401

    def test_valid_token_passes_through(self, client, app):
        with app.app_context():
            user = User(
                email='auth@example.com', token='t', refresh_token='r',
                token_uri='u', client_id='c', client_secret='s', scopes='sc',
                api_token='valid-token',
            )
            db.session.add(user)
            db.session.commit()
        with patch('app.org.routes.build') as mock_build:
            mock_build.return_value.calendars().insert().execute.return_value = {'id': 'cal-id'}
            mock_build.return_value.acl().insert().execute.return_value = {}
            response = client.post(
                '/org/register',
                json={'org_name': 'Test'},
                headers={'Authorization': 'Bearer valid-token'},
            )
        assert response.status_code == 201
