"""Authentication and account entry-point routes."""

from __future__ import annotations

import html
import os
import time
from datetime import datetime, timezone

from flask import current_app, redirect, jsonify, render_template, request, session, url_for
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from . import settings
from .auth import (
    email_exists,
    get_user_by_username,
    is_valid_phone,
    is_valid_register_number,
    login_user,
    normalize_email,
    normalize_username,
    username_exists,
    validate_password_strength,
    verify_staff_access_key,
)
from .extensions import db
from .models import PasswordResetToken, User
from .services import build_password_reset_link, is_allowed_institute_email, save_signature_image, send_mailjet_email, verify_recaptcha


def register_auth_routes(app):
    """Register login, signup, logout, and landing routes."""

    @app.route("/")
    def index():
        if not session.get("username"):
            return redirect(url_for("login"))
        return redirect(url_for("student_dashboard" if session.get("role") == "student" else "staff_dashboard"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if session.get("username"):
            return redirect(url_for("index"))

        message = request.args.get("message", "")
        if request.method == "POST":
            identifier = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            captcha_ok, captcha_error = verify_recaptcha(request.form.get("g-recaptcha-response"))

            missing = []
            if not identifier:
                missing.append("Register number or Email")
            if not password:
                missing.append("Password")
            if missing:
                return render_template(
                    "login.html",
                    error="{} is required.".format(" and ".join(missing)),
                    message=message,
                ), 400
            if not captcha_ok:
                return render_template("login.html", error=captcha_error, message=message), 400

            normalized_id = normalize_username(identifier)
            normalized_mail = normalize_email(identifier)
            user = User.query.filter(
                (func.lower(User.username) == normalized_id.lower()) |
                (func.lower(User.email) == normalized_mail.lower())
            ).first()

            if not user or not check_password_hash(user.password_hash, password):
                return render_template("login.html", error="Invalid credentials.", message=message), 401
            if user.role != "student":
                return render_template("login.html", error="Use the staff login page for staff accounts.", message=message), 403

            login_user(user)
            return redirect(url_for("student_dashboard"))

        return render_template("login.html", message=message)

    @app.route("/staff/login", methods=["GET", "POST"])
    def staff_login():
        if session.get("username") and session.get("role") in {"staff", "admin"}:
            return redirect(url_for("staff_dashboard"))

        message = request.args.get("message", "")
        if request.method == "POST":
            identifier = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()
            access_key = request.form.get("access_key", "").strip()
            captcha_ok, captcha_error = verify_recaptcha(request.form.get("g-recaptcha-response"))

            missing = []
            if not identifier:
                missing.append("Username or Email")
            if not password:
                missing.append("Password")
            if settings.STAFF_ACCESS_KEY and not access_key:
                missing.append("Admin key")
            if missing:
                return render_template(
                    "staff_login.html",
                    error="{} is required.".format(" and ".join(missing)),
                    message=message,
                    access_key_enabled=bool(settings.STAFF_ACCESS_KEY),
                ), 400
            if not captcha_ok:
                return render_template(
                    "staff_login.html",
                    error=captcha_error,
                    message=message,
                    access_key_enabled=bool(settings.STAFF_ACCESS_KEY),
                ), 400
            if not verify_staff_access_key(access_key):
                return render_template(
                    "staff_login.html",
                    error="Invalid admin key.",
                    message=message,
                    access_key_enabled=bool(settings.STAFF_ACCESS_KEY),
                ), 403

            normalized_id = normalize_username(identifier)
            normalized_mail = normalize_email(identifier)
            user = User.query.filter(
                (func.lower(User.username) == normalized_id.lower()) |
                (func.lower(User.email) == normalized_mail.lower())
            ).first()

            if not user or user.role not in {"staff", "admin"} or not check_password_hash(user.password_hash, password):
                return render_template(
                    "staff_login.html",
                    error="Invalid username or password.",
                    message=message,
                    access_key_enabled=bool(settings.STAFF_ACCESS_KEY),
                ), 401

            login_user(user, is_staff_key_verified=True)
            return redirect(url_for("staff_dashboard"))

        return render_template("staff_login.html", message=message, access_key_enabled=bool(settings.STAFF_ACCESS_KEY))

    def _password_reset_check_limit(key: str, max_requests: int = 5, window_seconds: int = 3600) -> bool:
        bucket = current_app.config.setdefault("password_reset_limits", {})
        now = time.time()
        records = [stamp for stamp in bucket.get(key, []) if now - stamp < window_seconds]
        if len(records) >= max_requests:
            bucket[key] = records
            return False
        bucket[key] = records + [now]
        return True

    @app.route("/forgot-password", methods=["GET", "POST"])
    def forgot_password():
        if session.get("username"):
            return redirect(url_for("index"))

        if request.method == "POST":
            email = normalize_email(request.form.get("email", ""))
            captcha_ok, captcha_error = verify_recaptcha(request.form.get("g-recaptcha-response"))
            if not captcha_ok:
                return render_template("forgot_password.html", error=captcha_error), 400
            if not email or "@" not in email:
                return render_template("forgot_password.html", error="Please enter a valid email address."), 400

            limit_key = f"{request.remote_addr or 'unknown'}:{email}"
            if not _password_reset_check_limit(limit_key):
                return render_template(
                    "forgot_password.html",
                    success="If an account exists for the information provided, a password reset link has been sent.",
                )

            user = User.query.filter(func.lower(User.email) == email.lower()).first()
            if user:
                for token in PasswordResetToken.query.filter_by(user_id=user.username, used=False).filter(
                    PasswordResetToken.expires_at > datetime.now(timezone.utc)
                ).all():
                    token.used = True
                reset_record = PasswordResetToken.create_for_user(user)
                reset_url = build_password_reset_link(reset_record.raw_token)
                send_mailjet_email(
                    user.email,
                    "Password Reset Request",
                    (
                        "<!doctype html><html><body>"
                        f"<p>Hello {html.escape(user.name)},</p>"
                        "<p>We received a request to reset your password.</p>"
                        f'<p><a href="{html.escape(reset_url, quote=True)}">Reset your password</a></p>'
                        f"<p>Link: {html.escape(reset_url)}</p>"
                        "<p>This link expires in 30 minutes. If you did not request this, you can ignore this email.</p>"
                        "</body></html>"
                    ),
                    ref=user.username,
                )

            return render_template(
                "forgot_password.html",
                success="If an account exists for the information provided, a password reset link has been sent.",
            )

        return render_template("forgot_password.html")

    @app.route("/reset-password/<token>", methods=["GET", "POST"])
    def reset_password(token):
        if session.get("username"):
            return redirect(url_for("index"))

        reset_record = PasswordResetToken.lookup_by_raw_token(token)
        if not reset_record:
            return render_template("reset_password.html", valid=False, error="This password reset link is invalid or has expired."), 400

        user = db.session.get(User, reset_record.user_id)
        if not user:
            return render_template("reset_password.html", valid=False, error="This password reset link is invalid or has expired."), 400

        if request.method == "POST":
            password = request.form.get("password", "").strip()
            confirm = request.form.get("confirm_password", "").strip()
            errors = []
            if len(password) < 8:
                errors.append("Password must be at least 8 characters long.")
            if password != confirm:
                errors.append("Passwords do not match.")
            if errors:
                return render_template("reset_password.html", valid=True, error=" ".join(errors), token=token), 400

            user.password_hash = generate_password_hash(password)

            reset_record.used = True
            PasswordResetToken.query.filter(
                PasswordResetToken.user_id == user.username,
                PasswordResetToken.id != reset_record.id,
            ).update({PasswordResetToken.used: True})

            db.session.add(user)
            db.session.add(reset_record)
            db.session.commit()

            return redirect(url_for("login", message="Your password has been reset successfully. Please sign in."))

        return render_template("reset_password.html", valid=True, token=token)

    @app.route("/debug-users")
    def debug_users():
        users = User.query.with_entities(User.username, User.role).all()
        return jsonify([{"username": u.username, "role": u.role} for u in users])

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if not settings.ALLOW_STUDENT_SELF_SIGNUP:
            return render_template(
                "signup.html",
                error="Student self-registration is disabled. Please contact the institute administrator.",
                allow_signup=False,
                allowed_domains=sorted(settings.ALLOWED_EMAIL_DOMAINS),
            )

        if request.method == "POST":
            register_number = normalize_username(request.form.get("register_number", ""))
            password = request.form.get("password", "").strip()
            name = request.form.get("name", "").strip()
            email = normalize_email(request.form.get("email", ""))
            captcha_ok, captcha_error = verify_recaptcha(request.form.get("g-recaptcha-response"))

            errors = []
            if not is_valid_register_number(register_number):
                errors.append("Register number must be 6 to 20 letters or digits without spaces.")
            errors.extend(validate_password_strength(password))
            if len(name) < 2:
                errors.append("Full name is required.")
            if "@" not in email:
                errors.append("A valid institute email is required.")
            elif not is_allowed_institute_email(email):
                if settings.ALLOWED_EMAIL_DOMAINS:
                    errors.append(f"Use your institute email address ({', '.join(sorted(settings.ALLOWED_EMAIL_DOMAINS))}).")
                else:
                    errors.append("Use a valid institute email address.")
            if not captcha_ok:
                errors.append(captcha_error)

            if username_exists(register_number):
                errors.append("Register number already exists.")
            if email_exists(email):
                errors.append("An account with this email already exists.")

            if errors:
                return render_template(
                    "signup.html",
                    error=" ".join(errors),
                    allow_signup=True,
                    allowed_domains=sorted(settings.ALLOWED_EMAIL_DOMAINS),
                    register_number=register_number,
                    name=name,
                    email=email,
                ), 400

            db.session.add(
                User(
                    username=register_number,
                    password_hash=generate_password_hash(password),
                    role="student",
                    name=name,
                    email=email,
                )
            )
            db.session.commit()

            return redirect(url_for("login", message="Account created. Please sign in with your student credentials."))

        return render_template("signup.html", allow_signup=True, allowed_domains=sorted(settings.ALLOWED_EMAIL_DOMAINS))

    @app.route("/profile", methods=["GET", "POST"])
    def profile():
        if not session.get("username"):
            return redirect(url_for("login"))

        user = db.session.get(User, session["username"])
        if not user:
            session.clear()
            return redirect(url_for("login"))

        errors = []
        message = ""
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = normalize_email(request.form.get("email", ""))
            phone = request.form.get("phone", "").strip()
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            signature = request.files.get("signature")

            if len(name) < 2 or len(name) > 120:
                errors.append("Name must be between 2 and 120 characters.")
            if "@" not in email or len(email) > 255:
                errors.append("Enter a valid email address.")
            elif not is_allowed_institute_email(email):
                errors.append("Use a valid institute email address.")
            if phone and not is_valid_phone(phone):
                errors.append("Enter a valid phone number.")
            other_user = User.query.filter(func.lower(User.email) == email, User.username != user.username).first()
            if other_user:
                errors.append("That email address is already in use.")
            if new_password:
                if not current_password or not check_password_hash(user.password_hash, current_password):
                    errors.append("Enter your current password to change it.")
                errors.extend(validate_password_strength(new_password))
            if signature and signature.filename:
                signature.stream.seek(0, 2)
                signature_size = signature.stream.tell()
                signature.stream.seek(0)
                extension = os.path.splitext(secure_filename(signature.filename))[1].lower()
                if signature_size > settings.MAX_SIGNATURE_SIZE:
                    errors.append("Signature image must be 2 MB or smaller.")
                if extension not in {".png", ".jpg", ".jpeg"}:
                    errors.append("Signature must be a PNG, JPG, or JPEG image.")

            if not errors:
                user.name = name
                user.email = email
                user.phone = phone or None
                if new_password:
                    user.password_hash = generate_password_hash(new_password)
                if signature and signature.filename:
                    user.signature_file_name = save_signature_image(signature, user.username)
                db.session.commit()
                session["name"] = user.name
                session["email"] = user.email
                message = "Profile updated successfully."

        return render_template("profile.html", user=user, errors=errors, message=message)

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))