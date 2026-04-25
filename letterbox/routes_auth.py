"""Authentication and account entry-point routes."""

from __future__ import annotations

from flask import redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import settings
from .auth import (
    email_exists,
    get_user_by_username,
    is_valid_register_number,
    login_user,
    normalize_email,
    normalize_username,
    username_exists,
    validate_password_strength,
    verify_staff_access_key,
)
from .extensions import db
from .models import User
from .services import is_allowed_institute_email, verify_recaptcha


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
            username = normalize_username(request.form.get("username", ""))
            password = request.form.get("password", "").strip()
            captcha_ok, captcha_error = verify_recaptcha(request.form.get("g-recaptcha-response"))

            missing = []
            if not username:
                missing.append("Register number")
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

            user = get_user_by_username(username)
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
            username = normalize_username(request.form.get("username", ""))
            password = request.form.get("password", "").strip()
            access_key = request.form.get("access_key", "").strip()
            captcha_ok, captcha_error = verify_recaptcha(request.form.get("g-recaptcha-response"))

            missing = []
            if not username:
                missing.append("Username")
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

            user = get_user_by_username(username)
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

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))
