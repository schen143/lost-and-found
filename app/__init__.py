import os
import secrets

from flask import Flask, abort, request, session
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "info"


def _database_url():
    url = os.environ.get("DATABASE_URL", "sqlite:///lostandfound.db")
    # Heroku/Render hand out postgres:// URLs; SQLAlchemy wants an explicit driver.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
        SQLALCHEMY_DATABASE_URI=_database_url(),
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        AUTO_SEED=os.environ.get("AUTO_SEED", "1") == "1",
        SHOW_DEMO_HINT=os.environ.get("SHOW_DEMO_HINT", "1") == "1",
        ITEMS_PER_PAGE=12,
    )
    if config:
        app.config.update(config)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)
    login_manager.init_app(app)

    from . import models  # noqa: F401  (register models)
    from .auth import bp as auth_bp
    from .items import bp as items_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(items_bp)

    _register_csrf(app)

    from .seed import register_cli, seed_if_empty

    register_cli(app)
    with app.app_context():
        try:
            db.create_all()
            if app.config["AUTO_SEED"]:
                seed_if_empty()
        except SQLAlchemyError:
            # Several servers booting against a fresh database can race here;
            # whichever loses just uses the tables/data the winner created.
            db.session.rollback()
            app.logger.warning("Skipped DB setup; another instance is doing it.", exc_info=True)

    return app


def _register_csrf(app):
    """Minimal CSRF protection: every POST must echo the per-session token."""

    def csrf_token():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_urlsafe(32)
        return session["_csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def check_csrf():
        if app.config.get("TESTING") and not app.config.get("CSRF_IN_TESTS"):
            return
        if request.method == "POST":
            sent = request.form.get("csrf_token", "")
            if not sent or not secrets.compare_digest(sent, session.get("_csrf", "")):
                abort(400, description="Your form expired. Go back, reload the page and try again.")
