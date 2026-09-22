# Mira — Personal AI Roadmap System

Mira is an AI-powered personal roadmap and progress management web application designed to turn trusted learning plans into executable daily tasks, adapt to changes, and help you actually finish what you started.

> **Core Philosophy:**
> *"The AI does not decide what I should learn. It helps me actually finish what I have already decided to learn."*

---

## 🏛 Architecture Principle

```
User → API → AI/Services → Validation → Roadmap Engine → Database
```

* **Deterministic Roadmap Engine:** Responsible for enforcing core product rules:
  * Finding the first incomplete day
  * Locking and protecting completed days (completed history is never overwritten)
  * Inserting new content starting from the first incomplete day (never appended)
  * Shifting future work forward while keeping the **total roadmap duration fixed**
  * Rebalancing future workload and detecting scheduling conflicts
* **AI Layer:** Accepts content, analyzes topics, and returns strictly structured data. The AI **never** directly modifies the database.

---

## 📁 Repository Structure

```
Mira/
├── docs/
│   └── PRD.md                  # Official Product Requirements Document
├── backend/
│   ├── app/
│   │   ├── api/                # API routers and endpoints
│   │   │   └── v1/
│   │   │       ├── endpoints/
│   │   │       │   └── health.py
│   │   │       └── router.py
│   │   ├── core/               # Configuration and core utilities
│   │   │   └── config.py
│   │   ├── models/             # Database ORM models (Phase 3+)
│   │   ├── schemas/            # Pydantic validation schemas
│   │   │   └── health.py
│   │   ├── services/           # Service orchestration layer (Phase 4+)
│   │   ├── roadmap_engine/     # Deterministic roadmap engine (Phase 6+)
│   │   ├── ai/                 # AI prompt handling & structured parsing (Phase 5+)
│   │   └── main.py             # FastAPI entry point & app factory
│   └── tests/                  # Automated test suite
│       ├── conftest.py
│       └── test_health.py
├── .env.example                # Environment variables template
├── .gitignore
├── README.md
└── requirements.txt            # Project dependencies (UTF-8)
```

---

## 🚀 Getting Started

### 1. Prerequisites
* Python 3.10+ (tested on Python 3.14.3)
* Git

### 2. Environment Setup

If not already created, create and activate a Python virtual environment:

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

Install the required dependencies:
```powershell
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```

---

## 💻 Running the Backend

Start the development server using Uvicorn:

```powershell
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

* **Interactive API Documentation (Swagger UI):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Alternative API Documentation (ReDoc):** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
* **Health Check:** [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

## 🧪 Running Tests

Run the test suite using `pytest`:

```powershell
python -m pytest backend/tests -v
```

---

## 🗺 Development Roadmap

* [x] **Phase 1 — Foundation:** Project structure, config, FastAPI setup, health check, automated tests, PRD documentation.
* [ ] **Phase 2 — Frontend Shell & Roadmap UI (Mock Data):** Visual game-level roadmap interface.
* [ ] **Phase 3 — Database & Core CRUD:** PostgreSQL, SQLAlchemy models, Alembic migrations.
* [ ] **Phase 4 — Task/Day Completion Logic:** Independent task completion, day status transitions.
* [ ] **Phase 5 — Initial AI Roadmap Generation:** Structured prompt formatting, JSON response parsing.
* [ ] **Phase 6 — Roadmap Insertion & Shifting Engine:** Deterministic insertion, shifting future tasks, preserving history.
* [ ] **Phase 7 — Rescheduling & Fixed-Duration Validation:** Workload rebalancing, conflict detection.
* [ ] **Phase 8 — UI Polish, Animations & Gamification:** Visual feedback, micro-interactions.
* [ ] **Phase 9 — Testing & Deployment.**
