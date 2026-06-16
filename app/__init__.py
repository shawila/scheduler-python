from flask import Flask
from flask_migrate import Migrate
from app.config import Config
from app.extensions import db, mail
from app.main.routes import main_bp


def create_app(config_override=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_override:
        app.config.update(config_override)

    db.init_app(app)
    mail.init_app(app)
    Migrate(app, db)

    app.register_blueprint(main_bp)

    from app.booking.routes import booking_bp
    app.register_blueprint(booking_bp)

    with app.app_context():
        db.create_all()

    return app
