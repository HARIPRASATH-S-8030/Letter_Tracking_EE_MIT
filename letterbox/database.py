"""Database setup, startup migrations, and seed helpers."""

from __future__ import annotations

import logging
import os

from sqlalchemy import text
from werkzeug.security import generate_password_hash

from . import settings
from .extensions import db
from .models import User

logger = logging.getLogger(__name__)


def ensure_dirs() -> None:
    """Create runtime output folders if they do not already exist."""
    for path in (settings.QR_DIR, settings.BARCODE_DIR, settings.GEN_DIR, settings.SIGNATURE_DIR, settings.SENT_DIR):
        os.makedirs(path, exist_ok=True)


def ensure_legacy_compatible_schema() -> None:
    """Apply lightweight schema updates without heavy catalog reflection."""
    is_postgres = db.engine.dialect.name == "postgresql"

    if is_postgres:
        # Native PostgreSQL zero-overhead migrations
        statements = [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255) DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(30)",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS signature_file_name TEXT",
            "ALTER TABLE users ALTER COLUMN signature_file_name TYPE TEXT",

            "ALTER TABLE letters ADD COLUMN IF NOT EXISTS generated_file_name VARCHAR(255)",
            "ALTER TABLE letters ADD COLUMN IF NOT EXISTS qr_file_name VARCHAR(255)",
            "ALTER TABLE letters ADD COLUMN IF NOT EXISTS signature_file_name TEXT",
            "ALTER TABLE letters ALTER COLUMN signature_file_name TYPE TEXT",
            "ALTER TABLE letters ADD COLUMN IF NOT EXISTS generation_mode VARCHAR(10) DEFAULT 'manual'",
            "ALTER TABLE letters ADD COLUMN IF NOT EXISTS content_source VARCHAR(20) DEFAULT 'manual'",
            "ALTER TABLE letters ADD COLUMN IF NOT EXISTS request_type VARCHAR(40) DEFAULT 'Other'",
            "ALTER TABLE letters ADD COLUMN IF NOT EXISTS original_description TEXT",
            "ALTER TABLE letters ADD COLUMN IF NOT EXISTS generated_subject VARCHAR(255)",
            "ALTER TABLE letters ADD COLUMN IF NOT EXISTS generated_body TEXT",

            "ALTER TABLE scans ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP",
        ]
        for stmt in statements:
            try:
                db.session.execute(text(stmt))
                db.session.commit()
            except Exception:
                db.session.rollback()
    else:
        # Lightweight SQLite migrations
        sqlite_cols = {
            "users": [
                ("created_at", "TIMESTAMP"),
                ("email", "VARCHAR(255) DEFAULT ''"),
                ("phone", "VARCHAR(30)"),
                ("signature_file_name", "TEXT"),
            ],
            "letters": [
                ("generated_file_name", "VARCHAR(255)"),
                ("qr_file_name", "VARCHAR(255)"),
                ("signature_file_name", "TEXT"),
                ("generation_mode", "VARCHAR(10) DEFAULT 'manual'"),
                ("content_source", "VARCHAR(20) DEFAULT 'manual'"),
                ("request_type", "VARCHAR(40) DEFAULT 'Other'"),
                ("original_description", "TEXT"),
                ("generated_subject", "VARCHAR(255)"),
                ("generated_body", "TEXT"),
            ],
            "scans": [
                ("created_at", "TIMESTAMP"),
            ],
        }
        for table, cols in sqlite_cols.items():
            for col_name, col_type in cols:
                try:
                    db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
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
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


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
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


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
    try:
        db.create_all()
    except Exception as exc:
        logger.warning("db.create_all warning: %s", exc)
        db.session.rollback()

    ensure_legacy_compatible_schema()
    seed_initial_users()
    ensure_initial_staff()