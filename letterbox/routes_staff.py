"""Staff dashboards, admin management, workflow processing, and ESP routes."""

from __future__ import annotations

import os

from flask import jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from . import settings
from .auth import (
    email_exists,
    is_valid_staff_username,
    login_required,
    normalize_email,
    normalize_username,
    roles_required,
    staff_key_required,
    username_exists,
    validate_password_strength,
)
from .extensions import csrf, db
from .models import Letter, User
from .services import (
    decode_uploaded_scan,
    ensure_letter_file,
    esp_token_valid,
    extract_app_id,
    fetch_esp_payload,
    generate_app_id,
    get_letter,
    jsonify_error,
    send_email,
    update_letter_status,
    utc_now,
    verify_recaptcha,
)


def register_staff_routes(app):
    """Register staff-only dashboards, admin pages, and workflow routes."""

    @app.route("/dashboard/staff")
    @login_required
    @roles_required("staff", "admin")
    @staff_key_required
    def staff_dashboard():
        letters = Letter.query.order_by(Letter.created_at.desc(), Letter.app_id.desc()).all()
        counts = {status: 0 for status in settings.VALID_STATUSES}
        for letter in letters:
            counts[letter.status] = counts.get(letter.status, 0) + 1
        return render_template("staff_dashboard.html", letters=letters, counts=counts, name=session.get("name"))

    @app.route("/admin")
    @login_required
    @roles_required("staff", "admin")
    @staff_key_required
    def admin_panel():
        staff_accounts = User.query.filter(User.role.in_(["staff", "admin"])).order_by(User.name.asc(), User.username.asc()).all()
        return render_template(
            "admin.html",
            staff_accounts=staff_accounts,
            name=session.get("name"),
            message=request.args.get("message", ""),
            access_key_enabled=bool(settings.STAFF_ACCESS_KEY),
        )

    @app.route("/admin/staff/create", methods=["POST"])
    @login_required
    @roles_required("staff", "admin")
    @staff_key_required
    def create_staff_account():
        username = normalize_username(request.form.get("username", ""))
        password = request.form.get("password", "").strip()
        name = request.form.get("name", "").strip()
        email = normalize_email(request.form.get("email", ""))
        captcha_ok, captcha_error = verify_recaptcha(request.form.get("g-recaptcha-response"))

        errors = []
        if not is_valid_staff_username(username):
            errors.append("Username must be 3 to 30 characters using letters, numbers, dot, underscore, or hyphen.")
        errors.extend(validate_password_strength(password))
        if len(name) < 2:
            errors.append("Staff name is required.")
        if "@" not in email:
            errors.append("A valid staff email is required.")
        elif settings.ALLOWED_EMAIL_DOMAINS and email.rsplit("@", 1)[1] not in settings.ALLOWED_EMAIL_DOMAINS:
            errors.append(f"Use an institute email address ({', '.join(sorted(settings.ALLOWED_EMAIL_DOMAINS))}).")
        if username_exists(username):
            errors.append("Username already exists.")
        if email_exists(email):
            errors.append("Email already exists.")
        if not captcha_ok:
            errors.append(captcha_error)

        if errors:
            return redirect(url_for("admin_panel", message=" ".join(errors)))

        db.session.add(
            User(
                username=username,
                password_hash=generate_password_hash(password),
                role="staff",
                name=name,
                email=email,
            )
        )
        db.session.commit()

        return redirect(url_for("admin_panel", message=f"Staff account '{username}' created successfully."))

    @app.route("/generate", methods=["POST"])
    @login_required
    @roles_required("staff", "admin")
    @staff_key_required
    def generate():
        app_id = generate_app_id()
        letter = Letter(
            app_id=app_id,
            name="",
            email="",
            phone="",
            subject="Staff Generated Placeholder",
            description="",
            status=settings.STATUS_CREATED,
            created_at=utc_now(),
        )
        db.session.add(letter)
        db.session.commit()

        ensure_letter_file(letter)
        img_url = url_for("static", filename=f"qr_codes/{letter.qr_file_name}")
        return f"QR generated for placeholder letter {app_id}<br><img src='{img_url}' alt='QR code'>"

    @app.route("/staff")
    @login_required
    @roles_required("staff", "admin")
    @staff_key_required
    def staff():
        return redirect(url_for("scanners"))

    @app.route("/scanners")
    @login_required
    @roles_required("staff", "admin")
    @staff_key_required
    def scanners():
        return render_template("scanners.html")

    @app.route("/submit_scan", methods=["POST"])
    @login_required
    @roles_required("staff", "admin")
    @staff_key_required
    def submit_scan():
        app_id = request.args.get("id", "").strip() or request.form.get("id", "").strip()
        if not app_id:
            return jsonify_error("Missing id.")

        try:
            letter = update_letter_status(app_id, settings.STATUS_SUBMITTED)
        except ValueError as exc:
            return jsonify_error(str(exc), 409, app_id=app_id)

        if not letter:
            return jsonify_error("Application not found.", 404, app_id=app_id)

        return jsonify({"status": "ok", "message": "Marked as Submitted.", "app_id": app_id})

    @app.route("/letters/<app_id>/review", methods=["POST"])
    @login_required
    @roles_required("staff", "admin")
    @staff_key_required
    def mark_pending(app_id):
        try:
            letter = update_letter_status(app_id, settings.STATUS_PENDING)
        except ValueError as exc:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify_error(str(exc), 409, app_id=app_id)
            return redirect(url_for("staff_dashboard"))

        if not letter:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify_error("Application not found.", 404, app_id=app_id)
            return redirect(url_for("staff_dashboard"))

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "ok", "message": "Marked as Pending.", "app_id": app_id})
        return redirect(url_for("staff_dashboard"))

    @app.route("/esp_submit", methods=["POST"])
    @csrf.exempt
    def esp_submit():
        data = request.get_json(silent=True) or request.form
        app_id = (data.get("id") or data.get("app_id") or "").strip() if hasattr(data, "get") else ""
        if not app_id:
            return jsonify_error("Missing id.")
        if not esp_token_valid(data):
            return jsonify_error("Unauthorized.", 401)

        try:
            letter = update_letter_status(app_id, settings.STATUS_SUBMITTED)
        except ValueError as exc:
            return jsonify_error(str(exc), 409, app_id=app_id)

        if not letter:
            return jsonify_error("Application not found.", 404, app_id=app_id)

        return jsonify({"status": "ok", "message": "Marked as Submitted.", "app_id": app_id})

    @app.route("/esp_approve", methods=["POST"])
    @csrf.exempt
    def esp_approve():
        data = request.get_json(silent=True) or request.form
        app_id = (data.get("id") or data.get("app_id") or "").strip() if hasattr(data, "get") else ""
        if not app_id:
            return jsonify_error("Missing id.")
        if not esp_token_valid(data):
            return jsonify_error("Unauthorized.", 401)

        try:
            letter = update_letter_status(app_id, settings.STATUS_APPROVED)
        except ValueError as exc:
            return jsonify_error(str(exc), 409, app_id=app_id)

        if not letter:
            return jsonify_error("Application not found.", 404, app_id=app_id)

        send_email(
            letter.email,
            f"Your letter {app_id} has been approved and placed in the output box.",
            subject="Letter Approved",
            ref=app_id,
        )
        return jsonify({"status": "ok", "message": "Marked as Approved.", "app_id": app_id})

    @app.route("/trigger_esp")
    @login_required
    @roles_required("staff", "admin")
    @staff_key_required
    def trigger_esp():
        esp_host = request.args.get("host", "").strip() or os.environ.get("ESP32_HOST", "").strip()
        action = request.args.get("action", "submit").strip().lower()
        if action not in {"submit", "approve"}:
            return jsonify_error("Invalid action.")
        if not esp_host:
            return jsonify_error("ESP host not configured. Set ESP32_HOST or provide ?host=.", 400)

        url = f"http://{esp_host}/trigger?action={action}"
        try:
            import requests as _requests

            response = _requests.get(url, timeout=5)
            try:
                payload = response.json()
            except Exception:
                payload = {"raw": response.text}
            return jsonify({"status": "ok", "esp_status": response.status_code, "data": payload})
        except Exception as exc:
            return jsonify_error("Failed to contact ESP device.", 502, error=str(exc))

    @app.route("/esp_data")
    @login_required
    @roles_required("staff", "admin")
    @staff_key_required
    def esp_data():
        esp_host = request.args.get("host", "").strip() or os.environ.get("ESP32_HOST", "").strip()
        if not esp_host:
            return jsonify_error("ESP host not configured. Set ESP32_HOST or provide ?host=.", 400)

        payload, error = fetch_esp_payload(esp_host)
        if payload is not None:
            return jsonify(payload)
        return jsonify_error("Failed to fetch from ESP.", 502, **error)

    @app.route("/scan_upload", methods=["POST"])
    @login_required
    @roles_required("staff", "admin")
    @staff_key_required
    def scan_upload():
        if "file" not in request.files:
            return jsonify_error("No file uploaded.")
        file = request.files["file"]
        if not file.filename:
            return jsonify_error("No file uploaded.")

        try:
            texts = decode_uploaded_scan(file)
            for text_value in texts:
                app_id = extract_app_id(text_value)
                if not app_id:
                    continue
                if not get_letter(app_id):
                    return jsonify_error("Application not found.", 404, app_id=app_id, decoded=texts)
                return jsonify({"status": "ok", "app_id": app_id, "decoded": texts})
            return jsonify_error("Could not parse an application ID from the decoded image.", 400, decoded=texts)
        except ValueError as exc:
            return jsonify_error(str(exc))
        except RuntimeError as exc:
            return jsonify_error(str(exc), 500)
        except Exception:
            return jsonify_error("Failed to decode the uploaded image.", 500)

    @app.route("/approve", methods=["GET", "POST"])
    @login_required
    @roles_required("staff", "admin")
    @staff_key_required
    def approve():
        app_id = request.args.get("id", "").strip() or request.form.get("id", "").strip()
        if not app_id:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify_error("Missing id.")
            return redirect(url_for("staff_dashboard"))

        try:
            letter = update_letter_status(app_id, settings.STATUS_APPROVED)
        except ValueError as exc:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify_error(str(exc), 409, app_id=app_id)
            return render_template("success.html", message=str(exc), app_id=app_id, name=session.get("name", "")), 409

        if not letter:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify_error("Application not found.", 404, app_id=app_id)
            return render_template("success.html", message="Application not found.", app_id=app_id, name=session.get("name", "")), 404

        send_email(
            letter.email,
            f"Your letter {app_id} has been approved and placed in the output box.",
            subject="Letter Approved",
            ref=app_id,
        )

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "ok", "message": "Approved and notification sent.", "app_id": app_id})

        return render_template("success.html", message="Letter approved and notification sent.", app_id=app_id, name=letter.name)
