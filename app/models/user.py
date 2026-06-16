from app.extensions import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    token = db.Column(db.String(500), nullable=False)
    refresh_token = db.Column(db.String(500), nullable=False)
    token_uri = db.Column(db.String(200), nullable=False)
    client_id = db.Column(db.String(200), nullable=False)
    client_secret = db.Column(db.String(200), nullable=False)
    scopes = db.Column(db.Text, nullable=False)
    api_token = db.Column(db.String(100), unique=True, nullable=True)

    def __repr__(self):
        return f'<User {self.email}>'

