# Letterbox Management System

URL: https://letter-tracking-ee-mit.onrender.com/login

A Flask-based web application for managing student letter requests and staff approvals using QR workflows, document generation, and support for PostgreSQL deployment.

## Overview

This project provides a complete digital letterbox system for academic institutions. Students can submit formal letter requests, generate printable documents, and track progress. Staff and administrators can manage requests, scan QR codes, approve letters, and use ESP hardware integration for automated workflows.

## Key features

- Student portal for creating, tracking, and downloading formal letters
- Staff/admin dashboard for managing letter requests and workflows
- QR code generation for every letter request
- Downloadable letter documents in `DOCX` or fallback `TXT` format
- Status workflow: `Created` → `Submitted` → `Pending` → `Approved`
- Role-based access control with separate student and staff login pages
- Optional student self-signup and institute email domain restriction
- Optional Google reCAPTCHA support for public forms
- Secure authentication with hashed passwords and CSRF protection
- SMTP email notifications for request creation and status changes
- Optional Twilio SMS notifications for request creation and status changes
- Local email audit log in `sent_emails/`
- Optional ESP integration for hardware device scanning and remote approval
- Local Ollama AI assistance for standardized letter subjects and bodies
- Works with SQLite locally and PostgreSQL in production
- Gunicorn-ready deployment with `Procfile`

## Repository structure

```text
.
├── app.py
├── Procfile
├── README.md
├── requirements.txt
├── .env.example
├── scripts/
│   └── migrate_sqlite_to_postgres.py
├── letterbox/
│   ├── __init__.py
│   ├── auth.py
│   ├── database.py
│   ├── extensions.py
│   ├── models.py
│   ├── routes_auth.py
│   ├── routes_staff.py
│   ├── routes_student.py
│   ├── services.py
│   └── settings.py
├── templates/
│   ├── admin.html
│   ├── form.html
│   ├── login.html
│   ├── staff_dashboard.html
│   ├── student_dashboard.html
│   ├── status.html
│   ├── student_scan.html
│   ├── scanners.html
│   └── ...
├── static/
│   ├── generated_letters/
│   ├── qr_codes/
│   └── barcodes/
├── sent_emails/
└── docs/
```

## Technology stack

- Python 3
- Flask 3
- Flask-SQLAlchemy
- Flask-WTF
- Gunicorn
- PostgreSQL (recommended for production)
- `python-docx` for DOCX generation
- `qrcode` for QR code generation
- Optional `pyzbar` and `Pillow` for barcode/QR decoding
- SMTP email support via `smtplib`
- Ollama local model support via its HTTP API

## Prerequisites

- Python 3.11+ (recommended)
- `pip`
- PostgreSQL for production deployments (optional for local SQLite)
- SMTP credentials for email notifications (optional)

## Local development setup

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

4. Edit `.env` and configure your values.

5. Start the application:

```powershell
python app.py
```

6. Visit:

- Student login: `http://127.0.0.1:5000/login`
- Staff login: `http://127.0.0.1:5000/staff/login`

## Environment configuration

Use `.env` or actual environment variables to configure the app. Important values include:

- `APP_ENV` — `development` or `production`
- `SECRET_KEY` — used for session signing
- `DATABASE_URL` — SQLite or PostgreSQL connection string
- `APP_BASE_URL` — public base URL for generated links
- `INSTITUTE_NAME`, `DEPARTMENT_TITLE`, `CAMPUS_TITLE`, `CITY_TITLE`
- `LETTER_HEADING` — letter heading text
- `INSTITUTE_EMAIL_DOMAINS` — comma-separated allowed domains for student signup
- `ALLOW_STUDENT_SELF_SIGNUP` — `true` / `false`
- `INITIAL_STAFF_USERNAME`, `INITIAL_STAFF_PASSWORD`, `INITIAL_STAFF_EMAIL`
- `ADMIN_ACCESS_KEY` — optional staff login key
- `RECAPTCHA_SITE_KEY`, `RECAPTCHA_SECRET_KEY`
- `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_USE_TLS`, `MAIL_USE_SSL`, `MAIL_DEFAULT_SENDER`
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`
- `SMS_ENABLED`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`
- `ESP_TOKEN`, `ESP32_HOST`
- `AI_OLLAMA_URL`, `AI_MODEL`, `AI_TIMEOUT`, `AI_MAX_BODY_LENGTH`
- `SESSION_IDLE_MINUTES` — automatic logout after inactivity; defaults to 5 minutes

### Local AI letter generation

Install Ollama and download the local model:

```powershell
ollama pull qwen2.5:1.5b-instruct
ollama serve
```

Student descriptions are sent only to the local Ollama service at `AI_OLLAMA_URL`. The application stores the original description separately from the generated subject and body, validates the structured response, and then places only the validated variable content into the existing DOCX/TXT template. If Ollama is unavailable or output validation fails, no letter record is created.

### Recommended production settings

```env
APP_ENV=production
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=postgresql://user:pass@host:5432/dbname
APP_BASE_URL=https://your-app.example.com
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=Lax
INSTITUTE_EMAIL_DOMAINS=mit.edu,mitindia.edu
INITIAL_STAFF_USERNAME=officeadmin
INITIAL_STAFF_PASSWORD=ChangeThisImmediately123!
INITIAL_STAFF_EMAIL=officeadmin@mit.edu
ADMIN_ACCESS_KEY=replace-with-a-second-secret
RECAPTCHA_SITE_KEY=...
RECAPTCHA_SECRET_KEY=...
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=you@example.com
MAIL_PASSWORD=...
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_DEFAULT_SENDER=you@example.com

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@example.com
SMTP_PASS=...
SMS_ENABLED=false
SMS_DEFAULT_COUNTRY_CODE=+91
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+1xxxxxxxxxx
ESP_TOKEN=optional-esp-token
ESP32_HOST=esp-device.local
```

## Running in production

The application is ready for WSGI deployment. Example using Gunicorn:

```powershell
gunicorn app:app
```

A `Procfile` is included for platforms like Render:

```text
web: gunicorn app:app
```

## Database options

- Local development: default SQLite `database.db`
- Production: PostgreSQL via `DATABASE_URL`

### Migrate SQLite to PostgreSQL

If you started with SQLite and want to move to PostgreSQL:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py
```

Or specify a source SQLite file:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py database.db
```

## Application capabilities

### Student users

- Register and login
- Create letter requests with name, email, phone, subject, and description
- Download generated letter documents
- Track status through the workflow
- Scan QR codes for status lookups

### Staff and admin users

- Login with staff credentials and optional admin key
- View dashboard with letter counts by status
- Review and change letter status to `Submitted`, `Pending`, or `Approved`
- Generate new QR placeholders
- Scan QR codes or barcode uploads
- Manage staff accounts via admin panel

### QR / hardware support

- Every letter request generates a QR code linked to its status page
- ESP device integration via `/esp_submit`, `/esp_approve`, or `/esp_action`
- ESP32 and ESP8266 devices can POST status updates directly to Render using `/esp_submit`, `/esp_approve`, or `/esp_action`. JSON, form-encoded, and query-string payloads are supported; the scanned value may be sent as `id`, `app_id`, `code`, `barcode`, or `qr`.
- Use `X-ESP-Token` header or `token` body field when `ESP_TOKEN` is configured
- Example device payload:

```json
{
  "id": "LETTER123",
  "action": "submit",
  "token": "your-esp-token"
}
```


## Security and reliability

- CSRF protection via Flask-WTF
- Password hashing using Werkzeug
- Role-aware access control for student, staff, and admin routes
- Secure session cookies and configurable `SESSION_COOKIE_SECURE`
- Optional reCAPTCHA on authentication and signup forms
- Local email audit copies in `sent_emails/`
- Structured stdout logging for cloud hosting

## File generation and storage

- QR codes are stored in `static/qr_codes/`
- Generated letters are stored in `static/generated_letters/`
- Barcode images are optionally stored in `static/barcodes/`
- Generated artifacts are recreated automatically if missing in ephemeral storage

## Deployment recommendations

- Use PostgreSQL in production
- Enable `SESSION_COOKIE_SECURE=true`
- Set a strong `SECRET_KEY` and staff access key
- Configure SMTP for real email notifications
- Protect the app behind HTTPS

## Troubleshooting

- If email delivery fails, configure a real SMTP account. Gmail requires an App Password (not the normal account password); use `MAIL_USE_TLS=true` with port 587, or `MAIL_USE_SSL=true` with port 465.
- The `sent_emails/` directory is an audit copy only; it is not proof that SMTP delivery succeeded.
- For SMS, configure a Twilio account and an E.164 sender number. Indian 10-digit student numbers are normalized with `SMS_DEFAULT_COUNTRY_CODE` (default `+91`).
- See `docs/esp_https.md` for ESP32 and ESP8266 HTTPS POST examples.
- If reCAPTCHA is enabled, ensure both site and secret keys are valid
- If QR generation fails, verify `qrcode` and `Pillow` are installed
- If document downloads fallback to `.txt`, check `python-docx` availability

## Notes

- This repository is designed as an academic/demo system for campus letter workflows.
- The code includes a developer helper route at `/debug-users` for user inspection.

## License

Use this repository under your preferred academic or open-source license.
