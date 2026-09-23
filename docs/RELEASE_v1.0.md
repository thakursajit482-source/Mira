# Mira v1.0 — Official Release Notes

## Release Status
**Production-Ready / Ready for Deployment**

Mira has completed all development phases (Phases 1 through 12) and passed final quality assurance, regression testing, and security hardening.

---

## Included Features

### Core Experience & Workflow
- **Daily Focus Dashboard (Today)**: Real-time progress tracking, current day overview, remaining duration, workload status (`ON_TRACK`, `TIGHT`, `OVER_CAPACITY`, `COMPLETE`), and task completion interactions.
- **Visual Roadmap Progression**: Level-by-level day view with locked future stages, expandable task lists, category badges, and completion microinteractions.
- **AI-Assisted Roadmap Generation**: Generates structured, day-wise learning curriculums from goals or syllabi with interactive preview and capacity validation.
- **Deterministic Roadmap Insertion ("Add to Mira")**: Safely injects new material starting at the first incomplete day without altering completed history or silently extending fixed total durations.
- **Deterministic Rescheduling Engine**: Rebalances unfinished tasks across available future days when plans fall behind or study capacity changes.
- **Progress & Momentum Tracking**: Deterministic completion analytics, streak calculation, velocity tracking, milestone celebrations, and recent activity logs.
- **Roadmap Versioning & Change History**: Full audit trail recording all AI creations, manual insertions, and rescheduling adjustments with snapshot diffs.
- **Notification & Reminder Center**: Unobtrusive in-app alerts, unread counters, daily evening reminders, timezone awareness, and quiet hour respect.
- **Settings, Theming & Account Experience**: User preferences, daily capacity tuning (15–1440 min), theme switcher (System / Light / Dark), full JSON roadmap export, and safe roadmap deletion with confirmation dialogs.

---

## Architecture

```text
User Browser → React 18 SPA (Vite) → FastAPI Backend (/api/v1) → Service Layer → Deterministic Engine / AI Provider → SQLAlchemy ORM → PostgreSQL / SQLite
```

- **Frontend**: Modern React 18, TypeScript, and Vite single-page application utilizing CSS modules, theme tokens, and accessible modal dialogs.
- **Backend**: FastAPI web service with Pydantic v2 schemas, structured logging, HTTP security headers, and separated liveness/readiness probes.
- **Database**: PostgreSQL target (with SQLite fallback for local development) orchestrated via SQLAlchemy 2.0 ORM and Alembic migrations.
- **AI Layer**: Provider abstraction (`MockAIProvider`, configurable for external LLMs) with strict Pydantic output validation. The AI **never** mutates the database directly.
- **Roadmap Engine**: Pure deterministic logic enforcing capacity limits, day shifts, and status transitions.

---

## Core Guarantees

1. **Completed History is Immutable**: Completed tasks and days can never be shifted, overwritten, or modified by AI or rescheduling engines.
2. **Deterministic Roadmap Insertion**: New content always begins at the first incomplete day, shifting downstream days forward while strictly respecting fixed target duration limits.
3. **Deterministic Rescheduling**: Incomplete tasks are rebalanced across remaining days based strictly on user daily capacity without modifying completed days.
4. **Fixed-Duration Invariant**: Target roadmap duration remains invariant during operations unless explicitly updated by the user.
5. **AI Isolation**: AI outputs are validated against strict structural constraints before persistence. The AI layer has no direct database write access.
6. **Explicit User Confirmation**: All destructive and schedule-mutating operations require an explicit non-destructive preview and user confirmation.
7. **Audit & Version History**: Every roadmap mutation creates an immutable version snapshot with detailed change logs.

---

## Verification Results

| Verification Item | Result | Details |
| :--- | :--- | :--- |
| **Backend Unit & Integration Tests** | **148 Passed (100%)** | Ran `pytest backend/tests -v` in 7.36s with 0 failures. |
| **Critical Flows (Flows A–I)** | **Verified** | Dedicated E2E integration test covering all 9 user journeys passed cleanly. |
| **Database Migrations** | **Clean / Up to date** | `alembic check` reports `No new upgrade operations detected.` |
| **Frontend Production Build** | **Success** | `tsc && vite build` completed in 5.91s with 0 TypeScript errors. Bundle: 90.15 kB gzip JS, 14.87 kB gzip CSS. |
| **Liveness & Readiness Probes** | **Verified** | `GET /health` (200 OK) and `GET /ready` (200 OK, active database query) verified. |
| **Security & Error Sanitization** | **Verified** | Security headers injected; unhandled 500 errors sanitized in production. |

---

## Known Limitations

- **Single-User Scope**: Mira v1.0 is engineered as a focused personal planner. Multi-tenant team collaboration and OAuth/SSO authentication are intentionally deferred to future versions.
- **Local Notification System**: Notifications and reminders currently trigger within the web client and browser Notification API; SMS and email delivery channels are not included in v1.0.
- **Synchronous AI Requests**: AI generation runs synchronously during request lifecycle; for very large syllabi (>30 days), requests take 2–4 seconds under external providers.

---

## Production Deployment Guide

### 1. Database (PostgreSQL)
Provision a PostgreSQL 14+ instance (AWS RDS, Supabase, Neon, or self-hosted) and obtain the connection string:
```bash
postgresql+psycopg://username:password@hostname:5432/mira_db?sslmode=require
```

### 2. Backend Deployment
```bash
# Set environment variables
export ENVIRONMENT=production
export DEBUG=False
export ENABLE_DOCS=False
export LOG_LEVEL=INFO
export CORS_ORIGINS='["https://mira.yourdomain.com"]'
export DATABASE_URL="postgresql+psycopg://user:pass@host:5432/dbname?sslmode=require"

# Install dependencies
pip install -r requirements.txt

# Run migrations
python -m alembic upgrade head

# Start production server
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. Frontend Deployment
```bash
cd frontend

# Set API base URL (if served from separate domain or reverse proxy)
export VITE_API_BASE_URL="https://api.mira.yourdomain.com/api/v1"

# Build production assets
npm install
npm run build

# Serve dist/ via Nginx, Cloudflare Pages, AWS S3/CloudFront, or Vercel
```

---

## Version
**Mira v1.0.0**
