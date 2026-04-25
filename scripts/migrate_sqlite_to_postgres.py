"""One-off migration helper from the legacy SQLite database to PostgreSQL."""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

from letterbox import create_app
from letterbox.extensions import db
from letterbox.models import Letter, ScanLog, User


def parse_timestamp(value):
    """Convert SQLite text timestamps into timezone-aware datetime objects."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def normalize_password_hash(value: str) -> str:
    """Hash plain-text legacy passwords while preserving existing Werkzeug hashes."""
    raw = (value or "").strip()
    if not raw:
        return generate_password_hash("ChangeMe123!")
    if raw.startswith(("pbkdf2:", "scrypt:")):
        return raw
    return generate_password_hash(raw)


def sqlite_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    """Read the available columns from the source SQLite file."""
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def main() -> int:
    legacy_path = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("LEGACY_SQLITE_PATH", "database.db")
    if not os.path.exists(legacy_path):
        print(f"Legacy SQLite file not found: {legacy_path}")
        return 1

    app = create_app()
    with app.app_context():
        if db.engine.url.get_backend_name() == "sqlite":
            print("Set DATABASE_URL to your PostgreSQL database before running this migration.")
            return 1

        source = sqlite3.connect(legacy_path)
        source.row_factory = sqlite3.Row

        users_total = 0
        letters_total = 0
        scans_total = 0

        user_columns = sqlite_columns(source, "users")
        for row in source.execute("SELECT * FROM users"):
            username = (row["username"] or "").strip().lower()
            if not username:
                continue
            user = db.session.get(User, username)
            if user is None:
                user = User(username=username)
                db.session.add(user)
            user.password_hash = normalize_password_hash(row["password"])
            user.role = row["role"] if row["role"] in {"student", "staff", "admin"} else "student"
            user.name = row["name"] or username
            user.email = (row["email"] or f"{username}@example.com").strip().lower()
            user.created_at = parse_timestamp(row["created_at"]) if "created_at" in user_columns else None
            users_total += 1

        letter_columns = sqlite_columns(source, "letters")
        for row in source.execute("SELECT * FROM letters"):
            app_id = (row["app_id"] or "").strip()
            if not app_id:
                continue
            letter = db.session.get(Letter, app_id)
            if letter is None:
                letter = Letter(app_id=app_id)
                db.session.add(letter)
            letter.name = row["name"] or ""
            letter.email = (row["email"] or "").strip().lower()
            letter.phone = row["phone"] or ""
            letter.subject = row["subject"] or "Request"
            letter.description = row["description"] or ""
            letter.status = row["status"] or "Created"
            letter.created_at = parse_timestamp(row["created_at"]) or datetime.now(timezone.utc)
            letter.submitted_at = parse_timestamp(row["submitted_at"]) if "submitted_at" in letter_columns else None
            letter.approved_at = parse_timestamp(row["approved_at"]) if "approved_at" in letter_columns else None
            letter.generated_file_name = row["generated_file_name"] if "generated_file_name" in letter_columns else None
            letter.qr_file_name = row["qr_file_name"] if "qr_file_name" in letter_columns else None
            letters_total += 1

        if "scans" in {row["name"] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            scan_columns = sqlite_columns(source, "scans")
            for row in source.execute("SELECT * FROM scans"):
                code = (row["code"] or "").strip()
                if not code:
                    continue
                scan = ScanLog(code=code)
                if "created_at" in scan_columns:
                    scan.created_at = parse_timestamp(row["created_at"]) or datetime.now(timezone.utc)
                elif "timestamp" in scan_columns:
                    scan.created_at = parse_timestamp(row["timestamp"]) or datetime.now(timezone.utc)
                else:
                    scan.created_at = datetime.now(timezone.utc)
                db.session.add(scan)
                scans_total += 1

        db.session.commit()
        source.close()

    print(f"Migrated {users_total} users, {letters_total} letters, and {scans_total} scans from {legacy_path}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
