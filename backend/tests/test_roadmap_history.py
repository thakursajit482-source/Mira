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
from backend.app.schemas.roadmap import RoadmapCreate
from backend.app.services.roadmap_service import roadmap_service
from backend.app.roadmap_engine import engine as roadmap_engine
from backend.app.roadmap_engine import rescheduler as rescheduling_engine
from backend.app.schemas.insertion import RoadmapInsertionRequest, NewDayDefinition, NewTaskDefinition
from backend.app.schemas.rescheduling import RoadmapRescheduleRequest
from backend.app.ai.schemas import RoadmapGenerationRequest


@pytest.fixture
def test_db():
    """Create a fresh in-memory SQLite database for each test."""
    db_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(db_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(db_engine)


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
    """Create a sample user."""
    user = User(
        email="history_test@mira.test",
        username="history_tester",
        daily_available_minutes=120,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


def test_get_history_not_found(client: TestClient):
    """Should return 404 if roadmap does not exist."""
    response = client.get("/api/v1/roadmaps/99999/history")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_history_empty(client: TestClient, test_db: Session, sample_user: User):
    """A roadmap created without changes returns empty changes list."""
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="Empty History Roadmap",
        target_duration_days=10,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()
    test_db.refresh(roadmap)

    response = client.get(f"/api/v1/roadmaps/{roadmap.id}/history")
    assert response.status_code == 200
    data = response.json()
    assert data["roadmap_id"] == roadmap.id
    assert data["total_changes"] == 0
    assert data["changes"] == []


def test_get_history_after_ai_generation(client: TestClient, test_db: Session, sample_user: User):
    """Newly AI-generated roadmap should have an INITIAL_GENERATION entry with version 1."""
    gen_req = RoadmapGenerationRequest(
        user_id=sample_user.id,
        goal="Master FastAPI Development",
        target_duration_days=5,
        daily_available_minutes=60,
    )
    roadmap = roadmap_service.generate_and_create_roadmap(test_db, gen_req)

    response = client.get(f"/api/v1/roadmaps/{roadmap.id}/history")
    assert response.status_code == 200
    data = response.json()
    assert data["roadmap_id"] == roadmap.id
    assert data["total_changes"] == 1

    change = data["changes"][0]
    assert change["change_type"] == "INITIAL_GENERATION"
    assert change["version_number"] == 1
    assert "Generated initial roadmap" in change["description"]
    assert change["metadata_info"]["goal"] == "Master FastAPI Development"
    assert change["metadata_info"]["target_duration_days"] == 5
    assert change["metadata_info"]["daily_available_minutes"] == 60


def test_get_history_chronological_order_and_insertion(
    client: TestClient, test_db: Session, sample_user: User
):
    """History must return changes in newest-first order with correct version mappings."""
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="TypeScript Fundamentals",
        target_duration_days=10,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()

    v1 = RoadmapVersion(
        roadmap_id=roadmap.id,
        version_number=1,
        change_summary="Initial generation",
        snapshot_data={"days": []},
    )
    test_db.add(v1)
    test_db.flush()

    c1_init = RoadmapChange(
        roadmap_id=roadmap.id,
        version_id=v1.id,
        change_type=RoadmapChangeType.INITIAL_GENERATION,
        description="Initial generation with 3 days",
        metadata_info={"total_days": 3},
    )
    test_db.add(c1_init)

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.CURRENT)
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2, d3])
    test_db.commit()

    # 3. Insert 2 new days
    insert_req = RoadmapInsertionRequest(
        new_days=[
            NewDayDefinition(
                tasks=[
                    NewTaskDefinition(title="Advanced Generics", estimated_minutes=60),
                ]
            ),
            NewDayDefinition(
                tasks=[
                    NewTaskDefinition(title="Conditional Types", estimated_minutes=60),
                ]
            ),
        ]
    )
    res = roadmap_service.apply_insertion(test_db, roadmap.id, insert_req)
    assert not res.conflict

    # 4. Fetch history
    response = client.get(f"/api/v1/roadmaps/{roadmap.id}/history")
    assert response.status_code == 200
    data = response.json()
    assert data["total_changes"] == 2

    # Newest first
    c0 = data["changes"][0]
    c1 = data["changes"][1]

    assert c0["change_type"] == "CONTENT_INSERTION"
    assert c0["version_number"] == 2
    assert c0["metadata_info"]["inserted_days_count"] == 2
    assert c0["metadata_info"]["insertion_start_day"] == 2

    assert c1["change_type"] == "INITIAL_GENERATION"
    assert c1["version_number"] == 1


def test_get_history_read_only_invariant(client: TestClient, test_db: Session, sample_user: User):
    """Calling history endpoint must be strictly read-only and never mutate database counts."""
    gen_req = RoadmapGenerationRequest(
        user_id=sample_user.id,
        goal="Read-Only Invariant Test",
        target_duration_days=5,
        daily_available_minutes=60,
    )
    roadmap = roadmap_service.generate_and_create_roadmap(test_db, gen_req)

    count_changes_before = test_db.query(RoadmapChange).count()
    count_versions_before = test_db.query(RoadmapVersion).count()
    count_roadmaps_before = test_db.query(Roadmap).count()

    response = client.get(f"/api/v1/roadmaps/{roadmap.id}/history")
    assert response.status_code == 200

    assert test_db.query(RoadmapChange).count() == count_changes_before
    assert test_db.query(RoadmapVersion).count() == count_versions_before
    assert test_db.query(Roadmap).count() == count_roadmaps_before


def test_get_history_after_rescheduling(client: TestClient, test_db: Session, sample_user: User):
    """Rescheduling creates a WORKLOAD_REBALANCE change that appears at the top of history."""
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="Reschedule History Roadmap",
        target_duration_days=5,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.CURRENT)
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2, d3])
    test_db.commit()

    # Day 2 has an overload of tasks
    t1 = Task(day_id=d2.id, title="Task 1", estimated_minutes=90, order_index=0)
    t2 = Task(day_id=d2.id, title="Task 2", estimated_minutes=90, order_index=1)
    test_db.add_all([t1, t2])
    test_db.commit()

    reschedule_req = RoadmapRescheduleRequest(daily_available_minutes=90)
    result = roadmap_service.apply_reschedule(test_db, roadmap.id, reschedule_req)
    assert not result.conflict

    response = client.get(f"/api/v1/roadmaps/{roadmap.id}/history")
    assert response.status_code == 200
    data = response.json()
    assert data["total_changes"] >= 1
    top_change = data["changes"][0]
    assert top_change["change_type"] == "WORKLOAD_REBALANCE"
    assert top_change["metadata_info"]["daily_capacity_minutes"] == 90

