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
