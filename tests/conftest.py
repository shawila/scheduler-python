import pytest
from app import create_app
from app.extensions import db as _db
from app.models.user import User


@pytest.fixture
def app():
    test_app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'MAIL_SUPPRESS_SEND': True,
        'WTF_CSRF_ENABLED': False,
    })
    with test_app.app_context():
        _db.create_all()
        yield test_app
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def store(app):
    with app.app_context():
        user = User(
            email='store@example.com',
            token='fake-token',
            refresh_token='fake-refresh-token',
            token_uri='https://oauth2.googleapis.com/token',
            client_id='fake-client-id',
            client_secret='fake-client-secret',
            scopes='https://www.googleapis.com/auth/calendar',
        )
        _db.session.add(user)
        _db.session.commit()
        yield user


@pytest.fixture
def authed_user(app):
    with app.app_context():
        user = User(
            email='owner@example.com',
            token='gtoken', refresh_token='rtoken',
            token_uri='https://oauth2.googleapis.com/token',
            client_id='cid', client_secret='csecret',
            scopes='https://www.googleapis.com/auth/calendar',
            api_token='owner-api-token',
        )
        _db.session.add(user)
        _db.session.commit()
        _db.session.refresh(user)
        _db.session.expunge(user)
        return user


@pytest.fixture
def org_with_owner(app, authed_user):
    from app.models.organization import Organization
    from app.models.organization_member import OrganizationMember
    with app.app_context():
        org = Organization(name='Test Org', google_calendar_id='org-cal-id')
        _db.session.add(org)
        _db.session.flush()
        member = OrganizationMember(
            org_id=org.id,
            user_id=authed_user.id,
            role='owner',
            priority=1,
        )
        _db.session.add(member)
        _db.session.commit()
        return org.id
