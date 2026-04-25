"""Application package entry point and Flask app factory."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template, request, session, url_for
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from . import settings
from .database import init_db
from .extensions import csrf, db
from .routes_auth import register_auth_routes
from .routes_staff import register_staff_routes
from .routes_student import register_student_routes

BASE_DIR = Path(__file__).resolve().parent.parent


def configure_logging(app: Flask) -> None:
    """Send structured application logs to stdout for local runs and cloud hosts."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    app.logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))


def register_error_handlers(app: Flask) -> None:
    """Register user-friendly error pages and JSON fallbacks."""

    def wants_json() -> bool:
        return request.path.startswith("/esp_") or request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest"

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error: CSRFError):
        message = "Security validation failed. Refresh the page and try again."
        if wants_json():
            return jsonify({"status": "error", "message": message}), 400
        return render_template("success.html", message=message, app_id="", name=session.get("name", "")), 400

    @app.errorhandler(400)
    def handle_bad_request(error):
        if wants_json():
            return jsonify({"status": "error", "message": "Bad request."}), 400
        return render_template("success.html", message="Bad request.", app_id="", name=session.get("name", "")), 400

    @app.errorhandler(403)
    def handle_forbidden(error):
        if wants_json():
            return jsonify({"status": "error", "message": "You do not have permission to access this resource."}), 403
        return render_template(
            "success.html",
            message="You do not have permission to access this resource.",
            app_id="",
            name=session.get("name", ""),
        ), 403

    @app.errorhandler(404)
    def handle_not_found(error):
        if wants_json():
            return jsonify({"status": "error", "message": "Requested resource was not found."}), 404
        return render_template("success.html", message="Requested resource was not found.", app_id="", name=session.get("name", "")), 404

    @app.errorhandler(500)
    def handle_server_error(error):
        app.logger.exception("Unhandled server error: %s", error)
        if wants_json():
            return jsonify({"status": "error", "message": "Internal server error."}), 500
        return render_template("success.html", message="Internal server error.", app_id="", name=session.get("name", "")), 500


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
        static_url_path="/static",
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    app.config.update(
        SECRET_KEY=settings.SECRET_KEY,
        SQLALCHEMY_DATABASE_URI=settings.DATABASE_URL,
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SESSION_COOKIE_HTTPONLY=settings.SESSION_COOKIE_HTTPONLY,
        SESSION_COOKIE_SAMESITE=settings.SESSION_COOKIE_SAMESITE,
        SESSION_COOKIE_SECURE=settings.SESSION_COOKIE_SECURE,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=settings.SESSION_HOURS),
        PREFERRED_URL_SCHEME=settings.PREFERRED_URL_SCHEME,
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        WTF_CSRF_TIME_LIMIT=3600,
    )

    configure_logging(app)
    db.init_app(app)
    csrf.init_app(app)

    IST_ZONE = ZoneInfo("Asia/Kolkata")

    def format_datetime_ist(value):
        if value is None:
            return ""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(IST_ZONE).strftime("%d %b %Y %I:%M %p %Z")

    app.jinja_env.filters["ist_datetime"] = format_datetime_ist
    app.jinja_env.filters["localtime"] = format_datetime_ist

    @app.context_processor
    def inject_branding():
        anna_file = "anna-university.png" if (BASE_DIR / "static" / "anna-university.png").exists() else "anna-placeholder.svg"
        mit_file = "mit.png" if (BASE_DIR / "static" / "mit.png").exists() else "mit-placeholder.svg"
        return {
            "institute_name": settings.INSTITUTE_NAME,
            "department_title": settings.DEPARTMENT_TITLE,
            "campus_title": settings.CAMPUS_TITLE,
            "city_title": settings.CITY_TITLE,
            "anna_logo_url": url_for("static", filename=anna_file),
            "mit_logo_url": url_for("static", filename=mit_file),
            "recaptcha_enabled": settings.RECAPTCHA_ENABLED,
            "recaptcha_site_key": settings.RECAPTCHA_SITE_KEY,
        }

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    with app.app_context():
        init_db()

    register_error_handlers(app)
    register_auth_routes(app)
    register_staff_routes(app)
    register_student_routes(app)
    return app


def run_dev_server() -> None:
    """Start the local development server with helpful deployment warnings."""
    if app.config["SECRET_KEY"] == "change-me-in-production":
        app.logger.warning("Using the default secret key. Set SECRET_KEY before deploying publicly.")
    if not settings.STAFF_ACCESS_KEY:
        app.logger.warning("ADMIN_ACCESS_KEY / STAFF_ACCESS_KEY is not set. Staff login key protection is disabled.")
    app.run(debug=settings.FLASK_DEBUG, host="0.0.0.0", port=settings.PORT)


app = create_app()
