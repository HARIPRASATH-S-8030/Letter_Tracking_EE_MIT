"""Database setup, startup migrations, and seed helpers."""

from __future__ import annotations

import logging
import os

from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

from . import settings
from .extensions import db
from .models import User

logger = logging.getLogger(__name__)


def ensure_dirs() -> None:
    """Create runtime output folders if they do not already exist."""
    for path in (settings.QR_DIR, settings.BARCODE_DIR, settings.GEN_DIR, settings.SIGNATURE_DIR, settings.SENT_DIR):
        os.makedirs(path, exist_ok=True)


def column_exists(table_name: str, column_name: str) -> bool:
    """Check whether a column exists in the current database."""
    inspector = inspect(db.engine)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def ensure_legacy_compatible_schema() -> None:
    """Apply schema updates to support long Base64 strings in PostgreSQL and SQLite."""
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())

    if "users" in table_names:
        if not column_exists("users", "created_at"):
            db.session.execute(text("ALTER TABLE users ADD COLUMN created_at TIMESTAMP"))
        if not column_exists("users", "email"):
            db.session.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL DEFAULT ''"))
        if not column_exists("users", "phone"):
            db.session.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(30)"))
        if not column_exists("users", "signature_file_name"):
            db.session.execute(text("ALTER TABLE users ADD COLUMN signature_file_name TEXT"))
        else:
            try:
                db.session.execute(text("ALTER TABLE users ALTER COLUMN signature_file_name TYPE TEXT"))
            except Exception:
                db.session.rollback()

    if "letters" in table_names:
        if not column_exists("letters", "generated_file_name"):
            db.session.execute(text("ALTER TABLE letters ADD COLUMN generated_file_name VARCHAR(255)"))
        if not column_exists("letters", "qr_file_name"):
            db.session.execute(text("ALTER TABLE letters ADD COLUMN qr_file_name VARCHAR(255)"))
        if not column_exists("letters", "signature_file_name"):
            db.session.execute(text("ALTER TABLE letters ADD COLUMN signature_file_name TEXT"))
        else:
            try:
                db.session.execute(text("ALTER TABLE letters ALTER COLUMN signature_file_name TYPE TEXT"))
            except Exception:
                db.session.rollback()
        if not column_exists("letters", "generation_mode"):
            db.session.execute(text("ALTER TABLE letters ADD COLUMN generation_mode VARCHAR(10) NOT NULL DEFAULT 'manual'"))
        if not column_exists("letters", "content_source"):
            db.session.execute(text("ALTER TABLE letters ADD COLUMN content_source VARCHAR(20) NOT NULL DEFAULT 'manual'"))
        if not column_exists("letters", "request_type"):
            db.session.execute(text("ALTER TABLE letters ADD COLUMN request_type VARCHAR(40) NOT NULL DEFAULT 'Other'"))
        if not column_exists("letters", "original_description"):
            db.session.execute(text("ALTER TABLE letters ADD COLUMN original_description TEXT"))
        if not column_exists("letters", "generated_subject"):
            db.session.execute(text("ALTER TABLE letters ADD COLUMN generated_subject VARCHAR(255)"))
        if not column_exists("letters", "generated_body"):
            db.session.execute(text("ALTER TABLE letters ADD COLUMN generated_body TEXT"))

    if "scans" in table_names and not column_exists("scans", "created_at"):
        try:
            db.session.execute(text("ALTER TABLE scans ADD COLUMN created_at TIMESTAMP"))
            db.session.execute(text("UPDATE scans SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        except Exception:
            db.session.rollback()
        else:
            db.session.commit()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def seed_user(username: str, password: str, role: str, name: str, email: str) -> None:
    """Create a seeded user only when it is fully configured and missing."""
    if not username or not password or not email:
        return

    existing = db.session.get(User, username)
    if existing:
        return

    db.session.add(
        User(
            username=username,
            password_hash=generate_password_hash(password),
            role=role,
            name=name,
            email=email,
        )
    )
    db.session.commit()


def ensure_initial_staff() -> None:
    """Ensure the environment-defined staff account exists without creating duplicates."""
    username = settings.INITIAL_STAFF_USERNAME
    password = settings.INITIAL_STAFF_PASSWORD
    email = settings.INITIAL_STAFF_EMAIL

    if not username or not password or not email:
        return

    existing = db.session.get(User, username)
    if existing:
        return

    db.session.add(
        User(
            username=username,
            password_hash=generate_password_hash(password),
            role="staff",
            name=settings.INITIAL_STAFF_NAME,
            email=email,
        )
    )
    db.session.commit()


def seed_initial_users() -> None:
    """Seed admin and staff accounts when deployment settings provide them."""
    seed_user(
        settings.INITIAL_ADMIN_USERNAME,
        settings.INITIAL_ADMIN_PASSWORD,
        "admin",
        settings.INITIAL_ADMIN_NAME,
        settings.INITIAL_ADMIN_EMAIL,
    )
    seed_user(
        settings.INITIAL_STAFF_USERNAME,
        settings.INITIAL_STAFF_PASSWORD,
        "staff",
        settings.INITIAL_STAFF_NAME,
        settings.INITIAL_STAFF_EMAIL,
    )


def init_db() -> None:
    """Create tables, apply minimal schema changes, and seed startup data."""
    ensure_dirs()
    db.create_all()
    ensure_legacy_compatible_schema()
    seed_initial_users()
    ensure_initial_staff()