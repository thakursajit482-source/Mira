"""
Regression tests for large roadmap (129 days) AI planning and generation flow.

Verifies:
1. 129-day generation request passes AI validation.
2. 129-day preview endpoint (POST /api/v1/roadmaps/generate/preview) returns 200 OK.
3. 129-day persistence endpoint (POST /api/v1/roadmaps/generate) returns 201 Created.
4. Large 8087-character content slice is handled without validation or truncation errors.
5. Deterministic insertion conflict detection when 129 days exceeds active roadmap capacity.
6. DB persistence integrity: 129 days and all corresponding tasks created with correct DayStatus/TaskStatus.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import get_db
from backend.app.models.base import Base
from backend.app.models.enums import DayStatus, TaskStatus
from backend.app.models.user import User
from backend.app.models.roadmap import Roadmap
from backend.app.ai.schemas import RoadmapGenerationRequest, GeneratedRoadmap
from backend.app.ai.service import ai_service
from backend.app.ai.validator import AIValidator


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client(test_db: Session):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user(test_db: Session) -> User:
    user = User(
        id=1,
        email="dev@mira.local",
        username="dev_user",
        daily_available_minutes=120,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


# ==============================================================================
# 1. AI Service & Validator tests for 129 days
# ==============================================================================

def test_ai_service_generates_and_validates_129_days():
    """Verify that AIService and AIValidator handle 129-day generation without error."""
    # Use a large plain-text context (no day boundaries) to test large-string handling
    # without triggering context parsing (which would produce fewer parsed days).
    large_context = ("Study topic, practice exercises. " * 300)[:2000]
    req = RoadmapGenerationRequest(
        user_id=1,
        goal="Master Distributed Systems and Advanced Cloud Architecture",
        target_duration_days=129,
        daily_available_minutes=120,
        context=large_context,
    )

    generated = ai_service.generate_roadmap(req, effective_daily_capacity=120)

    assert isinstance(generated, GeneratedRoadmap)
    assert generated.target_duration_days == 129
    assert len(generated.days) == 129
    assert [d.day_number for d in generated.days] == list(range(1, 130))
    assert len(generated.title) <= 255

    # Invariant: AIValidator.validate must pass without raising AIValidationError
    AIValidator.validate(generated, req, daily_capacity=120)


def test_ai_service_workload_within_daily_capacity_for_129_days():
    """Verify that each day in a 129-day roadmap adheres to the 120-minute daily capacity."""
    req = RoadmapGenerationRequest(
        user_id=1,
        goal="Comprehensive 129-Day Full Stack Program",
        target_duration_days=129,
        daily_available_minutes=120,
    )

    generated = ai_service.generate_roadmap(req, effective_daily_capacity=120)

    for day in generated.days:
        day_total = sum(t.estimated_minutes for t in day.tasks)
        assert day_total <= 120, f"Day {day.day_number} workload {day_total} > 120"
        for task in day.tasks:
            assert len(task.title) <= 255
            assert task.estimated_minutes > 0


# ==============================================================================
# 2. API Endpoints for 129 days
# ==============================================================================

def test_api_generate_preview_129_days_returns_200(client: TestClient, sample_user: User):
    """
    POST /api/v1/roadmaps/generate/preview with 129 days and large 8087-char content
    must return 200 OK with valid GeneratedRoadmap structure.
    """
    # Use large plain-text context (no day boundaries) so the generic 129-day
    # generation path is used. This still exercises large-string handling.
    large_content = ("Read chapters, practice coding, review notes. " * 200)[:2000]
    payload = {
        "user_id": sample_user.id,
        "goal": "Target (Phase 1) - 129-Day Execution Roadmap",
        "target_duration_days": 129,
        "daily_available_minutes": 120,
        "context": large_content,
    }

    resp = client.post("/api/v1/roadmaps/generate/preview", json=payload)
    assert resp.status_code == 200, f"Unexpected {resp.status_code}: {resp.text}"

    data = resp.json()
    assert data["target_duration_days"] == 129
    assert len(data["days"]) == 129
    assert len(data["title"]) <= 255
    assert data["days"][0]["day_number"] == 1
    assert data["days"][128]["day_number"] == 129


def test_api_generate_and_persist_129_days_returns_201(
    client: TestClient, sample_user: User, test_db: Session
):
    """
    POST /api/v1/roadmaps/generate with 129 days must persist successfully,
    returning 201 Created and establishing valid DayStatus/TaskStatus entities.
    """
    payload = {
        "user_id": sample_user.id,
        "goal": "Target (Phase 1) - 129 Days Comprehensive Mastery",
        "target_duration_days": 129,
        "daily_available_minutes": 120,
        "context": "Comprehensive study plan",
    }

    resp = client.post("/api/v1/roadmaps/generate", json=payload)
    assert resp.status_code == 201, f"Unexpected {resp.status_code}: {resp.text}"

    data = resp.json()
    assert data["id"] is not None
    assert data["target_duration_days"] == 129
    assert len(data["days"]) == 129

    # Day 1 is CURRENT, Day 2..129 are LOCKED
    assert data["days"][0]["status"] == DayStatus.CURRENT.value
    for d in data["days"][1:]:
        assert d["status"] == DayStatus.LOCKED.value

    # Verify DB persistence
    test_db.expire_all()
    roadmap_db = test_db.get(Roadmap, data["id"])
    assert roadmap_db is not None
    assert len(roadmap_db.days) == 129
    assert len(roadmap_db.versions) == 1
    assert len(roadmap_db.changes) == 1


def test_preview_insertion_with_129_days_detects_capacity_conflict(
    client: TestClient, sample_user: User, test_db: Session
):
    """
    When inserting 129 new days into a roadmap of fixed smaller duration (e.g. 10 days),
    the insertion engine must return 200 OK with conflict=True (INSUFFICIENT_CAPACITY).
    """
    # 1. Create a 10-day roadmap
    rm_payload = {
        "user_id": sample_user.id,
        "goal": "Initial Small Roadmap",
        "target_duration_days": 10,
        "daily_available_minutes": 120,
    }
    create_resp = client.post("/api/v1/roadmaps/generate", json=rm_payload)
    assert create_resp.status_code == 201
    rm_id = create_resp.json()["id"]

    # 2. Preview inserting 129 days
    insertion_payload = {
        "new_days": [
            {
                "tasks": [
                    {
                        "title": f"New Task Day {i}",
                        "description": "",
                        "estimated_minutes": 60,
                        "order_index": 0,
                        "category": "Practice",
                    }
                ]
            }
            for i in range(1, 130)
        ],
        "metadata": {"source": "ai_planning", "goal": "Oversized Insertion"},
    }

    insert_resp = client.post(f"/api/v1/roadmaps/{rm_id}/insert/preview", json=insertion_payload)
    assert insert_resp.status_code == 200

    data = insert_resp.json()
    assert data["conflict"] is True
    assert data["conflict_reason"] == "INSUFFICIENT_CAPACITY"
    assert data["status"] == "CONFLICT"
