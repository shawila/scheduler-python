from flask import Flask
from flask_migrate import Migrate
from app.config import Config
from app.extensions import db
from app.main.routes import main_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)

    # Register blueprints
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()

    return app

