# 📬 IoT-Enabled Letter Tracking & Automated Academic Requisition System

![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0%2B-000000?style=for-the-badge&logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=for-the-badge&logo=postgresql&logoColor=white)
![AI](https://img.shields.io/badge/AI-Groq%20Llama%203.3%2070B-F05032?style=for-the-badge)
![Deployment](https://img.shields.io/badge/Render-Cloud%20Hosted-46E3B7?style=for-the-badge&logo=render&logoColor=white)

An end-to-end **IoT and cloud-integrated platform** designed to digitize and automate formal institutional requisition workflows.

The system streamlines formal letter generation using **LLM-based natural language processing**, embeds dynamic **QR/barcode verification tags** into standardized `.docx` documents, tracks physical letterbox lifecycle transitions through **ESP32/ESP8266 optical scanners**, and sends automated **email and SMS notifications** to students and staff.

---

## 📑 Table of Contents

- [Key Features](#-key-features)
- [System Architecture & Workflow](#-system-architecture--workflow)
- [Technology Stack](#-technology-stack)
- [Project Directory Structure](#-project-directory-structure)
- [Database & Security Architecture](#-database--security-architecture)
- [Hardware & IoT Scanner Interface](#-hardware--iot-scanner-interface)
- [Environment Variables](#-environment-variables)
- [Local Installation & Setup](#-local-installation--setup)
- [Deployment on Render](#-deployment-on-render)
- [Security Notes](#-security-notes)
- [Future Improvements](#-future-improvements)
- [License](#-license)

---

## 🌟 Key Features

### 1. 🤖 AI-Powered Formal Letter Generation

- **Cloud LLM Pipeline:** Integrates the **Groq Cloud API** using `llama-3.3-70b-versatile` to transform brief student explanations such as Medical Leave, On-Duty, and Lab Permission requests into formal academic requisitions.
- **Resilient Fallback Engine:** Provides deterministic rule-based template generation when cloud API limits or network failures occur.
- **Draft & Preview Architecture:** Students can preview, customize, regenerate, and edit AI-generated drafts before final submission.

### 2. 📄 Standardized Document & Verification Engine

- **Academic Formatting:** Generates dynamic `.docx` documents containing the department header, student credentials, reference date, formal body, and student signature.
- **Persistent Digital Signatures:** Stores signatures as Base64-encoded data in PostgreSQL `TEXT` columns so they can be dynamically resolved and embedded into generated documents.
- **HoD Verification Seal:** Adds an authenticated green `✓ Digitally verified by the HoD` seal after departmental approval.
- **QR/Barcode Tracking:** Generated documents contain unique tracking information that can be scanned by the physical letterbox system.

### 3. 📡 IoT Hardware Tracking & Scanning

- **Physical-to-Digital Synchronization:** Integrates ESP32/ESP8266 optical scanners with physical department Inbox/Outbox letter collection units.
- **Barcode & QR Payloads:** Embeds unique tracking URLs and serial identifiers into generated documents.
- **Automated State Transitions:** Physical scanning can advance an application's lifecycle, for example:

```text
Created → Submitted → Approved
```

### 4. 🔒 Authentication, Authorization & Security

- **Multi-Identifier Authentication:** Supports sign-in using either a Register Number or Institute Email Address.
- **Role-Based Access Control (RBAC):** Separates Student, Staff, and Admin authorization scopes.
- **Staff Master Access:** Supports optional additional verification for privileged staff access.
- **Secure Password Reset:** Uses time-limited, single-use password-reset tokens stored as SHA-256 hashes.
- **Database Hardening:** Uses PostgreSQL/Supabase Row-Level Security (RLS) to restrict unauthorized database access.

### 5. 📬 Real-Time Multi-Channel Notifications

- **Transactional Email:** Uses the Mailjet HTTP API to send HTML and plain-text status notifications.
- **SMS Gateway:** Uses Twilio to send E.164-normalized SMS notifications.
- Notifications can be triggered during important workflow events such as:
  - Letter generation
  - Letter submission
  - Departmental approval

---

## 🔄 System Architecture & Workflow

```text
                         ┌─────────────────────┐
                         │   Student Portal    │
                         │ Prompt / Upload     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │    Groq Cloud API   │
                         │   Llama 3.3 70B     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Automated .docx     │
                         │ Document Generator  │
                         │ QR + Signature      │
                         └──────────┬──────────┘
                                    │
                                    ▼
                            Download / Print
                                    │
                                    ▼
                    ┌────────────────────────────┐
                    │ Physical Department       │
                    │ Letter Drop Box           │
                    └─────────────┬──────────────┘
                                  │
                         QR / Barcode Scan
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │ ESP32 / ESP8266 Scanner   │
                    └─────────────┬──────────────┘
                                  │ HTTP POST
                                  ▼
                    ┌────────────────────────────┐
                    │ Flask Backend              │
                    │ Render / WSGI              │
                    └──────────┬─────────┬───────┘
                               │         │
                    State Update│         │Notifications
                               ▼         ▼
                    ┌───────────────┐  ┌───────────────────┐
                    │ Supabase      │  │ Mailjet + Twilio  │
                    │ PostgreSQL    │  │ Email + SMS       │
                    │ RLS           │  └───────────────────┘
                    └───────┬───────┘
                            │
                            ▼
                    ┌────────────────┐
                    │ Staff / HoD    │
                    │ Dashboard      │
                    │ Approval       │
                    └────────────────┘
```

### Workflow

1. A student creates a requisition through the web portal.
2. The student provides a short description or uses the AI-assisted generation mode.
3. The Groq LLM generates a formal academic letter.
4. The student previews and edits the generated content.
5. The Flask backend generates a standardized `.docx` document.
6. A unique tracking identifier and QR/barcode payload are embedded into the document.
7. The student downloads and prints the letter.
8. The physical letter is deposited into the department letterbox.
9. The ESP32/ESP8266 scanner reads the QR code or barcode.
10. The scanner sends the scanned identifier to the Flask backend.
11. The backend updates the application's status.
12. Staff/HoD users can view and process the application through the dashboard.
13. Email/SMS notifications are dispatched for relevant status changes.

---

## 🛠 Technology Stack

| Layer | Technology / Service | Purpose |
|---|---|---|
| **Backend** | Flask 3.0+, Gunicorn | Production web application and WSGI server |
| **Database** | PostgreSQL / Supabase | Persistent cloud database |
| **ORM** | SQLAlchemy | Database abstraction and model management |
| **AI / Generation** | Groq API + `llama-3.3-70b-versatile` | Formal letter generation |
| **Documents** | `python-docx` | `.docx` document generation |
| **QR Generation** | `qrcode` | QR code generation |
| **Barcode Generation** | `python-barcode` | Barcode generation |
| **Image Processing** | Pillow | Signature and document image processing |
| **Email** | Mailjet v3.1 API | Transactional email delivery |
| **SMS** | Twilio API | SMS notifications |
| **IoT** | ESP32 / ESP8266 | Physical letterbox scanning |
| **Embedded Software** | MicroPython / C++ | Scanner firmware and HTTP communication |
| **Hosting** | Render | Cloud deployment |
| **Version Control / CI** | GitHub / GitHub Actions | Source control and automation |

---

## 📂 Project Directory Structure

```text
.
├── app.py
│
├── letterbox/
│   ├── __init__.py
│   ├── ai_generation.py
│   ├── auth.py
│   ├── database.py
│   ├── extensions.py
│   ├── models.py
│   ├── routes_admin.py
│   ├── routes_auth.py
│   ├── routes_esp.py
│   ├── routes_student.py
│   ├── services.py
│   └── settings.py
│
├── static/
│   └── ...
│
├── templates/
│   └── ...
│
├── requirements.txt
├── Procfile
├── .gitignore
├── .env
└── README.md
```

### Core Modules

| File | Responsibility |
|---|---|
| `app.py` | Application bootstrap and entry point |
| `letterbox/__init__.py` | Flask application factory |
| `letterbox/ai_generation.py` | Groq LLM integration, prompts, and AI generation |
| `letterbox/auth.py` | Authentication, RBAC helpers, validation, and session handling |
| `letterbox/database.py` | Database initialization, migrations, and seeding |
| `letterbox/extensions.py` | SQLAlchemy, CSRF, and external service initialization |
| `letterbox/models.py` | Database models such as users, letters, tokens, and scans |
| `letterbox/routes_admin.py` | Staff/Admin dashboard and verification routes |
| `letterbox/routes_auth.py` | Sign-in, sign-up, and password-reset flows |
| `letterbox/routes_esp.py` | ESP32/ESP8266 IoT endpoints |
| `letterbox/routes_student.py` | Student requisition creation and tracking |
| `letterbox/services.py` | Document generation, encoding, and notification services |
| `letterbox/settings.py` | Centralized environment configuration |
| `static/` | CSS, images, logos, and frontend assets |
| `templates/` | Jinja2 HTML templates |
| `requirements.txt` | Python dependencies |
| `Procfile` | Production start command for Render |
| `.gitignore` | Files excluded from Git |

---

## 🗄 Database & Security Architecture

The application uses **PostgreSQL hosted through Supabase** for persistent cloud storage.

### Database Tables

#### 1. `users`

Stores:

- User credentials
- Hashed passwords
- User roles:
  - `student`
  - `staff`
  - `admin`
- Institute/register identifiers
- Stored Base64 signature data

#### 2. `letters`

Stores:

- Unique application/tracking identifiers
- Student requisition information
- AI generation mode
- AI-generated descriptions
- Application status
- Status timestamps
- Generated document information

Typical status flow:

```text
Created → Submitted → Approved
```

#### 3. `password_reset_tokens`

Stores:

- SHA-256 hashed password-reset tokens
- Token expiration information
- Single-use reset state

Password reset tokens are designed to expire after a limited period.

#### 4. `scans`

Stores hardware scanner audit information, including:

- Raw scanner input
- Device identifier
- Scan action
- Timestamp
- Related application information

### Row-Level Security

Supabase/PostgreSQL Row-Level Security can be enabled on all application tables:

```sql
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

ALTER TABLE letters ENABLE ROW LEVEL SECURITY;

ALTER TABLE scans ENABLE ROW LEVEL SECURITY;

ALTER TABLE password_reset_tokens ENABLE ROW LEVEL SECURITY;
```

> **Important:** The application backend should use appropriately secured server-side PostgreSQL credentials. Never expose database credentials, API secrets, or service-role credentials in client-side code.

---

## 📡 Hardware & IoT Scanner Interface

The physical letterbox uses an **ESP32/ESP8266 microcontroller** connected to a compatible 1D/2D optical scanner.

When a student deposits a printed letter, the scanner reads the document's QR code or barcode and sends the tracking information to the Flask backend.

### Hardware Endpoint

```http
POST /api/esp/scan
```

### Headers

```http
Content-Type: application/json
X-ESP-Token: <ESP_TOKEN>
```

### Request Payload

```json
{
  "code": "https://letter-tracking-ee-mit.onrender.com/submit?id=a1b2c3d4",
  "device_id": "INBOX_NODE_01",
  "action": "submit"
}
```

### Example Response

```json
{
  "status": "ok",
  "app_id": "a1b2c3d4",
  "new_status": "Submitted"
}
```

### IoT Communication Flow

```text
QR / Barcode
     │
     ▼
Optical Scanner
     │
     ▼
ESP32 / ESP8266
     │
     │ HTTP POST
     ▼
Flask API
     │
     ▼
Application Database
     │
     ├── Update Status
     └── Trigger Notifications
```

The shared `ESP_TOKEN` should be treated as a secret and must not be hard-coded into publicly accessible source code.

---

## ⚙️ Environment Variables

Create a `.env` file for local development or configure the following variables in the Render dashboard.

| Variable | Required | Description | Example |
|---|:---:|---|---|
| `DATABASE_URL` | Yes | PostgreSQL/Supabase connection string | `postgresql+psycopg2://user:pass@host:6543/postgres?sslmode=require` |
| `SECRET_KEY` | Yes | Flask cryptographic session key | Generate a secure random value |
| `APP_BASE_URL` | Yes | Application's public base URL | `https://your-app.onrender.com` |
| `GROQ_API_KEY` | Yes | Groq Cloud API key | `gsk_xxxxxxxxxxxx` |
| `ESP_TOKEN` | Optional | Shared IoT authentication token | `secure_device_secret_token` |
| `MAILJET_API_KEY` | Optional | Mailjet public API key | `xxxxxxxxxxxxxxxx` |
| `MAILJET_SECRET_KEY` | Optional | Mailjet secret API key | `xxxxxxxxxxxxxxxx` |
| `MAILJET_SENDER_EMAIL` | Optional | Verified Mailjet sender address | `letterbox@institute.edu` |
| `TWILIO_ACCOUNT_SID` | Optional | Twilio account identifier | `ACxxxxxxxxxxxxxxxx` |
| `TWILIO_AUTH_TOKEN` | Optional | Twilio authentication token | `xxxxxxxxxxxxxxxx` |
| `TWILIO_FROM_NUMBER` | Optional | Twilio virtual number | `+1xxxxxxxxxx` |

### Example Local `.env`

```env
DATABASE_URL=sqlite:///database.db
SECRET_KEY=replace_with_a_secure_random_secret
APP_BASE_URL=http://127.0.0.1:5000
GROQ_API_KEY=gsk_your_groq_key_here

# Optional IoT
ESP_TOKEN=your_secure_esp_token

# Optional Mailjet
MAILJET_API_KEY=
MAILJET_SECRET_KEY=
MAILJET_SENDER_EMAIL=

# Optional Twilio
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
```

### Generating a Secure Secret Key

For local development, a random secret can be generated with Python:

```python
import secrets
print(secrets.token_hex(32))
```

> **Never commit `.env` or real API keys to GitHub.**

---

## 💻 Local Installation & Setup

### Prerequisites

Make sure the following are installed:

- Python 3.11 or 3.12
- Git
- pip
- A supported PostgreSQL database or SQLite for local development
- API credentials for the services you intend to enable

### 1. Clone the Repository



```bash
git clone https://github.com/HARIPRASATH-S-8030/Letter_Tracking_EE_MIT
cd Letter_Tracking_EE_MIT
```

### 2. Create a Virtual Environment

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```env
DATABASE_URL=sqlite:///database.db
SECRET_KEY=replace_with_a_secure_random_secret
APP_BASE_URL=http://127.0.0.1:5000
GROQ_API_KEY=gsk_your_groq_key_here
```

Add Mailjet, Twilio, and ESP configuration if those services are enabled.

### 5. Run the Development Server

```bash
python app.py
```

The application should then be available at:

```text
http://127.0.0.1:5000
```

---

## 🚀 Deployment on Render

The application is designed to run as a Python web service on Render.

### 1. Push the Project to GitHub

```bash
git add .
git commit -m "Prepare application for deployment"
git push origin main
```

### 2. Create a Render Web Service

In Render:

1. Create a new **Web Service**.
2. Connect the GitHub repository.
3. Select the appropriate branch.
4. Configure the Python environment.

### 3. Build Command

```bash
pip install -r requirements.txt
```

### 4. Start Command

```bash
gunicorn app:app
```

### 5. Configure Environment Variables

Add the required variables in the Render **Environment** section:

```text
DATABASE_URL
SECRET_KEY
APP_BASE_URL
GROQ_API_KEY
ESP_TOKEN
MAILJET_API_KEY
MAILJET_SECRET_KEY
MAILJET_SENDER_EMAIL
TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN
TWILIO_FROM_NUMBER
```

Only configure the optional Mailjet, Twilio, and ESP variables if those services are being used.

### 6. Deploy

After saving the configuration, Render will:

```text
GitHub Repository
       │
       ▼
   Build Service
       │
       ▼
pip install -r requirements.txt
       │
       ▼
gunicorn app:app
       │
       ▼
 Flask Application
```

---

## 🔐 Security Notes

This project handles authentication credentials, application information, digital signatures, API credentials, and IoT device authentication tokens. Follow these practices when deploying it publicly.

### Never Commit Secrets

Add sensitive files to `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
*.pyc
*.pyo
instance/
*.db
```

### Protect API Credentials

Do not place the following directly in source code:

- Groq API keys
- Mailjet credentials
- Twilio credentials
- PostgreSQL passwords
- Flask secret keys
- ESP authentication tokens

Use environment variables instead.

### Protect the IoT Endpoint

The ESP endpoint should validate the `X-ESP-Token` before processing scanner requests.

### Use HTTPS

For production deployment, use HTTPS for:

- Student portal access
- Authentication
- Password-reset links
- IoT HTTP requests
- API communication

### Database Access

Do not expose PostgreSQL credentials to the browser or embedded IoT firmware.

---

## 🔁 Application Status Lifecycle

A typical requisition follows this lifecycle:

```text
┌─────────┐
│ Created │
└────┬────┘
     │
     │ Physical letter submitted
     ▼
┌───────────┐
│ Submitted │
└─────┬─────┘
      │
      │ Staff / HoD verification
      ▼
┌──────────┐
│ Approved │
└──────────┘
```

The IoT scanner provides the physical-to-digital transition between the printed document and the web application's tracking record.

---

## 📊 Project Highlights

The project combines several engineering domains into a single workflow:

- **Web Application Development**
- **Artificial Intelligence / LLM Integration**
- **Internet of Things**
- **Embedded Systems**
- **Cloud Computing**
- **Database Management**
- **Document Automation**
- **QR / Barcode Identification**
- **Authentication & Authorization**
- **Transactional Communication**
- **Cloud Deployment**

This makes the system suitable as an academic demonstration of an integrated **IoT + AI + Cloud + Web** application.

---

## 🔮 Future Improvements

Potential extensions include:

- [ ] Real-time WebSocket status updates
- [ ] Dedicated ESP32 firmware repository
- [ ] Offline scan buffering when the network is unavailable
- [ ] Automatic retry and queue management for notifications
- [ ] Admin analytics and reporting dashboards
- [ ] Audit-log visualization
- [ ] More advanced document verification
- [ ] Digital certificate/signature infrastructure
- [ ] Mobile-friendly student interface
- [ ] Docker-based deployment
- [ ] Automated database migrations
- [ ] Automated unit and integration testing
- [ ] CI/CD quality gates through GitHub Actions

---

## 🤝 Contributing

Contributions, improvements, and bug fixes are welcome.

A typical contribution workflow is:

```bash
git checkout -b feature/your-feature
git add .
git commit -m "Add your feature"
git push origin feature/your-feature
```

Then open a Pull Request on GitHub.

---

## 📄 License

This project is intended for academic and educational purposes.

If this repository is released publicly, add the appropriate license file and update this section with the selected license terms.

---

## 👨‍💻 Project

**IoT-Enabled Letter Tracking & Automated Academic Requisition System**

Built using:

**Flask · PostgreSQL · Supabase · Groq Llama 3.3 · ESP32/ESP8266 · Mailjet · Twilio · Render**

