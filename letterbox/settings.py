"""Central application settings loaded from environment variables."""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    def load_dotenv() -> bool:
        return False


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

load_dotenv()


# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PACKAGE_DIR = os.path.dirname(__file__)
ROOT_DIR = os.path.abspath(os.path.join(PACKAGE_DIR, os.pardir))


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable safely."""
    value = os.environ.get(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def split_csv(value: str) -> list[str]:
    """Split a comma-separated environment variable."""
    if not value:
        return []

    return [
        item.strip().lower()
        for item in value.split(",")
        if item.strip()
    ]


def resolve_path(env_name: str, default: str) -> str:
    """Resolve a filesystem path relative to the project root."""
    value = os.environ.get(env_name)

    if not value:
        value = default

    if os.path.isabs(value):
        return os.path.abspath(value)

    return os.path.abspath(
        os.path.join(ROOT_DIR, value)
    )


# ---------------------------------------------------------------------------
# Database / storage
# ---------------------------------------------------------------------------

DB_PATH = resolve_path(
    "DB_PATH",
    "database.db",
)

DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or f"sqlite:///{DB_PATH.replace(os.sep, '/')}"
)


# ---------------------------------------------------------------------------
# Application directories
# ---------------------------------------------------------------------------

QR_DIR = resolve_path(
    "QR_DIR",
    "static/qr_codes",
)

BARCODE_DIR = resolve_path(
    "BARCODE_DIR",
    "static/barcodes",
)

GEN_DIR = resolve_path(
    "GEN_DIR",
    "instance/generated_letters",
)

SIGNATURE_DIR = resolve_path(
    "SIGNATURE_DIR",
    "instance/signatures",
)

SENT_DIR = resolve_path(
    "SENT_DIR",
    "sent_emails",
)

MAX_SIGNATURE_SIZE = 2 * 1024 * 1024

AI_OLLAMA_URL = os.environ.get(
    "AI_OLLAMA_URL",
    "http://localhost:11434/api/generate",
).strip()
AI_MODEL = os.environ.get("AI_MODEL", "qwen2.5:1.5b-instruct").strip()
AI_TIMEOUT = int(os.environ.get("AI_TIMEOUT", "45"))
AI_MAX_BODY_LENGTH = int(os.environ.get("AI_MAX_BODY_LENGTH", "1000"))
AI_MAX_SUBJECT_LENGTH = int(os.environ.get("AI_MAX_SUBJECT_LENGTH", "120"))


# ---------------------------------------------------------------------------
# Application URL
# ---------------------------------------------------------------------------

APP_BASE_URL = os.environ.get(
    "APP_BASE_URL",
    "",
).rstrip("/")


# ---------------------------------------------------------------------------
# Institution information
# ---------------------------------------------------------------------------

INSTITUTE_NAME = os.environ.get(
    "INSTITUTE_NAME",
    "Institute Letterbox System",
)

DEPARTMENT_TITLE = os.environ.get(
    "DEPARTMENT_TITLE",
    "Department of Electronics Engineering",
)

CAMPUS_TITLE = os.environ.get(
    "CAMPUS_TITLE",
    "MIT Campus - Anna University",
)

CITY_TITLE = os.environ.get(
    "CITY_TITLE",
    "Chennai",
)

LETTER_HEADING = os.environ.get(
    "LETTER_HEADING",
    "Dept of Electronics Engineering",
)


# ---------------------------------------------------------------------------
# Student registration / email restrictions
# ---------------------------------------------------------------------------

ALLOWED_EMAIL_DOMAINS = set(
    split_csv(
        os.environ.get(
            "INSTITUTE_EMAIL_DOMAINS",
            "",
        )
    )
)

ALLOW_STUDENT_SELF_SIGNUP = env_bool(
    "ALLOW_STUDENT_SELF_SIGNUP",
    True,
)

SEED_DEMO_USERS = env_bool(
    "SEED_DEMO_USERS",
    False,
)


# ---------------------------------------------------------------------------
# Initial staff / admin account
#
# Supports both:
#
# INITIAL_STAFF_*
# INITIAL_ADMIN_*
# ---------------------------------------------------------------------------

INITIAL_STAFF_USERNAME = os.environ.get(
    "INITIAL_STAFF_USERNAME",
    os.environ.get(
        "INITIAL_ADMIN_USERNAME",
        "",
    ),
).strip().lower()

INITIAL_STAFF_PASSWORD = os.environ.get(
    "INITIAL_STAFF_PASSWORD",
    os.environ.get(
        "INITIAL_ADMIN_PASSWORD",
        "",
    ),
)

INITIAL_STAFF_NAME = os.environ.get(
    "INITIAL_STAFF_NAME",
    os.environ.get(
        "INITIAL_ADMIN_NAME",
        "Institute Staff",
    ),
)

INITIAL_STAFF_EMAIL = os.environ.get(
    "INITIAL_STAFF_EMAIL",
    os.environ.get(
        "INITIAL_ADMIN_EMAIL",
        "",
    ),
).strip().lower()


# Backward-compatible aliases.
INITIAL_ADMIN_USERNAME = INITIAL_STAFF_USERNAME
INITIAL_ADMIN_PASSWORD = INITIAL_STAFF_PASSWORD
INITIAL_ADMIN_NAME = INITIAL_STAFF_NAME
INITIAL_ADMIN_EMAIL = INITIAL_STAFF_EMAIL


# ---------------------------------------------------------------------------
# Staff / admin access key
# ---------------------------------------------------------------------------

STAFF_ACCESS_KEY = (
    os.environ.get(
        "ADMIN_ACCESS_KEY",
        "",
    ).strip()
    or os.environ.get(
        "STAFF_ACCESS_KEY",
        "",
    ).strip()
)

ADMIN_ACCESS_KEY = STAFF_ACCESS_KEY


# ---------------------------------------------------------------------------
# Flask security
# ---------------------------------------------------------------------------

SECRET_KEY = (
    os.environ.get("FLASK_SECRET")
    or os.environ.get("SECRET_KEY")
    or "change-me-in-production"
)

FLASK_SECRET = SECRET_KEY

SESSION_COOKIE_SECURE = env_bool(
    "SESSION_COOKIE_SECURE",
    False,
)

SESSION_COOKIE_HTTPONLY = env_bool(
    "SESSION_COOKIE_HTTPONLY",
    True,
)

SESSION_COOKIE_SAMESITE = os.environ.get(
    "SESSION_COOKIE_SAMESITE",
    "Lax",
)

SESSION_HOURS = int(
    os.environ.get(
        "SESSION_HOURS",
        "8",
    )
)

SESSION_IDLE_MINUTES = int(
    os.environ.get(
        "SESSION_IDLE_MINUTES",
        "5",
    )
)


# ---------------------------------------------------------------------------
# Flask application behaviour
# ---------------------------------------------------------------------------

APP_ENV = os.environ.get(
    "APP_ENV",
    "production",
).strip().lower()

FLASK_DEBUG = env_bool(
    "FLASK_DEBUG",
    APP_ENV == "development",
)

PREFERRED_URL_SCHEME = os.environ.get(
    "PREFERRED_URL_SCHEME",
    "https" if SESSION_COOKIE_SECURE else "http",
)

PORT = int(
    os.environ.get(
        "PORT",
        "5000",
    )
)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_LEVEL = os.environ.get(
    "LOG_LEVEL",
    "INFO",
).strip().upper()


# ---------------------------------------------------------------------------
# Email / Mailjet v3.1 HTTP API
# ---------------------------------------------------------------------------

MAILJET_API_KEY = os.environ.get("MAILJET_API_KEY", "").strip()
MAILJET_SECRET_KEY = os.environ.get("MAILJET_SECRET_KEY", "").strip()
MAILJET_SENDER_EMAIL = os.environ.get("MAILJET_SENDER_EMAIL", "").strip()
MAILJET_API_URL = "https://api.mailjet.com/v3.1/send"

MAILJET_TIMEOUT = int(
    os.environ.get(
        "MAILJET_TIMEOUT",
        "15",
    )
)



# ---------------------------------------------------------------------------
# Optional SMS notifications (Twilio REST API)
# ---------------------------------------------------------------------------

TWILIO_ACCOUNT_SID = os.environ.get(
    "TWILIO_ACCOUNT_SID",
    "",
).strip()

TWILIO_AUTH_TOKEN = os.environ.get(
    "TWILIO_AUTH_TOKEN",
    "",
).strip()

TWILIO_FROM_NUMBER = os.environ.get(
    "TWILIO_FROM_NUMBER",
    "",
).strip()

SMS_DEFAULT_COUNTRY_CODE = os.environ.get(
    "SMS_DEFAULT_COUNTRY_CODE",
    "+91",
).strip()

SMS_ENABLED = env_bool(
    "SMS_ENABLED",
    bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER),
)

SMS_TIMEOUT = int(os.environ.get("SMS_TIMEOUT", "15"))


# ---------------------------------------------------------------------------
# Google reCAPTCHA v2
# ---------------------------------------------------------------------------

RECAPTCHA_ENABLED = env_bool(
    "RECAPTCHA_ENABLED",
    False,
)

RECAPTCHA_SITE_KEY = os.environ.get(
    "RECAPTCHA_SITE_KEY",
    "",
).strip()

RECAPTCHA_SECRET_KEY = os.environ.get(
    "RECAPTCHA_SECRET_KEY",
    "",
).strip()


# ---------------------------------------------------------------------------
# ESP32 configuration
# ---------------------------------------------------------------------------

ESP_TOKEN = os.environ.get(
    "ESP_TOKEN",
    "",
).strip()

ESP32_HOST = os.environ.get(
    "ESP32_HOST",
    "",
).strip()

ESP_INBOX_DEVICE_ID = os.environ.get(
    "ESP_INBOX_DEVICE_ID",
    "",
).strip().lower()

ESP_OUTBOX_DEVICE_ID = os.environ.get(
    "ESP_OUTBOX_DEVICE_ID",
    "",
).strip().lower()


# ---------------------------------------------------------------------------
# Status values
# ---------------------------------------------------------------------------

STATUS_CREATED = "Created"
STATUS_SUBMITTED = "Submitted"
STATUS_PENDING = "Pending"
STATUS_APPROVED = "Approved"

VALID_STATUSES = {
    STATUS_CREATED,
    STATUS_SUBMITTED,
    STATUS_PENDING,
    STATUS_APPROVED,
}

STATUS_FLOW = {
    STATUS_CREATED: {
        STATUS_SUBMITTED,
        STATUS_PENDING,
        STATUS_APPROVED,
    },
    STATUS_SUBMITTED: {
        STATUS_PENDING,
        STATUS_APPROVED,
    },
    STATUS_PENDING: {
        STATUS_APPROVED,
    },
    STATUS_APPROVED: set(),
}


# ---------------------------------------------------------------------------
# Letter configuration
# ---------------------------------------------------------------------------

MAX_LETTER_DESCRIPTION_LENGTH = 500

LETTER_FIELDS = """
    app_id,
    name,
    email,
    phone,
    subject,
    description,
    status,
    created_at,
    submitted_at,
    approved_at
"""
