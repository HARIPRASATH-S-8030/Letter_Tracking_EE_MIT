"""Central application settings loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path


PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable with a safe default."""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def split_csv(value: str) -> list[str]:
    """Split a comma-separated environment variable into normalized values."""
    if not value:
        return []
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def resolve_path(env_name: str, default: str) -> str:
    """Resolve a filesystem path relative to the project root when needed."""
    raw_value = os.environ.get(env_name, default)
    path = Path(raw_value)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return str(path.resolve())


def normalize_database_url(value: str | None) -> str:
    """Normalize database URLs for SQLAlchemy compatibility."""
    if value:
        value = value.strip()
        if value.startswith("postgres://"):
            return "postgresql://" + value[len("postgres://") :]
        return value
    sqlite_path = resolve_path("DB_PATH", "database.db")
    normalized_path = sqlite_path.replace("\\", "/")
    return f"sqlite:///{normalized_path}"


APP_ENV = os.environ.get("APP_ENV", os.environ.get("FLASK_ENV", "development")).strip().lower()
RUNNING_ON_RENDER = env_bool("RENDER", False)
IS_PRODUCTION = APP_ENV == "production" or RUNNING_ON_RENDER

DATABASE_URL = normalize_database_url(os.environ.get("DATABASE_URL"))
QR_DIR = resolve_path("QR_DIR", "static/qr_codes")
BARCODE_DIR = resolve_path("BARCODE_DIR", "static/barcodes")
GEN_DIR = resolve_path("GEN_DIR", "static/generated_letters")
SENT_DIR = resolve_path("SENT_DIR", "sent_emails")
APP_BASE_URL = os.environ.get("APP_BASE_URL", os.environ.get("RENDER_EXTERNAL_URL", "")).rstrip("/")

INSTITUTE_NAME = os.environ.get("INSTITUTE_NAME", "Institute Letterbox System")
DEPARTMENT_TITLE = os.environ.get("DEPARTMENT_TITLE", "Department of Electronics Engineering")
CAMPUS_TITLE = os.environ.get("CAMPUS_TITLE", "MIT Campus - Anna University")
CITY_TITLE = os.environ.get("CITY_TITLE", "Chennai")
LETTER_HEADING = os.environ.get("LETTER_HEADING", "Dept of Electronics Engineering")

ALLOWED_EMAIL_DOMAINS = set(split_csv(os.environ.get("INSTITUTE_EMAIL_DOMAINS", "")))
ALLOW_STUDENT_SELF_SIGNUP = env_bool("ALLOW_STUDENT_SELF_SIGNUP", True)
SEED_DEMO_USERS = env_bool("SEED_DEMO_USERS", False)

INITIAL_ADMIN_USERNAME = os.environ.get("INITIAL_ADMIN_USERNAME", "").strip().lower()
INITIAL_ADMIN_PASSWORD = os.environ.get("INITIAL_ADMIN_PASSWORD", "")
INITIAL_ADMIN_NAME = os.environ.get("INITIAL_ADMIN_NAME", "Institute Admin")
INITIAL_ADMIN_EMAIL = os.environ.get("INITIAL_ADMIN_EMAIL", "").strip().lower()

INITIAL_STAFF_USERNAME = os.environ.get("INITIAL_STAFF_USERNAME", "").strip().lower()
INITIAL_STAFF_PASSWORD = os.environ.get("INITIAL_STAFF_PASSWORD", "")
INITIAL_STAFF_NAME = os.environ.get("INITIAL_STAFF_NAME", "Institute Staff")
INITIAL_STAFF_EMAIL = os.environ.get("INITIAL_STAFF_EMAIL", "").strip().lower()
STAFF_ACCESS_KEY = (os.environ.get("ADMIN_ACCESS_KEY", "").strip() or os.environ.get("STAFF_ACCESS_KEY", "").strip())

SECRET_KEY = os.environ.get("SECRET_KEY", "").strip() or "change-me-in-production"
SESSION_HOURS = int(os.environ.get("SESSION_HOURS", "8"))
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", IS_PRODUCTION)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "Lax")
PREFERRED_URL_SCHEME = os.environ.get("PREFERRED_URL_SCHEME", "https" if IS_PRODUCTION else "http")
FLASK_DEBUG = env_bool("FLASK_DEBUG", False)
PORT = int(os.environ.get("PORT", "5000"))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

RECAPTCHA_SITE_KEY = os.environ.get("RECAPTCHA_SITE_KEY", "").strip()
RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY", "").strip()
RECAPTCHA_ENABLED = bool(RECAPTCHA_SITE_KEY and RECAPTCHA_SECRET_KEY)

ESP_INBOX_DEVICE_ID = os.environ.get("ESP_INBOX_DEVICE_ID", "").strip()
ESP_OUTBOX_DEVICE_ID = os.environ.get("ESP_OUTBOX_DEVICE_ID", "").strip()

STATUS_CREATED = "Created"
STATUS_SUBMITTED = "Submitted"
STATUS_PENDING = "Pending"
STATUS_APPROVED = "Approved"
VALID_STATUSES = {STATUS_CREATED, STATUS_SUBMITTED, STATUS_PENDING, STATUS_APPROVED}
STATUS_FLOW = {
    STATUS_CREATED: {STATUS_SUBMITTED, STATUS_PENDING, STATUS_APPROVED},
    STATUS_SUBMITTED: {STATUS_PENDING, STATUS_APPROVED},
    STATUS_PENDING: {STATUS_APPROVED},
    STATUS_APPROVED: set(),
}

MAX_LETTER_DESCRIPTION_LENGTH = 500
