"""Authentication helpers, decorators, and user account utilities."""

from __future__ import annotations

import re
from functools import wraps

from flask import abort, redirect, session, url_for
from sqlalchemy import func

from . import settings
from .models import User


PASSWORD_REQUIREMENTS = [
    (re.compile(r".{8,}"), "Password must be at least 8 characters."),
    (re.compile(r"[A-Z]"), "Password must contain at least one uppercase letter."),
    (re.compile(r"[a-z]"), "Password must contain at least one lowercase letter."),
    (re.compile(r"\d"), "Password must contain at least one number."),
    (re.compile(r"[^A-Za-z0-9]"), "Password must contain at least one special character."),
]


def login_required(fn):
    """Require a logged-in session before a route can be accessed."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("username"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def roles_required(*roles):
    """Require the current user to match one of the allowed roles."""
    allowed_roles = set(roles)

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if session.get("role") not in allowed_roles:
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def staff_key_required(fn):
    """Require staff and admin users to have passed the separate staff-key login flow."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if session.get("role") in {"staff", "admin"} and settings.STAFF_ACCESS_KEY and not session.get("staff_key_ok"):
            return redirect(url_for("staff_login", message="Please sign in again with the admin key for staff access."))
        return fn(*args, **kwargs)

    return wrapper


def normalize_username(username: str) -> str:
    """Normalize usernames and register numbers for consistent lookups."""
    return username.strip().lower()


def normalize_email(email: str) -> str:
    """Normalize emails for consistent comparisons."""
    return email.strip().lower()


def get_user_by_username(username: str) -> User | None:
    """Fetch a user row using a case-insensitive username lookup."""
    normalized = normalize_username(username)
    return User.query.filter(func.lower(User.username) == normalized).first()


def username_exists(username: str) -> bool:
    """Check whether a normalized username or register number already exists."""
    return User.query.filter(func.lower(User.username) == normalize_username(username)).first() is not None


def email_exists(email: str) -> bool:
    """Check whether an email address already belongs to an existing account."""
    return User.query.filter(func.lower(User.email) == normalize_email(email)).first() is not None


def login_user(user: User, *, is_staff_key_verified: bool = False) -> None:
    """Store the authenticated user in the session."""
    session.clear()
    session["username"] = user.username
    session["role"] = user.role
    session["name"] = user.name
    session["email"] = normalize_email(user.email)
    session["staff_key_ok"] = bool(is_staff_key_verified)
    session.permanent = True


def verify_staff_access_key(submitted_key: str) -> bool:
    """Validate the separate staff access key when configured."""
    if not settings.STAFF_ACCESS_KEY:
        return True
    return submitted_key.strip() == settings.STAFF_ACCESS_KEY


def is_valid_register_number(value: str) -> bool:
    """Allow only simple alphanumeric register numbers without spaces."""
    return bool(re.fullmatch(r"[A-Za-z0-9]{6,20}", (value or "").strip()))


def is_valid_staff_username(value: str) -> bool:
    """Allow staff usernames with letters, numbers, underscore, and dot."""
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]{3,30}", (value or "").strip()))


def is_valid_phone(value: str) -> bool:
    """Allow international-friendly phone numbers while rejecting obvious junk."""
    return bool(re.fullmatch(r"[0-9+\-() ]{8,20}", (value or "").strip()))


def validate_password_strength(password: str) -> list[str]:
    """Return human-readable password validation errors."""
    errors = []
    for pattern, message in PASSWORD_REQUIREMENTS:
        if not pattern.search(password or ""):
            errors.append(message)
    return errors
