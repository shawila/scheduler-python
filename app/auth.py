from functools import wraps
from flask import request, jsonify, g
from app.models.user import User


def generate_auth_url():
    from app.google_calendar import build_oauth_flow
    flow = build_oauth_flow()
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
    )
    return auth_url


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.removeprefix('Bearer ').strip()
        user = User.query.filter_by(api_token=token).first() if token else None
        if not user:
            return jsonify({'error': 'Unauthorized', 'auth_url': generate_auth_url()}), 401
        g.current_user = user
        return f(*args, **kwargs)
    return decorated
