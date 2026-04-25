# Letterbox Management System

Production-ready Flask application for student/staff letter tracking with QR-based workflows, PostgreSQL support, environment-driven configuration, and Gunicorn deployment.

## What changed

- Replaced the SQLite-only access pattern with Flask-SQLAlchemy models that work with both local SQLite and cloud PostgreSQL.
- Added production config through environment variables: `SECRET_KEY`, `DATABASE_URL`, `APP_ENV`, `SESSION_COOKIE_SECURE`, `RECAPTCHA_*`, and more.
- Hardened authentication with Werkzeug password hashing, strong password validation, CSRF protection, secure session cookies, optional Google reCAPTCHA, and role-aware access control.
- Improved file handling so generated QR images and letter files use unique filenames and regenerate automatically if the host's filesystem is ephemeral.
- Added Gunicorn deployment support with `Procfile`.
- Added a one-off migration script to move existing SQLite data into PostgreSQL.

## Project structure

```text
.
|-- app.py
|-- Procfile
|-- requirements.txt
|-- .env.example
|-- scripts/
|   `-- migrate_sqlite_to_postgres.py
|-- letterbox/
|   |-- __init__.py
|   |-- auth.py
|   |-- database.py
|   |-- extensions.py
|   |-- models.py
|   |-- routes_auth.py
|   |-- routes_staff.py
|   |-- routes_student.py
|   |-- services.py
|   `-- settings.py
|-- templates/
|   |-- _brand_banner.html
|   `-- _form_security.html
`-- static/
    |-- generated_letters/
    `-- qr_codes/
```

## Local setup

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Copy the example environment file and set the values you need:

```powershell
Copy-Item .env.example .env
```

4. Set environment variables in PowerShell for the current session:

```powershell
$env:SECRET_KEY="replace-with-a-long-random-secret"
$env:DATABASE_URL="sqlite:///database.db"
$env:INITIAL_STAFF_USERNAME="officeadmin"
$env:INITIAL_STAFF_PASSWORD="ChangeThisImmediately123!"
$env:INITIAL_STAFF_EMAIL="officeadmin@mit.edu"
$env:ADMIN_ACCESS_KEY="set-a-separate-staff-key"
```

5. Start the app:

```powershell
python app.py
```

6. Open `http://127.0.0.1:5000/login`.

## Required production environment variables

- `SECRET_KEY`
- `DATABASE_URL`

## Recommended production environment variables

- `APP_ENV=production`
- `APP_BASE_URL=https://your-app.onrender.com`
- `SESSION_COOKIE_SECURE=true`
- `INSTITUTE_EMAIL_DOMAINS=mit.edu,mitindia.edu`
- `INITIAL_STAFF_USERNAME`
- `INITIAL_STAFF_PASSWORD`
- `INITIAL_STAFF_EMAIL`
- `ADMIN_ACCESS_KEY`
- `RECAPTCHA_SITE_KEY`
- `RECAPTCHA_SECRET_KEY`

## SQLite to PostgreSQL migration

The application can still run locally with SQLite, but cloud deployment should use PostgreSQL.

1. Set `DATABASE_URL` to your PostgreSQL connection string.
2. Run the migration script:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py
```

Optional source file override:

```powershell
.\.venv\Scripts\python.exe scripts\migrate_sqlite_to_postgres.py database.db
```

## Render deployment

Recommended Render settings:

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app`
- Environment: `Python 3`
- Instance Type: `Free`

Suggested environment variables:

```text
APP_ENV=production
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=postgresql://...
SESSION_COOKIE_SECURE=true
APP_BASE_URL=https://your-service.onrender.com
INSTITUTE_EMAIL_DOMAINS=mit.edu,mitindia.edu
INITIAL_STAFF_USERNAME=officeadmin
INITIAL_STAFF_PASSWORD=ChangeThisImmediately123!
INITIAL_STAFF_EMAIL=officeadmin@mit.edu
ADMIN_ACCESS_KEY=replace-with-a-second-secret
RECAPTCHA_SITE_KEY=...
RECAPTCHA_SECRET_KEY=...
```

## Important free-tier notes

- Generated files in `static/generated_letters` and `static/qr_codes` are recreated automatically if the host filesystem is reset.
- Free hosting is fine for an academic project demo, but it is not equal to enterprise production hosting.
- If you use Render Free:
  - web services can spin down after inactivity,
  - local filesystem changes are not durable across deploys/restarts,
  - Free Render Postgres expires after 30 days,
  - common SMTP ports are restricted on Free web services, so email sending may not work there.

Useful docs:

- Render free tier: https://render.com/docs/free
- Render first deploy: https://render.com/docs/your-first-deploy
- Render environment variables: https://render.com/docs/configure-environment-variables
- Render default environment variables: https://render.com/docs/environment-variables
