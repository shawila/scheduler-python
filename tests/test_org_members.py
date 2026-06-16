from unittest.mock import patch
from app.models.organization_member import OrganizationMember
from app.models.user import User
from app.extensions import db

OWNER_TOKEN = 'owner-api-token'


def auth(token=OWNER_TOKEN):
    return {'Authorization': f'Bearer {token}'}


def make_member(app, org_id, email, role, priority=1, api_token=None):
    with app.app_context():
        user = User(
            email=email, token='t', refresh_token='r',
            token_uri='u', client_id='c', client_secret='s', scopes='sc',
            api_token=api_token,
        )
        db.session.add(user)
        db.session.flush()
        db.session.add(OrganizationMember(org_id=org_id, user_id=user.id,
                                          role=role, priority=priority))
        db.session.commit()
        return user.id


class TestUpdateMember:
    def test_unauthenticated_returns_401(self, client, org_with_owner):
        with patch('app.auth.generate_auth_url', return_value='https://mock'):
            response = client.put(f'/org/{org_with_owner}/users/1', json={'role': 'manager'})
        assert response.status_code == 401

    def test_target_not_in_org_returns_404(self, client, authed_user, org_with_owner):
        response = client.put(f'/org/{org_with_owner}/users/99999',
                              json={'role': 'manager'},
                              headers=auth())
        assert response.status_code == 404

    def test_owner_can_promote_employee_to_manager(self, client, app, authed_user, org_with_owner):
        target_id = make_member(app, org_with_owner, 'emp@x.com', 'employee')
        response = client.put(f'/org/{org_with_owner}/users/{target_id}',
                              json={'role': 'manager'},
                              headers=auth())
        assert response.status_code == 200
        with app.app_context():
            assert OrganizationMember.query.filter_by(user_id=target_id).first().role == 'manager'

    def test_owner_can_promote_manager_to_owner(self, client, app, authed_user, org_with_owner):
        target_id = make_member(app, org_with_owner, 'mgr@x.com', 'manager')
        response = client.put(f'/org/{org_with_owner}/users/{target_id}',
                              json={'role': 'owner'},
                              headers=auth())
        assert response.status_code == 200
        with app.app_context():
            assert OrganizationMember.query.filter_by(user_id=target_id).first().role == 'owner'

    def test_owner_can_demote_owner_to_employee(self, client, app, authed_user, org_with_owner):
        target_id = make_member(app, org_with_owner, 'owner2@x.com', 'owner')
        response = client.put(f'/org/{org_with_owner}/users/{target_id}',
                              json={'role': 'employee'},
                              headers=auth())
        assert response.status_code == 200

    def test_owner_can_update_priority(self, client, app, authed_user, org_with_owner):
        target_id = make_member(app, org_with_owner, 'emp2@x.com', 'employee')
        response = client.put(f'/org/{org_with_owner}/users/{target_id}',
                              json={'priority': 5},
                              headers=auth())
        assert response.status_code == 200
        with app.app_context():
            assert OrganizationMember.query.filter_by(user_id=target_id).first().priority == 5

    def test_manager_can_update_employee_priority(self, client, app, authed_user, org_with_owner):
        with app.app_context():
            OrganizationMember.query.filter_by(user_id=authed_user.id).first().role = 'manager'
            db.session.commit()
        target_id = make_member(app, org_with_owner, 'emp3@x.com', 'employee')
        response = client.put(f'/org/{org_with_owner}/users/{target_id}',
                              json={'priority': 3},
                              headers=auth())
        assert response.status_code == 200

    def test_manager_cannot_update_manager_returns_403(self, client, app, authed_user, org_with_owner):
        with app.app_context():
            OrganizationMember.query.filter_by(user_id=authed_user.id).first().role = 'manager'
            db.session.commit()
        target_id = make_member(app, org_with_owner, 'mgr2@x.com', 'manager')
        response = client.put(f'/org/{org_with_owner}/users/{target_id}',
                              json={'priority': 3},
                              headers=auth())
        assert response.status_code == 403

    def test_manager_cannot_assign_manager_role_returns_403(self, client, app, authed_user, org_with_owner):
        with app.app_context():
            OrganizationMember.query.filter_by(user_id=authed_user.id).first().role = 'manager'
            db.session.commit()
        target_id = make_member(app, org_with_owner, 'emp4@x.com', 'employee')
        response = client.put(f'/org/{org_with_owner}/users/{target_id}',
                              json={'role': 'manager'},
                              headers=auth())
        assert response.status_code == 403

    def test_employee_cannot_update_role_returns_403(self, client, app, authed_user, org_with_owner):
        with app.app_context():
            OrganizationMember.query.filter_by(user_id=authed_user.id).first().role = 'employee'
            db.session.commit()
        response = client.put(f'/org/{org_with_owner}/users/{authed_user.id}',
                              json={'role': 'manager'},
                              headers=auth())
        assert response.status_code == 403

    def test_employee_cannot_update_priority_returns_403(self, client, app, authed_user, org_with_owner):
        with app.app_context():
            OrganizationMember.query.filter_by(user_id=authed_user.id).first().role = 'employee'
            db.session.commit()
        response = client.put(f'/org/{org_with_owner}/users/{authed_user.id}',
                              json={'priority': 5},
                              headers=auth())
        assert response.status_code == 403
