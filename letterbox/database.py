"""Database setup, startup migrations, and seed helpers."""

from __future__ import annotations

import os

from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

from . import settings
from .extensions import db
from .models import User


def ensure_dirs() -> None:
    """Create runtime output folders if they do not already exist."""
    for path in (settings.QR_DIR, settings.BARCODE_DIR, settings.GEN_DIR, settings.SENT_DIR):
        os.makedirs(path, exist_ok=True)


def column_exists(table_name: str, column_name: str) -> bool:
    """Check whether a column exists in the current database."""
    inspector = inspect(db.engine)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def ensure_legacy_compatible_schema() -> None:
    """Apply lightweight schema updates so older local SQLite databases still work."""
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())

    if "users" in table_names:
        if not column_exists("users", "created_at"):
            db.session.execute(text("ALTER TABLE users ADD COLUMN created_at TIMESTAMP"))
        if not column_exists("users", "email"):
            db.session.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255) NOT NULL DEFAULT ''"))

    if "letters" in table_names:
        if not column_exists("letters", "generated_file_name"):
            db.session.execute(text("ALTER TABLE letters ADD COLUMN generated_file_name VARCHAR(255)"))
        if not column_exists("letters", "qr_file_name"):
            db.session.execute(text("ALTER TABLE letters ADD COLUMN qr_file_name VARCHAR(255)"))

    if "scans" in table_names and not column_exists("scans", "created_at"):
        try:
            db.session.execute(text("ALTER TABLE scans ADD COLUMN created_at TIMESTAMP"))
            db.session.execute(text("UPDATE scans SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        except Exception:
            # Older SQLite files may already contain a timestamp column named differently.
            db.session.rollback()
        else:
            db.session.commit()

    db.session.commit()


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

    if db.session.get(User, username):
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

    if settings.SEED_DEMO_USERS:
        seed_user("student1", "Password123!", "student", "Demo Student", "student@example.com")
        seed_user("staff1", "Password123!", "staff", "Demo Staff", "staff@example.com")


def init_db() -> None:
    """Create tables, apply minimal schema changes, and seed startup data."""
    ensure_dirs()
    db.create_all()
    ensure_legacy_compatible_schema()
    seed_initial_users()
    ensure_initial_staff()
