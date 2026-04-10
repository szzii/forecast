from flask import Flask

from .config import Config
from .database_bootstrap import ensure_database_exists, ensure_prediction_record_columns
from .extensions import db
from .routes import register_blueprints
from .services.auto_collection_service import ensure_scheduler_started
from .services.collection_queue_service import ensure_collection_queue_started


def _enable_wal_mode(app):
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if not uri.startswith("sqlite"):
        return
    from sqlalchemy import text
    db.session.execute(text("PRAGMA journal_mode=WAL"))
    db.session.execute(text("PRAGMA synchronous=NORMAL"))
    db.session.commit()


def create_app(config_class=Config):
    app = Flask(__name__, static_folder="../static", template_folder="../templates")
    app.config.from_object(config_class)
    ensure_database_exists(app.config.get("SQLALCHEMY_DATABASE_URI"))

    db.init_app(app)
    register_blueprints(app)

    with app.app_context():
        db.create_all()
        ensure_prediction_record_columns(app.config.get("SQLALCHEMY_DATABASE_URI"))
        _enable_wal_mode(app)
        ensure_scheduler_started(app)
        ensure_collection_queue_started()

    return app
