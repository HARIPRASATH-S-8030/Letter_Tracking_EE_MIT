"""Database models for users, letters, scan logs, and password reset tokens."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

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
    phone = db.Column(db.String(30), nullable=True)
    signature_file_name = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=True, default=utcnow)


class PasswordResetToken(db.Model):
    """Single-use password reset tokens hashed before storage."""

    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(50), db.ForeignKey("users.username"), nullable=False, index=True)
    token_hash = db.Column(db.String(255), nullable=False, unique=True, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    used = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)

    user = db.relationship("User", backref=db.backref("password_reset_tokens", cascade="all, delete-orphan"))

    @staticmethod
    def hash_token(token: str) -> str:
        if not token:
            return ""
        return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()

    @classmethod
    def create_for_user(cls, user: "User", ttl_minutes: int = 30) -> "PasswordResetToken":
        raw_token = secrets.token_urlsafe(32)
        expires_at = utcnow() + timedelta(minutes=ttl_minutes)

        cls.query.filter(
            cls.user_id == user.username,
            cls.used.is_(False),
            cls.expires_at > utcnow(),
        ).update({cls.used: True})

        record = cls(
            user_id=user.username,
            token_hash=cls.hash_token(raw_token),
            expires_at=expires_at,
            used=False,
            created_at=utcnow(),
        )
        db.session.add(record)
        db.session.commit()
        record.raw_token = raw_token
        return record

    @classmethod
    def verify_token(cls, user: "User", raw_token: str | None) -> bool:
        if not user or not raw_token:
            return False
        record = cls.query.filter_by(user_id=user.username, token_hash=cls.hash_token(raw_token), used=False).filter(
            cls.expires_at > utcnow()
        ).order_by(cls.created_at.desc()).first()
        return record is not None

    @classmethod
    def verify_token_for_user(cls, user_id: str, raw_token: str | None) -> bool:
        if not user_id or not raw_token:
            return False
        record = cls.query.filter_by(user_id=user_id, token_hash=cls.hash_token(raw_token), used=False).filter(
            cls.expires_at > utcnow()
        ).order_by(cls.created_at.desc()).first()
        return record is not None

    @classmethod
    def consume_for_user(cls, user: "User", raw_token: str | None) -> bool:
        if not user or not raw_token:
            return False

        record = cls.query.filter_by(user_id=user.username, token_hash=cls.hash_token(raw_token), used=False).filter(
            cls.expires_at > utcnow()
        ).order_by(cls.created_at.desc()).first()
        if not record:
            return False

        cls.query.filter(
            cls.user_id == user.username,
            cls.used.is_(False),
            cls.id != record.id,
            cls.expires_at > utcnow(),
        ).update({cls.used: True})
        record.used = True
        db.session.commit()
        return True

    @classmethod
    def lookup_by_raw_token(cls, raw_token: str | None) -> "PasswordResetToken | None":
        if not raw_token:
            return None
        return cls.query.filter_by(token_hash=cls.hash_token(raw_token), used=False).filter(
            cls.expires_at > utcnow()
        ).order_by(cls.created_at.desc()).first()


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
    generation_mode = db.Column(db.String(10), nullable=False, default="manual")
    content_source = db.Column(db.String(20), nullable=False, default="manual")
    request_type = db.Column(db.String(40), nullable=False, default="Other")
    subject = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    original_description = db.Column(db.Text, nullable=True)
    generated_subject = db.Column(db.String(255), nullable=True)
    generated_body = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="Created", index=True)
    generated_file_name = db.Column(db.String(255), nullable=True)
    qr_file_name = db.Column(db.String(255), nullable=True)
    signature_file_name = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)
    submitted_at = db.Column(db.DateTime(timezone=True), nullable=True)
    approved_at = db.Column(db.DateTime(timezone=True), nullable=True)


class ScanLog(db.Model):
    """Recorded QR or barcode scans."""

    __tablename__ = "scans"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utcnow, index=True)