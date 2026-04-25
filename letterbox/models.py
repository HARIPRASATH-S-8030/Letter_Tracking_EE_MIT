"""Database models for users, letters, and scan logs."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from .extensions import db


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class User(db.Model):
    """Application user account."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('student', 'staff', 'admin')", name="ck_users_role"),
    )

    username = db.Column(db.String(50), primary_key=True)
    password_hash = db.Column("password", db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=True, default=utcnow)


class Letter(db.Model):
    """Tracked letter request with generated file metadata."""

    __tablename__ = "letters"
    __table_args__ = (
        CheckConstraint(
            "status IN ('Created', 'Submitted', 'Pending', 'Approved')",
            name="ck_letters_status",
        ),
    )

    app_id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(30), nullable=False)
    subject = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="Created", index=True)
    generated_file_name = db.Column(db.String(255), nullable=True)
    qr_file_name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)


class ScanLog(db.Model):
    """Recorded QR or barcode scans."""

    __tablename__ = "scans"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
