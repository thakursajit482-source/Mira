import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import get_db
from backend.app.models.base import Base
from backend.app.models.enums import RoadmapStatus, DayStatus, TaskStatus, RoadmapChangeType
from backend.app.models.user import User
from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.models.task import Task
from backend.app.models.versioning import RoadmapVersion, RoadmapChange
from backend.app.ai.schemas import (
    RoadmapGenerationRequest,
    GeneratedRoadmap,
    GeneratedDay,
    GeneratedTask,
)
from backend.app.ai.providers.mock import MockAIProvider
from backend.app.ai.validator import AIValidator, AIValidationError
from backend.app.ai.service import ai_service


@pytest.fixture
def test_db():
    """Create a fresh in-memory SQLite database for each test with multi-thread support."""
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
    """FastAPI TestClient with overridden get_db dependency."""
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
    """Helper fixture to insert a test user with 120 minutes daily capacity."""
    user = User(email="ai_user@example.com", username="ai_user", daily_available_minutes=120)
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


# ==============================================================================
# 1. AI PROVIDER TESTS
# ==============================================================================

def test_mock_ai_provider_generates_structured_output():
    provider = MockAIProvider()
    req = RoadmapGenerationRequest(
        user_id=1,
        goal="Master FastAPI and PostgreSQL",
        target_duration_days=5,
        daily_available_minutes=120,
        context="Intermediate Python Developer",
    )
    res = provider.generate_roadmap(req, effective_daily_capacity=120)

    assert isinstance(res, GeneratedRoadmap)
    assert res.target_duration_days == 5
    assert len(res.days) == 5
    assert "Master FastAPI and PostgreSQL" in res.title
    assert "Intermediate Python Developer" in res.title
    assert [d.day_number for d in res.days] == [1, 2, 3, 4, 5]

    for d in res.days:
        assert len(d.tasks) >= 1
        day_total = sum(t.estimated_minutes for t in d.tasks)
        assert day_total <= 120
        for t in d.tasks:
            assert t.title is not None and len(t.title) > 0
            assert t.estimated_minutes > 0


def test_mock_ai_provider_is_deterministic():
    provider = MockAIProvider()
    req = RoadmapGenerationRequest(
        user_id=1,
        goal="Learn Rust Systems Programming",
        target_duration_days=10,
        daily_available_minutes=90,
    )

    run_1 = provider.generate_roadmap(req, effective_daily_capacity=90)
    run_2 = provider.generate_roadmap(req, effective_daily_capacity=90)

    assert run_1.model_dump() == run_2.model_dump()


# ==============================================================================
# 2. SCHEMA & OUTPUT VALIDATION TESTS
# ==============================================================================

def test_validator_accepts_valid_generated_roadmap():
    req = RoadmapGenerationRequest(
        user_id=1,
        goal="Learn Docker",
        target_duration_days=2,
    )
    valid_roadmap = GeneratedRoadmap(
        title="Docker Basics",
        description="Learn Docker in 2 days",
        target_duration_days=2,
        days=[
            GeneratedDay(
                day_number=1,
                title="Containers",
                tasks=[
                    GeneratedTask(title="Install Docker", estimated_minutes=30, order_index=0),
                    GeneratedTask(title="Run First Container", estimated_minutes=30, order_index=1),
                ],
            ),
            GeneratedDay(
                day_number=2,
                title="Dockerfiles",
                tasks=[
                    GeneratedTask(title="Write Dockerfile", estimated_minutes=60, order_index=0),
                ],
            ),
        ],
    )
    # Should not raise
    AIValidator.validate(valid_roadmap, req, daily_capacity=120)


def test_validator_rejects_missing_title():
    req = RoadmapGenerationRequest(user_id=1, goal="Goal", target_duration_days=1)
    bad_roadmap = GeneratedRoadmap(
        title="   ",  # Blank title
        target_duration_days=1,
        days=[
            GeneratedDay(
                day_number=1,
                tasks=[GeneratedTask(title="Task 1", estimated_minutes=30, order_index=0)],
            )
        ],
    )
    with pytest.raises(AIValidationError, match="Roadmap title is missing or empty"):
        AIValidator.validate(bad_roadmap, req, daily_capacity=120)


def test_validator_rejects_duration_mismatch():
    req = RoadmapGenerationRequest(user_id=1, goal="Goal", target_duration_days=30)
    # Generated only 27 days
    bad_roadmap = GeneratedRoadmap(
        title="Mismatch Plan",
        target_duration_days=27,
        days=[
            GeneratedDay(
                day_number=i,
                tasks=[GeneratedTask(title=f"Task {i}", estimated_minutes=30, order_index=0)],
            )
            for i in range(1, 28)
        ],
    )
    with pytest.raises(AIValidationError, match="does not match requested duration"):
        AIValidator.validate(bad_roadmap, req, daily_capacity=120)


def test_validator_rejects_duplicate_day_numbers():
    req = RoadmapGenerationRequest(user_id=1, goal="Goal", target_duration_days=2)
    bad_roadmap = GeneratedRoadmap(
        title="Duplicate Days",
        target_duration_days=2,
        days=[
            GeneratedDay(
                day_number=1,
                tasks=[GeneratedTask(title="Task 1", estimated_minutes=30, order_index=0)],
            ),
            GeneratedDay(
                day_number=1,  # Duplicate day 1!
                tasks=[GeneratedTask(title="Task 2", estimated_minutes=30, order_index=0)],
            ),
        ],
    )
    with pytest.raises(AIValidationError, match="duplicate day numbers"):
        AIValidator.validate(bad_roadmap, req, daily_capacity=120)


from pydantic import ValidationError


def test_schema_rejects_invalid_task_duration():
    with pytest.raises(ValidationError, match="greater_than_equal"):
        GeneratedTask(title="Task 1", estimated_minutes=0, order_index=0)


def test_schema_rejects_missing_task_title():
    with pytest.raises(ValidationError, match="string_too_short"):
        GeneratedTask(title="", estimated_minutes=30, order_index=0)


def test_validator_rejects_whitespace_task_title():
    req = RoadmapGenerationRequest(user_id=1, goal="Goal", target_duration_days=1)
    bad_roadmap = GeneratedRoadmap(
        title="Whitespace Task Title",
        target_duration_days=1,
        days=[
            GeneratedDay(
                day_number=1,
                tasks=[GeneratedTask(title="   ", estimated_minutes=30, order_index=0)],
            )
        ],
    )
    with pytest.raises(AIValidationError, match="missing a title"):
        AIValidator.validate(bad_roadmap, req, daily_capacity=120)


def test_validator_rejects_impossible_workload():
    req = RoadmapGenerationRequest(user_id=1, goal="Goal", target_duration_days=1)
    # Day has 180 mins, but daily capacity is 120 mins
    bad_roadmap = GeneratedRoadmap(
        title="Overloaded Day",
        target_duration_days=1,
        days=[
            GeneratedDay(
                day_number=1,
                tasks=[
                    GeneratedTask(title="Task 1", estimated_minutes=90, order_index=0),
                    GeneratedTask(title="Task 2", estimated_minutes=90, order_index=1),
                ],
            )
        ],
    )
    with pytest.raises(AIValidationError, match="exceeds daily available capacity"):
        AIValidator.validate(bad_roadmap, req, daily_capacity=120)


# ==============================================================================
# 3. API ENDPOINT & PERSISTENCE TESTS
# ==============================================================================

def test_api_generate_roadmap_success(client: TestClient, sample_user: User, test_db: Session):
    payload = {
        "user_id": sample_user.id,
        "goal": "Learn Modern DevOps with Kubernetes",
        "target_duration_days": 4,
        "daily_available_minutes": 90,
        "context": "Has Docker Experience",
    }

    resp = client.post("/api/v1/roadmaps/generate", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    # Verify response structure
    assert data["id"] is not None
    assert data["user_id"] == sample_user.id
    assert "Learn Modern DevOps with Kubernetes" in data["title"]
    assert data["target_duration_days"] == 4
    assert data["status"] == "ACTIVE"

    # Verify Days
    days = data["days"]
    assert len(days) == 4
    assert [d["day_number"] for d in days] == [1, 2, 3, 4]

    # Day 1 is CURRENT, subsequent days are LOCKED
    assert days[0]["status"] == "CURRENT"
    assert days[1]["status"] == "LOCKED"
    assert days[2]["status"] == "LOCKED"
    assert days[3]["status"] == "LOCKED"

    # Verify Tasks
    for d in days:
        assert len(d["tasks"]) >= 1
        for t in d["tasks"]:
            assert t["status"] == "PENDING"
            assert t["is_completed"] is False
            assert t["estimated_minutes"] > 0

    # Verify Database state
    test_db.expire_all()
    roadmap_db = test_db.get(Roadmap, data["id"])
    assert roadmap_db is not None
    assert len(roadmap_db.days) == 4

    # Verify RoadmapVersion (version 1 created)
    versions = test_db.query(RoadmapVersion).filter_by(roadmap_id=roadmap_db.id).all()
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert "Initial AI generation" in versions[0].change_summary
    assert "days" in versions[0].snapshot_data

    # Verify RoadmapChange (INITIAL_GENERATION audit log)
    changes = test_db.query(RoadmapChange).filter_by(roadmap_id=roadmap_db.id).all()
    assert len(changes) == 1
    assert changes[0].change_type == RoadmapChangeType.INITIAL_GENERATION
    assert changes[0].version_id == versions[0].id
    assert changes[0].metadata_info["goal"] == payload["goal"]


def test_api_generate_roadmap_nonexistent_user_returns_404(client: TestClient):
    payload = {
        "user_id": 99999,
        "goal": "Orphan Plan",
        "target_duration_days": 5,
    }
    resp = client.post("/api/v1/roadmaps/generate", json=payload)
    assert resp.status_code == 404
    assert "User with id 99999 not found" in resp.json()["detail"]


def test_api_generate_roadmap_invalid_request_returns_422(client: TestClient, sample_user: User):
    # Goal too short, target_duration_days = 0
    payload = {
        "user_id": sample_user.id,
        "goal": "ab",
        "target_duration_days": 0,
    }
    resp = client.post("/api/v1/roadmaps/generate", json=payload)
    assert resp.status_code == 422


def test_api_generate_roadmap_handles_provider_failure(
    client: TestClient, sample_user: User, monkeypatch
):
    def broken_provider(*args, **kwargs):
        raise RuntimeError("LLM service unavailable")

    monkeypatch.setattr(ai_service, "generate_roadmap", broken_provider)

    payload = {
        "user_id": sample_user.id,
        "goal": "Learn Python",
        "target_duration_days": 5,
    }
    resp = client.post("/api/v1/roadmaps/generate", json=payload)
    assert resp.status_code == 502
    assert "AI provider failed to generate roadmap" in resp.json()["detail"]


def test_api_generate_roadmap_handles_validation_failure(
    client: TestClient, sample_user: User, monkeypatch
):
    def invalid_output_provider(*args, **kwargs):
        raise AIValidationError("Malformed output", ["Day count mismatch"])

    monkeypatch.setattr(ai_service, "generate_roadmap", invalid_output_provider)

    payload = {
        "user_id": sample_user.id,
        "goal": "Learn Python",
        "target_duration_days": 5,
    }
    resp = client.post("/api/v1/roadmaps/generate", json=payload)
    assert resp.status_code == 422
    data = resp.json()
    assert "Malformed output" in data["detail"]["message"]
    assert "Day count mismatch" in data["detail"]["errors"]


# ==============================================================================
# 4. ARCHITECTURAL BOUNDARY INVARIANT TEST
# ==============================================================================

def test_ai_layer_does_not_directly_mutate_database(test_db: Session):
    """
    Verify the critical architectural invariant:
    Calling AIService.generate_roadmap directly must NEVER query or mutate the database.
    """
    initial_roadmaps_count = test_db.query(Roadmap).count()
    initial_days_count = test_db.query(Day).count()
    initial_tasks_count = test_db.query(Task).count()
    initial_versions_count = test_db.query(RoadmapVersion).count()
    initial_changes_count = test_db.query(RoadmapChange).count()

    req = RoadmapGenerationRequest(
        user_id=1,
        goal="Direct AI Service Call Test",
        target_duration_days=7,
        daily_available_minutes=60,
    )

    # Invoke AI Service directly
    generated = ai_service.generate_roadmap(req, effective_daily_capacity=60)
    assert isinstance(generated, GeneratedRoadmap)
    assert len(generated.days) == 7

    # Assert database is 100% UNTOUCHED
    test_db.expire_all()
    assert test_db.query(Roadmap).count() == initial_roadmaps_count
    assert test_db.query(Day).count() == initial_days_count
    assert test_db.query(Task).count() == initial_tasks_count
    assert test_db.query(RoadmapVersion).count() == initial_versions_count
    assert test_db.query(RoadmapChange).count() == initial_changes_count
