# Mira — Personal AI Roadmap System

Mira is an AI-powered personal roadmap and progress management web application designed to turn trusted learning plans into executable daily tasks, adapt to changes, and help you actually finish what you started.

> **Core Philosophy:**
> *"The AI does not decide what I should learn. It helps me actually finish what I have already decided to learn."*

---

## 🏛 Architecture Principle

```text
User → Frontend → API → Services → Deterministic Engine / AI Service → Database
```

* **Frontend (`frontend/`)**: Modern React 18, TypeScript, and Vite application rendering day-by-day game-like level progressions, daily focus tasks, and AI generation flows.
* **Deterministic Roadmap Engine (`backend/app/roadmap_engine/`)**: Enforces core Mira business invariants:
  * Identifies the first incomplete day
  * Protects completed days and tasks (completed history is immutable)
  * Inserts new content starting from the first incomplete day (never appended)
  * Shifts future incomplete tasks while strictly preserving the **fixed total duration**
  * Rebalances future workload and detects capacity conflicts
* **AI Layer (`backend/app/ai/`)**: Structured prompt handling and provider abstraction (`MockAIProvider`). AI output is strictly validated by `AIValidator` before reaching the database. The AI **never** directly accesses or mutates the database.

---

## 📁 Repository Structure

```text
Mira/
├── docs/
│   └── PRD.md                  # Official Product Requirements Document
├── backend/
│   ├── app/
│   │   ├── api/                # FastAPI v1 routers and endpoint handlers
│   │   │   └── v1/
│   │   │       ├── endpoints/  # health, roadmaps, days, tasks
│   │   │       └── router.py
│   │   ├── core/               # App configuration, database engine, settings
│   │   ├── models/             # SQLAlchemy ORM entities (User, Roadmap, Day, Task, etc.)
│   │   ├── schemas/            # Pydantic v2 schemas for validation & serialization
│   │   ├── services/           # Service orchestration (roadmap_service, progress_service)
│   │   ├── roadmap_engine/     # Deterministic insertion and rescheduling engines
│   │   ├── ai/                 # AI schemas, provider abstraction, mock provider, validator
│   │   └── main.py             # FastAPI entry point & lifespan handler
│   └── tests/                  # Pytest test suite (78 tests)
├── frontend/
│   ├── src/
│   │   ├── api/                # Centralized typed API client
│   │   ├── components/         # Common, layout, task, and roadmap components
│   │   ├── pages/              # Home (Today), Roadmap, Create, Settings
│   │   ├── styles/             # Design tokens, CSS modules, animations
│   │   ├── types/              # TypeScript interfaces matching backend models
│   │   └── utils/              # Formatters, development user reference
│   ├── package.json
│   └── vite.config.ts
├── alembic/                    # Database migrations
├── alembic.ini
├── .env.example                # Backend environment template
├── requirements.txt            # Python dependencies (UTF-8)
└── README.md
```

---

## 🚀 Getting Started

### 1. Prerequisites
* Python 3.10+ (tested on Python 3.14.3)
* Node.js 18+ and npm 9+ (tested on Node v24.14.0, npm 11.9.0)
* Git

---

### 2. Backend Setup

1. **Activate Virtual Environment:**

   **Windows (PowerShell):**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

   **Linux / macOS:**
   ```bash
   source .venv/bin/activate
   ```

2. **Install Dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   ```powershell
   copy .env.example .env
   ```
   *By default, `DATABASE_URL` falls back to SQLite (`sqlite:///./mira_dev.db`) for local development.*

4. **Run Database Migrations:**
   ```powershell
   python -m alembic upgrade head
   ```

5. **Start Backend Server:**
   ```powershell
   python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   * API Documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
   * Health Endpoint: [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

### 3. Frontend Setup

1. **Navigate to `frontend/` and Install Dependencies:**
   ```powershell
   cd frontend
   npm install
   ```

2. **Start Frontend Development Server:**
   ```powershell
   npm run dev
   ```
   The frontend runs on [http://localhost:3000](http://localhost:3000) and automatically proxies `/api` requests to the backend at `http://127.0.0.1:8000`.

3. **Build for Production:**
   ```powershell
   npm run build
   ```

---

### 4. Development User Seeding

When running in `ENVIRONMENT="development"`, the backend automatically ensures a default developer user exists:
* **User ID**: `1`
* **Username**: `dev_user`
* **Email**: `dev@mira.local`
* **Daily Capacity**: `120` minutes (2 hours)

This allows immediate roadmap generation and testing from the web UI without manual SQL queries. In production (`ENVIRONMENT="production"`), this automatic seeding is completely disabled.

---

## 🧪 Running Tests

### Backend Tests
```powershell
python -m pytest backend/tests -v
```

### Database Migration Verification
```powershell
python -m alembic check
```

### Frontend Build Verification
```powershell
cd frontend
npm run build
```

---

## 🗺 Project Status

* [x] **Phase 1 — Backend Foundation:** Project layout, config, FastAPI setup, health check.
* [x] **Phase 2 — Database Foundation:** PostgreSQL target, SQLAlchemy models, Alembic migrations.
* [x] **Phase 3 — Roadmap CRUD:** Full REST API for Roadmap creation, retrieval, listing, updates, deletion.
* [x] **Phase 4 — Progress Tracking:** Task completion, uncompletion, day status transitions, progress metrics.
* [x] **Phase 5 — Deterministic Roadmap Insertion Engine:** Shift calculations, capacity validation, audit snapshots.
* [x] **Phase 6 — Deterministic Rescheduling Engine:** Workload rebalancing, transient capacity overrides.
* [x] **Phase 7 — AI-Assisted Roadmap Generation:** Provider abstraction, mock provider, strict output validation.
* [x] **Phase 8 — Frontend Foundation & Roadmap UI:** React/TypeScript web app, level progression UI, task interactions.
* [x] **Phase 9 — Testing, Hardening & Deployment Readiness:** Comprehensive test coverage, security review, clean git hygiene.
