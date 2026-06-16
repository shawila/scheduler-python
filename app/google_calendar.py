from google.oauth2.credentials import Credentials
from app.models.customer import Customer


def credentials_from_customer(customer: Customer) -> Credentials:
    return Credentials(
        token=customer.token,
        refresh_token=customer.refresh_token,
        token_uri=customer.token_uri,
        client_id=customer.client_id,
        client_secret=customer.client_secret,
        scopes=customer.scopes.split(','),
    )
