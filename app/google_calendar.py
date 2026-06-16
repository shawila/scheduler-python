from google.oauth2.credentials import Credentials
from app.models.user import User


def credentials_from_user(user: User) -> Credentials:
    return Credentials(
        token=user.token,
        refresh_token=user.refresh_token,
        token_uri=user.token_uri,
        client_id=user.client_id,
        client_secret=user.client_secret,
        scopes=user.scopes.split(','),
    )
