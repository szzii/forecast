from flask import Flask

from .config import Config
from .extensions import db
from .routes import register_blueprints
from .services.auto_collection_service import ensure_scheduler_started


def create_app(config_class=Config):
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    app.config.from_object(config_class)

    db.init_app(app)
    register_blueprints(app)

    with app.app_context():
        db.create_all()

    @app.before_request
    def _bootstrap_scheduler():
        ensure_scheduler_started(app)

    return app
