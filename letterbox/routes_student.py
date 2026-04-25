"""Student-facing routes for letter creation, tracking, and downloads."""

from __future__ import annotations

import os

from flask import abort, jsonify, redirect, render_template, request, send_file, session, url_for
from sqlalchemy import func

from . import settings
from .auth import is_valid_phone, login_required, roles_required, staff_key_required
from .extensions import csrf, db
from .models import Letter, ScanLog
from .services import (
    ensure_letter_file,
    generate_app_id,
    get_letter,
    jsonify_error,
    letter_belongs_to_current_user,
    normalize_letter_description,
    send_email,
    serialize_datetime,
    utc_now,
)


def register_student_routes(app):
    """Register student dashboards, form routes, and download endpoints."""

    @app.route("/dashboard/student")
    @login_required
    @roles_required("student")
    def student_dashboard():
        letters = (
            Letter.query.filter(func.lower(Letter.email) == session.get("email"))
            .order_by(Letter.created_at.desc(), Letter.app_id.desc())
            .all()
        )
        return render_template(
            "student_dashboard.html",
            letters=letters,
            name=session.get("name"),
            submitted=request.args.get("submitted", ""),
        )

    @app.route("/submit")
    @login_required
    @roles_required("student", "staff", "admin")
    @staff_key_required
    def submit():
        app_id = request.args.get("id", "").strip()
        if not app_id:
            if session.get("role") != "student":
                return redirect(url_for("staff_dashboard"))
            return render_template(
                "form.html",
                app_id="",
                name=session.get("name", ""),
                email=session.get("email", ""),
            )

        letter = get_letter(app_id)
        if not letter:
            return render_template("success.html", message="Letter record not found.", app_id=app_id, name=session.get("name", "")), 404
        if not letter_belongs_to_current_user(letter):
            abort(403)

        return render_template("status.html", letter=letter)

    @app.route("/save", methods=["POST"])
    @login_required
    @roles_required("student")
    def save():
        """Create a new student letter request and immediately prepare the downloadable document."""
        name = request.form.get("name", "").strip() or session.get("name", "").strip()
        email = session.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        subject = request.form.get("subject", "").strip()
        description = normalize_letter_description(request.form.get("description", ""))

        errors = []
        if len(name) < 2:
            errors.append("Name is required.")
        if "@" not in email:
            errors.append("A valid email is required.")
        if not is_valid_phone(phone):
            errors.append("Enter a valid phone number.")
        if len(subject) < 3:
            errors.append("Subject is required.")
        if len(description) < 10:
            errors.append("Description must be at least 10 characters.")
        if len(description) > settings.MAX_LETTER_DESCRIPTION_LENGTH:
            errors.append(f"Description must stay within {settings.MAX_LETTER_DESCRIPTION_LENGTH} characters so the letter fits on one page.")

        if errors:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"status": "error", "errors": errors}), 400
            return render_template(
                "form.html",
                errors=errors,
                app_id="",
                name=name,
                email=email,
                phone=phone,
                subject=subject,
                description=description,
            ), 400

        app_id = generate_app_id()
        letter = Letter(
            app_id=app_id,
            name=name,
            email=email,
            phone=phone,
            subject=subject,
            description=description,
            status=settings.STATUS_CREATED,
            created_at=utc_now(),
        )
        db.session.add(letter)
        db.session.commit()

        output_path = ensure_letter_file(letter)
        send_email(
            email,
            f"Your letter request {app_id} has been created in the system. Download it, print it, and submit it to the institute letterbox.",
            subject="Letter Created",
            ref=app_id,
        )

        download_url = url_for("download_letter", app_id=app_id)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(
                {
                    "status": "ok",
                    "message": "Letter created successfully.",
                    "app_id": app_id,
                    "download": download_url,
                    "file": os.path.basename(output_path),
                }
            )

        return redirect(url_for("student_dashboard", submitted=app_id))

    @app.route("/student_scan")
    @login_required
    @roles_required("student", "staff", "admin")
    @staff_key_required
    def student_scan():
        return render_template("student_scan.html")

    @app.route("/status_api")
    @login_required
    @roles_required("student", "staff", "admin")
    @staff_key_required
    def status_api():
        app_id = request.args.get("id", "").strip()
        if not app_id:
            return jsonify_error("Missing id parameter.")

        letter = get_letter(app_id)
        if not letter:
            return jsonify_error("Application not found.", 404)
        if not letter_belongs_to_current_user(letter):
            return jsonify_error("You do not have permission to view this letter.", 403)

        return jsonify(
            {
                "status": "ok",
                "app_id": letter.app_id,
                "name": letter.name,
                "email": letter.email,
                "phone": letter.phone,
                "subject": letter.subject,
                "state": letter.status,
                "created_at": serialize_datetime(letter.created_at),
                "submitted_at": serialize_datetime(letter.submitted_at),
                "approved_at": serialize_datetime(letter.approved_at),
            }
        )

    @app.route("/download/<app_id>")
    @login_required
    @roles_required("student", "staff", "admin")
    @staff_key_required
    def download_letter(app_id):
        letter = get_letter(app_id)
        if not letter:
            return render_template("success.html", message="Application not found.", app_id=app_id, name=session.get("name", "")), 404
        if not letter_belongs_to_current_user(letter):
            abort(403)

        path = ensure_letter_file(letter)
        download_name = f"letter_{letter.app_id}{os.path.splitext(path)[1]}"
        return send_file(path, as_attachment=True, download_name=download_name)

    @app.route("/generate_letter", methods=["POST"])
    @login_required
    @roles_required("student")
    def generate_letter():
        app_id = request.form.get("app_id", "").strip()
        if not app_id:
            return redirect(url_for("student_dashboard"))

        letter = get_letter(app_id)
        if not letter:
            return render_template("success.html", message="Application ID not found.", app_id=app_id, name=session.get("name", "")), 404
        if not letter_belongs_to_current_user(letter):
            abort(403)

        output_path = ensure_letter_file(letter)
        return send_file(output_path, as_attachment=True, download_name=os.path.basename(output_path))

    @app.route("/scan", methods=["POST"])
    @csrf.exempt
    def scan():
        data = request.get_json(silent=True) or {}
        code = str(data.get("code", "")).strip()
        if not code:
            return jsonify_error("Invalid data.")

        db.session.add(ScanLog(code=code, created_at=utc_now()))
        db.session.commit()

        app.logger.info("Scanned code received: %s", code)
        return jsonify({"status": "received"})
