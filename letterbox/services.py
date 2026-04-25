"""Business logic for letters, workflow status updates, documents, and messaging."""

from __future__ import annotations

import os
import re
import smtplib
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import qrcode
import requests as _requests
from flask import current_app, has_request_context, jsonify, request, session, url_for
from sqlalchemy import func

from . import settings
from .auth import normalize_email
from .database import ensure_dirs
from .extensions import db
from .models import Letter

try:
    from docx import Document
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Inches, Pt

    HAVE_DOCX = True
except Exception:
    HAVE_DOCX = False

try:
    from PIL import Image

    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

try:
    from pyzbar.pyzbar import decode as zbar_decode

    HAVE_PYZBAR = True
except Exception:
    HAVE_PYZBAR = False

try:
    from barcode import Code128
    from barcode.writer import ImageWriter

    HAVE_BARCODE = True
except Exception:
    HAVE_BARCODE = False


IST_ZONE = ZoneInfo("Asia/Kolkata")


def utc_now() -> datetime:
    """Return a timezone-aware datetime for audit fields."""
    return datetime.now(timezone.utc)


def to_ist(value: datetime | None) -> datetime | None:
    """Convert stored UTC datetimes into Asia/Kolkata timezone."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(IST_ZONE)


def serialize_datetime(value: datetime | None) -> str | None:
    """Convert datetimes into stable IST ISO strings for templates and JSON."""
    if value is None:
        return None
    value = to_ist(value)
    return value.replace(microsecond=0).isoformat()


def format_letter_date(value: datetime | None) -> str:
    """Format stored timestamps for the formal letter header."""
    if value is None:
        return datetime.now(IST_ZONE).strftime("%d %B %Y")
    return to_ist(value).strftime("%d %B %Y")


def sentence_case(text: str) -> str:
    """Convert short user-entered subjects into a cleaner display form."""
    value = re.sub(r"\s+", " ", text or "").strip(" .")
    if not value:
        return ""
    return value[0].upper() + value[1:]


def normalize_letter_description(text: str) -> str:
    """Keep the student's wording, but trim noise so the letter stays readable and on one page."""
    paragraphs = []
    for raw_line in (text or "").splitlines():
        cleaned = re.sub(r"\s+", " ", raw_line).strip()
        if cleaned:
            paragraphs.append(cleaned)
    return "\n".join(paragraphs).strip()


def build_formal_letter_content(letter: Letter) -> dict[str, object]:
    """Build the fixed-format formal letter content used for DOCX and TXT export."""
    subject = sentence_case(letter.subject) or "Request"
    body_text = normalize_letter_description(letter.description)
    return {
        "heading_line": settings.LETTER_HEADING,
        "from_lines": [
            letter.name,
            letter.email,
            letter.phone,
        ],
        "date_line": format_letter_date(letter.created_at),
        "to_lines": [
            "The Head of the Department",
            settings.LETTER_HEADING,
            "MIT Campus",
            "Anna University",
            settings.CITY_TITLE,
        ],
        "subject_line": f"{subject} - Reg.",
        "body_text": body_text,
    }


def serialize_letter(letter: Letter) -> dict[str, str | None]:
    """Convert a letter model into a JSON-safe structure."""
    return {
        "app_id": letter.app_id,
        "name": letter.name,
        "email": letter.email,
        "phone": letter.phone,
        "subject": letter.subject,
        "description": letter.description,
        "status": letter.status,
        "created_at": serialize_datetime(letter.created_at),
        "submitted_at": serialize_datetime(letter.submitted_at),
        "approved_at": serialize_datetime(letter.approved_at),
    }


def is_allowed_institute_email(email: str) -> bool:
    """Restrict public student signup to configured institute domains."""
    email = normalize_email(email)
    if "@" not in email:
        return False
    if not settings.ALLOWED_EMAIL_DOMAINS:
        return True
    return email.rsplit("@", 1)[1] in settings.ALLOWED_EMAIL_DOMAINS


def generate_app_id() -> str:
    """Generate a short unique letter identifier."""
    for _ in range(10):
        app_id = uuid.uuid4().hex[:8]
        if not db.session.get(Letter, app_id):
            return app_id
    raise RuntimeError("Unable to generate a unique application ID")


def build_submit_url(app_id: str) -> str:
    """Build the QR payload URL for status tracking."""
    path = f"/submit?id={app_id}"
    if settings.APP_BASE_URL:
        return f"{settings.APP_BASE_URL}{path}"
    if has_request_context():
        return url_for("submit", id=app_id, _external=True)
    return path


def extract_app_id(text: str | None) -> str | None:
    """Extract the tracked letter ID from URLs, raw codes, or fallback payloads."""
    if not text:
        return None

    value = text.strip()
    if not value:
        return None

    try:
        parsed = urlparse(value)
        params = parse_qs(parsed.query)
        if params.get("id"):
            return params["id"][0].strip()
    except Exception:
        pass

    pipe_parts = [part.strip() for part in value.split("|") if part.strip()]
    if pipe_parts:
        last = pipe_parts[-1]
        if re.fullmatch(r"[A-Za-z0-9_-]{6,32}", last):
            return last

    if re.fullmatch(r"[A-Za-z0-9_-]{6,32}", value):
        return value

    match = re.search(r"[?&]id=([A-Za-z0-9_-]{6,32})", value)
    if match:
        return match.group(1)

    return None


def letter_belongs_to_current_user(letter: Letter) -> bool:
    """Restrict student access to only their own letters."""
    if session.get("role") in {"staff", "admin"}:
        return True
    return session.get("role") == "student" and normalize_email(letter.email) == session.get("email")


def get_letter(app_id: str) -> Letter | None:
    """Fetch a letter by its tracked ID."""
    return db.session.get(Letter, app_id)


def update_letter_status(app_id: str, new_status: str) -> Letter | None:
    """Advance the workflow and stamp important lifecycle dates."""
    if new_status not in settings.VALID_STATUSES:
        raise ValueError("Invalid status")

    letter = db.session.get(Letter, app_id)
    if not letter:
        return None

    current_status = letter.status
    if current_status != new_status and new_status not in settings.STATUS_FLOW.get(current_status, set()):
        raise ValueError(f"Cannot move letter from {current_status} to {new_status}")

    if current_status != new_status:
        timestamp = utc_now()
        letter.status = new_status
        if new_status == settings.STATUS_SUBMITTED and not letter.submitted_at:
            letter.submitted_at = timestamp
        if new_status == settings.STATUS_APPROVED and not letter.approved_at:
            letter.approved_at = timestamp
        db.session.commit()

    return letter


def build_artifact_name(app_id: str, extension: str, existing_name: str | None = None) -> str:
    """Create stable unique artifact names for generated files."""
    if existing_name:
        return existing_name
    return f"{app_id}_{uuid.uuid4().hex[:10]}.{extension}"


def create_qr_assets(letter: Letter) -> tuple[str, str | None]:
    """Generate QR and optional Code128 barcode images for a letter."""
    ensure_dirs()
    letter.qr_file_name = build_artifact_name(letter.app_id, "png", letter.qr_file_name)
    qr_path = os.path.join(settings.QR_DIR, letter.qr_file_name)
    payload = build_submit_url(letter.app_id)
    img = qrcode.make(payload)
    img.save(qr_path)

    barcode_path = None
    if HAVE_BARCODE:
        try:
            barcode_filebase = os.path.join(settings.BARCODE_DIR, letter.app_id)
            Code128(payload, writer=ImageWriter()).save(barcode_filebase)
            barcode_path = f"{barcode_filebase}.png"
        except Exception as exc:
            current_app.logger.warning("Failed to generate barcode for %s: %s", letter.app_id, exc)

    db.session.commit()
    return qr_path, barcode_path


def generate_letter_file(letter: Letter) -> str:
    """Create a compact downloadable letter that works well on both mobile and desktop downloads."""
    ensure_dirs()
    qr_path, _ = create_qr_assets(letter)
    letter_content = build_formal_letter_content(letter)
    extension = "docx" if HAVE_DOCX else "txt"
    letter.generated_file_name = build_artifact_name(letter.app_id, extension, letter.generated_file_name)
    output_path = os.path.join(settings.GEN_DIR, letter.generated_file_name)

    if HAVE_DOCX:
        doc = Document()
        section = doc.sections[0]
        section.top_margin = Inches(0.4)
        section.bottom_margin = Inches(0.4)
        section.left_margin = Inches(0.65)
        section.right_margin = Inches(0.65)

        normal_style = doc.styles["Normal"]
        normal_style.font.name = "Times New Roman"
        normal_style.font.size = Pt(10.5)

        heading = doc.add_paragraph()
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        heading_run = heading.add_run(letter_content["heading_line"])
        heading_run.bold = True
        heading_run.font.size = Pt(13)

        doc.add_paragraph()

        top_table = doc.add_table(rows=1, cols=2)
        top_table.alignment = WD_TABLE_ALIGNMENT.LEFT
        top_table.autofit = False
        left_cell = top_table.cell(0, 0)
        right_cell = top_table.cell(0, 1)

        from_paragraph = left_cell.paragraphs[0]
        from_paragraph.add_run("From:\n").bold = True
        from_paragraph.add_run("\n".join(letter_content["from_lines"]))

        qr_paragraph = right_cell.paragraphs[0]
        qr_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        qr_paragraph.add_run().add_picture(qr_path, width=Inches(0.9))

        doc.add_paragraph()
        doc.add_paragraph(letter_content["date_line"])
        doc.add_paragraph()

        to_paragraph = doc.add_paragraph()
        to_paragraph.add_run("To,\n").bold = True
        to_paragraph.add_run("\n".join(letter_content["to_lines"]))

        doc.add_paragraph()
        doc.add_paragraph("Respected Sir/Mam,")

        subject_paragraph = doc.add_paragraph()
        subject_paragraph.add_run("Sub").bold = True
        subject_paragraph.add_run(" : ")
        subject_paragraph.add_run(letter_content["subject_line"])

        for paragraph_text in (letter_content["body_text"] or "").splitlines():
            body_paragraph = doc.add_paragraph(paragraph_text)
            body_paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        doc.add_paragraph()
        doc.add_paragraph("Yours sincerely,")
        doc.add_paragraph("")
        doc.add_paragraph("")
        doc.add_paragraph(letter.name)

        doc.save(output_path)
    else:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(f"{letter_content['heading_line'].center(70)}\n")
            handle.write("\n")
            handle.write("From:\n")
            for line in letter_content["from_lines"]:
                handle.write(f"{line}\n")
            handle.write("\n")
            handle.write(f"{letter_content['date_line']}\n\n")
            handle.write("To,\n")
            for line in letter_content["to_lines"]:
                handle.write(f"{line}\n")
            handle.write("\n")
            handle.write("Respected Sir/Mam,\n")
            handle.write(f"Sub : {letter_content['subject_line']}\n")
            handle.write(f"{letter_content['body_text']}\n\n")
            handle.write("Yours sincerely,\n")
            handle.write("\n\n")
            handle.write(f"{letter.name}\n")

    db.session.commit()
    return output_path


def ensure_letter_file(letter: Letter) -> str:
    """Return a valid generated letter file path, recreating it when storage is ephemeral."""
    if letter.generated_file_name:
        current_path = os.path.join(settings.GEN_DIR, letter.generated_file_name)
        if os.path.exists(current_path):
            return current_path
    return generate_letter_file(letter)


def send_email(to_email: str, message: str, subject: str = "Notification", ref: str | None = None) -> None:
    """Send email notifications and always keep a local .eml audit copy."""
    if not to_email:
        current_app.logger.info("Skipping email because recipient is empty")
        return

    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_user or "no-reply@example.com"
    msg["To"] = to_email
    msg.set_content(message)

    try:
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        ref_part = f"{ref}_" if ref else ""
        file_name = f"{ref_part}{stamp}_{uuid.uuid4().hex[:8]}.eml"
        file_path = os.path.join(settings.SENT_DIR, file_name)
        with open(file_path, "w", encoding="utf-8") as handle:
            handle.write(f"From: {msg['From']}\n")
            handle.write(f"To: {msg['To']}\n")
            handle.write(f"Subject: {msg['Subject']}\n\n")
            handle.write(message)
    except Exception as exc:
        current_app.logger.warning("Failed to save local email copy: %s", exc)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            if smtp_port in (25, 587):
                try:
                    server.starttls()
                except Exception:
                    current_app.logger.debug("SMTP server does not support STARTTLS")
            if smtp_user and smtp_pass and smtp_host != "localhost":
                server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        current_app.logger.info("Email sent to %s", to_email)
    except Exception as exc:
        current_app.logger.warning("Failed to send email to %s: %s", to_email, exc)


def jsonify_error(message: str, status_code: int = 400, **payload):
    """Return a consistent JSON error body for AJAX and ESP clients."""
    body = {"status": "error", "message": message}
    body.update(payload)
    return jsonify(body), status_code


def verify_recaptcha(form_token: str | None) -> tuple[bool, str | None]:
    """Verify a Google reCAPTCHA response when keys are configured."""
    if not settings.RECAPTCHA_ENABLED:
        return True, None

    token = (form_token or "").strip()
    if not token:
        return False, "Please complete the reCAPTCHA challenge."

    remote_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    payload = {
        "secret": settings.RECAPTCHA_SECRET_KEY,
        "response": token,
        "remoteip": remote_ip.split(",")[0].strip(),
    }
    try:
        response = _requests.post("https://www.google.com/recaptcha/api/siteverify", data=payload, timeout=8)
        data = response.json()
    except Exception as exc:
        current_app.logger.warning("reCAPTCHA verification failed: %s", exc)
        return False, "Unable to verify reCAPTCHA right now. Please try again."

    if data.get("success"):
        return True, None
    current_app.logger.info("reCAPTCHA rejected request: %s", data.get("error-codes", []))
    return False, "reCAPTCHA verification failed. Please try again."


def esp_token_valid(data) -> bool:
    """Validate the optional ESP device token for hardware endpoints."""
    expected = os.environ.get("ESP_TOKEN", "").strip()
    if not expected:
        return True

    token = request.headers.get("X-ESP-Token", "").strip()
    if not token and hasattr(data, "get"):
        token = str(data.get("token", "")).strip()
    return token == expected


def infer_esp_action(data) -> str | None:
    """Infer submit/approve actions from explicit action or ESP device identity."""
    action = ""
    if hasattr(data, "get"):
        action = str(data.get("action", "")).strip().lower()
        if action in {"submit", "approve"}:
            return action

        device_id = str(data.get("device_id", "") or data.get("device", "") or data.get("node_id", "") or "").strip()
        if device_id:
            inbox = settings.ESP_INBOX_DEVICE_ID.lower()
            outbox = settings.ESP_OUTBOX_DEVICE_ID.lower()
            if inbox and device_id.lower() == inbox:
                return "submit"
            if outbox and device_id.lower() == outbox:
                return "approve"
    return None


def fetch_esp_payload(esp_host: str):
    """Query the ESP endpoint and normalize the response for the staff scanner UI."""
    candidate_paths = ["/data", "/"]
    tried = []
    last_error = None
    headers = {"Connection": "close", "User-Agent": "Mozilla/5.0"}

    for path in candidate_paths:
        url = f"http://{esp_host}{path}"
        tried.append(url)
        try:
            response = _requests.get(url, timeout=4, headers=headers)
            if response.status_code >= 400:
                continue
            try:
                return response.json(), None
            except Exception:
                text = response.text or ""
                app_id = extract_app_id(text)
                if app_id:
                    return {"app_id": app_id, "barcode": app_id, "raw": text, "source": url}, None
                stripped = re.sub(r"<[^>]+>", "", text).strip()
                if stripped:
                    return {"barcode": stripped, "raw": text, "source": url}, None
        except Exception as exc:
            last_error = exc
            current_app.logger.debug("ESP fetch failed for %s: %s", url, exc)

    return None, {"tried": tried, "error": str(last_error) if last_error else ""}


def decode_uploaded_scan(file_storage):
    """Decode a QR or barcode image uploaded by staff."""
    if not HAVE_PIL or not HAVE_PYZBAR:
        raise RuntimeError("Server is missing Pillow or pyzbar for barcode decoding.")

    image = Image.open(file_storage.stream).convert("RGB")
    decoded = zbar_decode(image)
    if not decoded:
        raise ValueError("No barcode or QR code found in the image.")

    texts = [item.data.decode("utf-8") for item in decoded]
    return texts
