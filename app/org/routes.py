import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session, redirect, g
from googleapiclient.discovery import build
from app.extensions import db
from app.models.organization import Organization
from app.models.organization_member import OrganizationMember
from app.models.organization_invite import OrganizationInvite
from app.models.user import User
from app.google_calendar import credentials_from_user, build_oauth_flow, INVITE_REDIRECT_URI
from app.auth import require_auth
from app.org.email import send_invite_email

org_bp = Blueprint('org', __name__, url_prefix='/org')

ROLE_RANK = {'employee': 1, 'manager': 2, 'owner': 3}


@org_bp.route('/register', methods=['POST'])
@require_auth
def register_org():
    data = request.get_json() or {}
    org_name = data.get('org_name', '').strip()
    if not org_name:
        return jsonify({'error': 'org_name is required'}), 400

    if OrganizationMember.query.filter_by(user_id=g.current_user.id).first():
        return jsonify({'error': 'Already belong to an org'}), 400

    credentials = credentials_from_user(g.current_user)
    service = build('calendar', 'v3', credentials=credentials)

    calendar = service.calendars().insert(body={'summary': org_name}).execute()
    calendar_id = calendar['id']

    service.acl().insert(
        calendarId=calendar_id,
        body={'role': 'owner', 'scope': {'type': 'user', 'value': g.current_user.email}},
    ).execute()

    org = Organization(name=org_name, google_calendar_id=calendar_id)
    db.session.add(org)
    db.session.flush()

    member = OrganizationMember(org_id=org.id, user_id=g.current_user.id, role='owner', priority=1)
    db.session.add(member)
    db.session.commit()

    return jsonify({'org_id': org.id, 'calendar_id': org.google_calendar_id}), 201


@org_bp.route('/<int:org_uid>/invite', methods=['POST'])
@require_auth
def invite_member(org_uid):
    data = request.get_json() or {}
    invitee_email = data.get('invitee_email', '').strip()
    role = data.get('role', 'employee')
    priority = int(data.get('priority', 1))

    if not invitee_email:
        return jsonify({'error': 'invitee_email is required'}), 400

    if role not in ROLE_RANK:
        return jsonify({'error': 'role must be owner, manager, or employee'}), 400

    actor_member = OrganizationMember.query.filter_by(
        user_id=g.current_user.id, org_id=org_uid
    ).first()
    if not actor_member:
        return jsonify({'error': 'Not a member of this org'}), 403

    if ROLE_RANK[actor_member.role] < ROLE_RANK['manager']:
        return jsonify({'error': 'Only managers and owners can invite members'}), 403

    if actor_member.role == 'manager' and role != 'employee':
        return jsonify({'error': 'Managers can only invite employees'}), 403

    existing_user = User.query.filter_by(email=invitee_email).first()
    if existing_user and OrganizationMember.query.filter_by(user_id=existing_user.id).first():
        return jsonify({'error': 'User already belongs to an org'}), 400

    existing_invite = OrganizationInvite.query.filter_by(
        org_id=org_uid, invited_email=invitee_email
    ).first()
    if existing_invite:
        if existing_invite.expires_at > datetime.utcnow():
            return jsonify({'error': 'Invite already pending for this email'}), 400
        db.session.delete(existing_invite)

    token = secrets.token_urlsafe(32)
    invite = OrganizationInvite(
        org_id=org_uid,
        invited_email=invitee_email,
        token=token,
        role=role,
        priority=priority,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.session.add(invite)
    db.session.commit()

    org = Organization.query.get(org_uid)
    send_invite_email(invitee_email, org.name, org_uid, token)

    return jsonify({'message': f'Invite sent to {invitee_email}'}), 200
