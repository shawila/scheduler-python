import pytest
from app import create_app
from app.extensions import db as _db
from app.models.customer import Customer


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
        customer = Customer(
            email='store@example.com',
            token='fake-token',
            refresh_token='fake-refresh-token',
            token_uri='https://oauth2.googleapis.com/token',
            client_id='fake-client-id',
            client_secret='fake-client-secret',
            scopes='https://www.googleapis.com/auth/calendar',
        )
        _db.session.add(customer)
        _db.session.commit()
        yield customer
