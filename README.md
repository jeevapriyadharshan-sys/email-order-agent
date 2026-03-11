# 📦 GenAI-Driven Email Order Automation Agent

An intelligent full-stack system that automatically processes freight transport request emails, extracts order details using a two-layer AI pipeline (Regex + Google Gemini), creates transport orders, and sends confirmation emails — all without human intervention.

**Live Demo:**
- 🌐 Frontend: `https://email-order-frontend.onrender.com`
- ⚙️ Backend API: `https://email-order-backend.onrender.com/docs`

---

## 📸 Overview

```
Gmail Inbox
    │
    ▼  (IMAP every 15s)
┌─────────────────────────┐
│   Email Ingestion        │  Fetches UNSEEN emails, deduplicates by Message-ID
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Layer 1: Regex        │  Fast, free, deterministic extraction
└────────────┬────────────┘
             │  missing fields?
             ▼
┌─────────────────────────┐
│   Layer 2: Gemini AI    │  Intelligent extraction — never guesses
└────────────┬────────────┘
             │
     ┌───────┴────────┐
     │                │
     ▼                ▼
All fields OK     Fields missing
     │                │
     ▼                ▼
Create Order    Human Review Queue
     │                │  (reviewer fills in)
     ▼                │
Send Confirmation ◄───┘
Email to Customer
```

---

## ✨ Features

- **Automated Email Ingestion** — connects to Gmail via IMAP every 15 seconds
- **Two-Layer AI Extraction** — regex first (free), Gemini AI fallback (smart)
- **Anti-Hallucination** — Gemini returns `null` for missing fields, never guesses
- **Human Review Workflow** — incomplete emails flagged for reviewer with missing-fields email sent to customer
- **Transport Order Creation** — unique Job IDs generated automatically
- **Confirmation Emails** — sent via Brevo HTTP API (no SMTP needed)
- **Operations Dashboard** — real-time charts: volume, status, KPIs
- **JWT Authentication** — admin and reviewer roles
- **Zero-cost deployment** — Render (free) + Neon PostgreSQL (free forever)

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Recharts |
| Backend | FastAPI, Python 3.11, APScheduler |
| Database | PostgreSQL 17 (Neon serverless) |
| AI Extraction | Google Gemini 1.5 Flash |
| Email Ingestion | IMAP (imaplib) |
| Email Delivery | Brevo HTTP API |
| Auth | JWT (python-jose) |
| ORM | SQLAlchemy + Pydantic |
| Hosting | Render (frontend + backend) |

---

## 📁 Project Structure

```
email-order-agent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, lifespan scheduler
│   │   ├── worker.py            # APScheduler, agent tick, process_email_task
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── config.py            # Settings from env vars
│   │   ├── db.py                # Database session
│   │   ├── auth.py              # JWT auth, role guards
│   │   ├── extraction/
│   │   │   ├── regex_layer.py   # Layer 1: regex extraction
│   │   │   └── gemini_layer.py  # Layer 2: Gemini AI extraction
│   │   ├── email/
│   │   │   ├── imap_ingest.py   # Gmail IMAP ingestion
│   │   │   └── smtp_send.py     # Brevo HTTP API email delivery
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── agent.py
│   │       ├── emails.py
│   │       ├── orders.py
│   │       ├── review.py
│   │       ├── settings.py
│   │       └── activity.py
│   ├── requirements.txt
│   └── .python-version          # Pins Python 3.11.9 for Render
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api.js               # Axios instance with JWT interceptor
│   │   ├── components/
│   │   │   └── Nav.jsx          # Responsive nav with mobile hamburger
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx    # KPIs + 3 charts (auto-refresh 15s)
│   │   │   ├── Inbox.jsx
│   │   │   ├── EmailDetail.jsx
│   │   │   ├── ReviewQueue.jsx
│   │   │   ├── Orders.jsx
│   │   │   ├── Processed.jsx
│   │   │   ├── Settings.jsx
│   │   │   └── Activity.jsx
│   │   └── styles.css
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

## 🚀 Local Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- A Gmail account with IMAP enabled
- Google Cloud account (for Gemini API key)
- Brevo account (for email delivery)

### 1. Clone the repository

```bash
git clone https://github.com/your-username/email-order-agent.git
cd email-order-agent
```

### 2. Backend setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Edit .env with your credentials (see Environment Variables section)

# Start the backend
python -m uvicorn app.main:app --reload --port 8000
```

Backend runs at: `http://localhost:8000`
API docs at: `http://localhost:8000/docs`

### 3. Frontend setup

```bash
cd frontend

# Install dependencies
npm install

# Create environment file
echo "VITE_API_URL=http://localhost:8000" > .env.local

# Start the dev server
npm run dev
```

Frontend runs at: `http://localhost:5173`

---

## ⚙️ Environment Variables

Create `backend/.env` with the following:

```env
# ── Database ──────────────────────────────────────────────────
DATABASE_URL=postgresql+psycopg2://user:password@host/dbname?sslmode=require

# ── Auth ──────────────────────────────────────────────────────
JWT_SECRET=your-strong-random-secret-key-here
ADMIN_USER=admin
ADMIN_PASSWORD=your-admin-password
REVIEWER_USER=reviewer
REVIEWER_PASSWORD=your-reviewer-password

# ── Gmail IMAP ────────────────────────────────────────────────
IMAP_HOST=imap.gmail.com
IMAP_USER=your-gmail@gmail.com
IMAP_PASSWORD=xxxx xxxx xxxx xxxx    # 16-char Gmail App Password (no spaces)

# ── Email Delivery (Brevo) ────────────────────────────────────
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USER=your-brevo-login@email.com
SMTP_PASSWORD=your-brevo-smtp-key
SMTP_FROM=your-verified-sender@email.com
BREVO_API_KEY=xkeysib-your-brevo-api-key

# ── Google Gemini ─────────────────────────────────────────────
GEMINI_API_KEY=AIzaSy-your-gemini-key
GEMINI_MODEL=gemini-1.5-flash

# ── App ───────────────────────────────────────────────────────
APP_BASE_URL=http://localhost:5173    # No trailing slash!
```

### Getting credentials

| Credential | Where to get it |
|---|---|
| `IMAP_PASSWORD` | Gmail → Settings → Security → 2-Step Verification → App Passwords |
| `BREVO_API_KEY` | [brevo.com](https://brevo.com) → Settings → API Keys |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API Key |
| `DATABASE_URL` | [neon.tech](https://neon.tech) → Project → Connection string |

---

## 🌐 Deployment (Render + Neon)

### Database — Neon

1. Create a free account at [neon.tech](https://neon.tech)
2. Create a new project (choose the region closest to you)
3. Copy the connection string — it looks like:
   ```
   postgresql+psycopg2://neondb_owner:password@ep-xxx.neon.tech/neondb?sslmode=require
   ```
4. Tables are created automatically on first backend startup

### Backend — Render Web Service

| Setting | Value |
|---|---|
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |

Add all environment variables from the `.env` section above.

> ⚠️ Set `APP_BASE_URL` to your exact frontend Render URL with **no trailing slash**.

### Frontend — Render Static Site

| Setting | Value |
|---|---|
| Root Directory | `frontend` |
| Build Command | `npm install && npm run build` |
| Publish Directory | `dist` |

Add environment variable:
```
VITE_API_URL=https://your-backend.onrender.com
```

Add a **Rewrite Rule**:
- Source: `/*`
- Destination: `/index.html`
- Action: **Rewrite** (not Redirect)

### Keep it alive — UptimeRobot

Render's free tier sleeps after 15 minutes of inactivity. Prevent this:

1. Create a free account at [uptimerobot.com](https://uptimerobot.com)
2. Add a new monitor:
   - Monitor Type: **HTTP(s)**
   - URL: `https://your-backend.onrender.com/health`
   - Interval: **Every 5 minutes**

---

## 📧 Gmail Setup

1. Enable 2-Step Verification on your Gmail account
2. Go to **Google Account → Security → App Passwords**
3. Create an App Password for "Mail" → "Other (custom name)"
4. Copy the 16-character password (remove spaces when pasting into env var)
5. Enable IMAP: Gmail → Settings → See All Settings → Forwarding and POP/IMAP → Enable IMAP

---

## 🔌 API Reference

All endpoints require `Authorization: Bearer <token>` except `/auth/login` and `/health`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/login` | Get JWT token |
| `GET` | `/health` | Health check |
| `GET` | `/agent/status` | Get agent enabled/disabled state |
| `POST` | `/agent/start` | Enable the automation agent |
| `POST` | `/agent/stop` | Disable the automation agent |
| `GET` | `/emails` | List active inbox emails |
| `GET` | `/emails/processed` | List archived processed emails |
| `GET` | `/emails/{id}` | Get email with extraction details |
| `POST` | `/emails/{id}/process` | Manually trigger processing |
| `GET` | `/review/queue` | Get emails needing human review |
| `POST` | `/review/{id}/submit` | Submit corrections and resume pipeline |
| `GET` | `/orders` | List all transport orders |
| `GET` | `/activity/recent` | Recent system activity |

Full interactive docs available at `/docs` (Swagger UI).

---

## 📬 Test Email Format

Send an email to your configured Gmail inbox with this format:

```
Subject: Transport Request

Customer Name: John Doe
Weight: 500 kg
Pickup Location: Chennai Port, TN
Drop Location: Bangalore Warehouse, KA
Pickup Date: 2026-03-20
Delivery Deadline: 2026-03-21
```

The system will:
1. Detect it within 15 seconds
2. Extract all 5 fields
3. Create a transport order (e.g. `JOB-20260320-A1B2C3D4`)
4. Send a confirmation email back to you

---

## 🔄 Processing Pipeline

```
Email arrives in Gmail
        ↓
IMAP fetch (every 15s)
        ↓
Stored in DB with status: RECEIVED
        ↓
Regex Layer extracts fields
        ↓
All fields found? ──Yes──→ Create Order → Send Confirmation
        ↓ No
Gemini AI attempts extraction
        ↓
All fields found? ──Yes──→ Create Order → Send Confirmation
        ↓ No
Status: NEEDS_HUMAN_REVIEW
Missing-fields email sent to customer
        ↓
Reviewer fills in missing fields via dashboard
        ↓
Pipeline resumes → Create Order → Send Confirmation
```

---

## 🗄️ Database Schema

### emails
| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | Auto ID |
| message_id | VARCHAR UNIQUE | Deduplication key |
| from_email | VARCHAR | Sender address |
| subject | VARCHAR | Email subject |
| body_text | TEXT | Plain text body |
| status | ENUM | Current pipeline status |
| extracted | JSONB | Extracted field values |
| missing_fields | JSONB | List of missing field names |
| archived | BOOLEAN | Archived after order creation |

### orders
| Column | Type | Description |
|---|---|---|
| id | SERIAL PK | Auto ID |
| job_id | VARCHAR UNIQUE | e.g. JOB-20260320-A1B2C3D4 |
| email_id | INTEGER FK | Source email |
| customer_name | VARCHAR | Customer name |
| weight_kg | INTEGER | Weight in kg |
| pickup_location | VARCHAR | Origin |
| drop_location | VARCHAR | Destination |
| pickup_time_window | VARCHAR | Time range |
| created_at | TIMESTAMP | Creation time |

---

## 🐛 Common Issues

**Tables not created in Neon**
- Ensure `DATABASE_URL` starts with `postgresql+psycopg2://` and ends with `?sslmode=require`
- Remove `&channel_binding=require` if present
- Force a redeploy on Render

**Login fails with "Invalid credentials"**
- Check `APP_BASE_URL` in backend env matches your frontend URL exactly (no trailing slash)
- This controls CORS — a mismatch silently blocks all API calls

**Emails stuck on EXTRACTING**
- Check Render logs for Gemini API errors
- Ensure `GEMINI_API_KEY` is set correctly
- Gemini free tier: 15 requests/minute max

**Health check returning 405**
- Update `/health` endpoint to accept both GET and HEAD methods

**Confirmation emails not sending**
- Ensure `BREVO_API_KEY` is set (not just SMTP vars)
- Check Render logs for `SMTP error` messages
- Verify sender email is verified in Brevo dashboard

---

## 🔮 Roadmap

- [ ] JWT token auto-refresh on expiry
- [ ] Search and filter on inbox/orders
- [ ] CSV export for orders
- [ ] Pagination on all list views
- [ ] PDF attachment parsing (Bill of Lading)
- [ ] Multi-tenancy support
- [ ] Mobile app for field agents
- [ ] Alembic database migrations
- [ ] Webhook integration with TMS platforms

---

## 👥 Authors

| Name | Roll No |
|---|---|
| Jeevapriyadharshan S | 71772218108 |
| Jeeva Bharathi M | 71772218109 |
| Vikram R | 71772218135 |
| Sanjay S | 71772218145 |

Department of Information Technology
Sri Ramakrishna Institute of Technology, Coimbatore
Under the guidance of **The Yellow Network Ecosystem Pvt. Ltd.**

---

## 📄 License

This project is submitted in partial fulfillment of the requirements for the B.Tech degree in Information Technology at Sri Ramakrishna Institute of Technology, Coimbatore (March 2026).
