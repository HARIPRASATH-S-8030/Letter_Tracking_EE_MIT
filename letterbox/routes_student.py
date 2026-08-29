"""Student-facing routes for letter creation, tracking, and downloads."""

from __future__ import annotations

import os
import secrets

from flask import abort, jsonify, redirect, render_template, request, send_file, session, url_for
from sqlalchemy import func
from werkzeug.utils import secure_filename

from .ai_generation import AIGenerationError, REQUEST_TYPES, generate_letter_content, validate_generated_content
from . import settings
from .auth import get_user_by_username, is_valid_phone, login_required, roles_required, staff_key_required
from .extensions import csrf, db
from .models import Letter, ScanLog
from .services import (
    ensure_letter_file,
    generate_app_id,
    get_letter,
    jsonify_error,
    letter_belongs_to_current_user,
    normalize_letter_description,
    notification_summary,
    notify_letter_created,
    parse_esp_payload,
    save_signature_image,
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
            Letter.query.filter(func.lower(Letter.email) == session.get("email", "").lower())
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
            user = get_user_by_username(session.get("username", ""))
            return render_template(
                "form.html",
                app_id="",
                name=user.name if user else session.get("name", ""),
                email=user.email if user else session.get("email", ""),
                phone=user.phone if (user and user.phone) else "",
                request_types=REQUEST_TYPES,
                request_type="Other",
                generation_mode="manual",
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
        user = get_user_by_username(session.get("username", ""))
        if not user:
            session.clear()
            return redirect(url_for("login"))

        name = user.name.strip()
        email = user.email.strip()

        # Read phone from form input first, fallback to user profile
        form_phone = request.form.get("phone", "").strip()
        phone = form_phone if form_phone else (user.phone.strip() if user.phone else "")

        generation_mode = request.form.get("generation_mode", "").strip().lower()
        action = request.form.get("action", "").strip().lower()
        preview_token = request.form.get("preview_token", "").strip()
        request_type = request.form.get("request_type", "").strip()
        original_description = normalize_letter_description(
            request.form.get("ai_description", "") if generation_mode == "ai" else request.form.get("description", "")
        )
        subject = request.form.get("subject", "").strip()
        signature = request.files.get("signature")
        preview = session.get("ai_preview") or {}
        using_preview = generation_mode == "ai" and action in {"accept", "regenerate"}

        if using_preview:
            if preview.get("token") != preview_token:
                return render_template("form.html", errors=["This preview has expired. Please generate it again."], request_types=REQUEST_TYPES, generation_mode="ai"), 400
            request_type = preview.get("request_type", "")
            original_description = preview.get("original_description", "")
            name = preview.get("name", name)
            email = preview.get("email", email)
            phone = preview.get("phone", phone)

        errors = []
        if len(name) < 2:
            errors.append("Name is required.")
        if "@" not in email:
            errors.append("A valid email is required.")
        if not phone or not is_valid_phone(phone):
            errors.append("Enter a valid 10-digit phone number.")
        if generation_mode not in {"manual", "ai"}:
            errors.append("Choose a valid generation mode.")
        if generation_mode == "ai" and request_type not in REQUEST_TYPES:
            errors.append("Choose a valid request type.")
        if generation_mode == "manual" and len(subject) < 3:
            errors.append("Subject is required.")
        if not using_preview and len(original_description) < 10:
            errors.append("Description must be at least 10 characters.")
        if not using_preview and len(original_description) > settings.MAX_LETTER_DESCRIPTION_LENGTH:
            errors.append(f"Description must stay within {settings.MAX_LETTER_DESCRIPTION_LENGTH} characters so the letter fits on one page.")
        if signature and signature.filename:
            signature.stream.seek(0, os.SEEK_END)
            signature_size = signature.stream.tell()
            signature.stream.seek(0)
            extension = os.path.splitext(secure_filename(signature.filename))[1].lower()
            if signature_size > settings.MAX_SIGNATURE_SIZE:
                errors.append("Signature image must be 2 MB or smaller.")
            if extension not in {".png", ".jpg", ".jpeg"}:
                errors.append("Signature must be a PNG, JPG, or JPEG image.")

        if errors:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"status": "error", "errors": errors}), 400
            return render_template(
                "form.html",
                errors=errors,
                app_id="",
                name=name,
                email=email,
                request_types=REQUEST_TYPES,
                request_type=request_type,
                phone=phone,
                generation_mode=generation_mode,
                subject=subject,
                description=original_description,
            ), 400

        # Persist phone to profile automatically if missing
        if phone and not user.phone:
            user.phone = phone
            db.session.commit()

        if generation_mode == "ai" and action not in {"accept", "regenerate"}:
            try:
                generated = generate_letter_content(request_type, original_description)
            except AIGenerationError as exc:
                return render_template(
                    "form.html",
                    errors=[str(exc) or "Letter generation is temporarily unavailable."],
                    app_id="",
                    name=name,
                    email=email,
                    request_types=REQUEST_TYPES,
                    request_type=request_type,
                    generation_mode=generation_mode,
                    ai_description=original_description,
                ), 503
            preview_token = secrets.token_urlsafe(32)
            session["ai_preview"] = {
                "token": preview_token,
                "name": name,
                "email": email,
                "phone": phone,
                "request_type": request_type,
                "original_description": original_description,
                "subject": generated["subject"],
                "body": generated["body"],
            }
            if signature and signature.filename:
                try:
                    session["ai_preview"]["signature_file_name"] = save_signature_image(signature, preview_token)
                except Exception:
                    return render_template("form.html", errors=["The signature file could not be read as a valid image."], request_types=REQUEST_TYPES, generation_mode="ai"), 400
            return render_template(
                "form.html",
                preview=generated,
                preview_token=preview_token,
                request_types=REQUEST_TYPES,
                request_type=request_type,
                generation_mode="ai",
            )

        if generation_mode == "ai":
            if action == "regenerate":
                try:
                    generated = generate_letter_content(preview["request_type"], preview["original_description"])
                except AIGenerationError as exc:
                    return render_template("form.html", errors=[str(exc) or "Letter generation is temporarily unavailable."], request_types=REQUEST_TYPES, generation_mode="ai"), 503
                preview.update(generated)
                session["ai_preview"] = preview
                return render_template("form.html", preview=generated, preview_token=preview_token, request_types=REQUEST_TYPES, request_type=preview["request_type"], generation_mode="ai")
            request_type = preview["request_type"]
            name = preview["name"]
            email = preview["email"]
            phone = preview["phone"]
            original_description = preview["original_description"]
            try:
                accepted = validate_generated_content(
                    {"subject": request.form.get("preview_subject", ""), "body": request.form.get("preview_body", "")},
                    original_description,
                )
            except AIGenerationError:
                return render_template("form.html", errors=["The edited letter content is invalid. Please review and try again."], preview=preview, preview_token=preview_token, request_types=REQUEST_TYPES, request_type=request_type, generation_mode="ai"), 400
            subject = accepted["subject"]
            description = accepted["body"]
            content_source = "ai_edited" if subject != preview["subject"] or description != preview["body"] else "ai_generated"
            session.pop("ai_preview", None)
        else:
            description = original_description
            content_source = "manual"

        app_id = generate_app_id()
        signature_file_name = preview.get("signature_file_name") if generation_mode == "ai" else None
        if signature and signature.filename:
            try:
                signature_file_name = save_signature_image(signature, app_id)
            except Exception:
                return render_template(
                    "form.html",
                    errors=["The signature file could not be read as a valid image."],
                    app_id="",
                    name=name,
                    email=email,
                    request_types=REQUEST_TYPES,
                    request_type=request_type,
                    phone=phone,
                    generation_mode=generation_mode,
                    subject=subject,
                    description=description,
                ), 400
        if not signature_file_name:
            signature_file_name = user.signature_file_name

        letter = Letter(
            app_id=app_id,
            name=name,
            email=email,
            phone=phone,
            request_type=request_type if generation_mode == "ai" else "Other",
            generation_mode=generation_mode,
            content_source=content_source,
            subject=subject,
            description=description,
            original_description=original_description,
            generated_subject=subject if generation_mode == "ai" else None,
            generated_body=description if generation_mode == "ai" else None,
            signature_file_name=signature_file_name,
            status=settings.STATUS_CREATED,
            created_at=utc_now(),
        )
        db.session.add(letter)
        db.session.commit()

        output_path = ensure_letter_file(letter)
        notifications = notify_letter_created(letter)

        download_url = url_for("download_letter", app_id=app_id)
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify(
                {
                    "status": "ok",
                    "message": f"Letter created successfully. {notification_summary(notifications)}",
                    "app_id": app_id,
                    "download": download_url,
                    "file": os.path.basename(output_path),
                    "notifications": notifications,
                }
            )

        return redirect(
            url_for(
                "student_dashboard",
                submitted=app_id,
                email_status=notifications.get("email", "not_configured"),
                sms_status=notifications.get("sms", "not_configured"),
            )
        )

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
        data = parse_esp_payload()
        code = str(data.get("code") or data.get("barcode") or data.get("app_id") or "").strip()
        if not code:
            return jsonify_error("Invalid data.")

        db.session.add(ScanLog(code=code, created_at=utc_now()))
        db.session.commit()

        app.logger.info("Scanned code received")
        return jsonify({"status": "received"})