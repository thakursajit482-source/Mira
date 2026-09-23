import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import get_db
from backend.app.models.base import Base
from backend.app.models.enums import RoadmapStatus, DayStatus, TaskStatus
from backend.app.models.user import User
from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.models.task import Task
from backend.app.services.progress_service import progress_service


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
    """Create a sample user with 90 minutes daily available capacity."""
    user = User(
        email="daily_test@mira.test",
        username="daily_tester",
        daily_available_minutes=90,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


def test_analysis_not_found(client: TestClient):
    """Return 404 if roadmap does not exist."""
    res = client.get("/api/v1/roadmaps/99999/daily-analysis")
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_analysis_on_track(client: TestClient, test_db: Session, sample_user: User):
    """When remaining work is comfortably below capacity, status is ON_TRACK."""
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="Python Basics",
        target_duration_days=5,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()

    day = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    test_db.add(day)
    test_db.commit()

    # 45 minutes total work vs 90 minutes available
    t1 = Task(day_id=day.id, title="Variables", estimated_minutes=25, order_index=0)
    t2 = Task(day_id=day.id, title="Data Types", estimated_minutes=20, order_index=1)
    test_db.add_all([t1, t2])
    test_db.commit()

    res = client.get(f"/api/v1/roadmaps/{roadmap.id}/daily-analysis")
    assert res.status_code == 200
    data = res.json()

    assert data["day_number"] == 1
    assert data["status"] == "ON_TRACK"
    assert data["remaining_task_count"] == 2
    assert data["completed_task_count"] == 0
    assert data["remaining_minutes"] == 45
    assert data["available_minutes"] == 90
    assert data["remaining_capacity_minutes"] == 45
    assert data["overage_minutes"] == 0
    assert "comfortably" in data["recommendation"].lower()


def test_analysis_tight(client: TestClient, test_db: Session, sample_user: User):
    """When remaining work is close to limit (within 15m or >= 85%), status is TIGHT."""
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="Go Fundamentals",
        target_duration_days=5,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()

    day = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    test_db.add(day)
    test_db.commit()

    # 80 minutes of work vs 90 minutes available (10 min to spare)
    t1 = Task(day_id=day.id, title="Goroutines", estimated_minutes=50, order_index=0)
    t2 = Task(day_id=day.id, title="Channels", estimated_minutes=30, order_index=1)
    test_db.add_all([t1, t2])
    test_db.commit()

    res = client.get(f"/api/v1/roadmaps/{roadmap.id}/daily-analysis")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "TIGHT"
    assert data["remaining_minutes"] == 80
    assert data["remaining_capacity_minutes"] == 10
    assert data["overage_minutes"] == 0
    assert "tight" in data["recommendation"].lower()


def test_analysis_over_capacity(client: TestClient, test_db: Session, sample_user: User):
    """When remaining work exceeds available capacity, status is OVER_CAPACITY."""
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="Rust Deep Dive",
        target_duration_days=5,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()

    day = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    test_db.add(day)
    test_db.commit()

    # 120 minutes of work vs 90 minutes available (30 min overage)
    t1 = Task(day_id=day.id, title="Ownership", estimated_minutes=60, order_index=0)
    t2 = Task(day_id=day.id, title="Borrowing", estimated_minutes=60, order_index=1)
    test_db.add_all([t1, t2])
    test_db.commit()

    res = client.get(f"/api/v1/roadmaps/{roadmap.id}/daily-analysis")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "OVER_CAPACITY"
    assert data["remaining_minutes"] == 120
    assert data["available_minutes"] == 90
    assert data["overage_minutes"] == 30
    assert data["remaining_capacity_minutes"] == 0
    assert "30 min over" in data["recommendation"]
    assert "lighter schedule" in data["recommendation"].lower()


def test_analysis_partially_completed_day(client: TestClient, test_db: Session, sample_user: User):
    """Completing a task deterministically shifts workload from over capacity to on track."""
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="Web Architecture",
        target_duration_days=5,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()

    day = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    test_db.add(day)
    test_db.commit()

    t1 = Task(day_id=day.id, title="DNS and Routing", estimated_minutes=60, order_index=0)
    t2 = Task(day_id=day.id, title="Load Balancers", estimated_minutes=50, order_index=1)
    test_db.add_all([t1, t2])
    test_db.commit()

    # 1. Before completion: 110 min > 90 min -> OVER_CAPACITY
    res1 = client.get(f"/api/v1/roadmaps/{roadmap.id}/daily-analysis")
    assert res1.json()["status"] == "OVER_CAPACITY"

    # 2. Complete t1 (60m)
    progress_service.complete_task(test_db, t1.id)

    # 3. After completion: remaining is 50 min < 90 min -> ON_TRACK
    res2 = client.get(f"/api/v1/roadmaps/{roadmap.id}/daily-analysis")
    data2 = res2.json()
    assert data2["status"] == "ON_TRACK"
    assert data2["completed_task_count"] == 1
    assert data2["remaining_task_count"] == 1
    assert data2["completed_minutes"] == 60
    assert data2["remaining_minutes"] == 50
    assert data2["remaining_capacity_minutes"] == 40


def test_analysis_complete_day(client: TestClient, test_db: Session, sample_user: User):
    """When all tasks on the current day are complete, status is COMPLETE."""
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="Design Systems",
        target_duration_days=5,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()

    day = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.CURRENT)
    test_db.add(day)
    test_db.commit()

    t1 = Task(day_id=day.id, title="Color Tokens", estimated_minutes=30, order_index=0)
    test_db.add(t1)
    test_db.commit()

    progress_service.complete_task(test_db, t1.id)

    res = client.get(f"/api/v1/roadmaps/{roadmap.id}/daily-analysis")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "COMPLETE"
    assert data["remaining_task_count"] == 0
    assert data["completed_task_count"] == 1
    assert data["remaining_minutes"] == 0
    assert "nothing else is required today" in data["recommendation"].lower()


def test_analysis_upcoming_workload_awareness(client: TestClient, test_db: Session, sample_user: User):
    """Calculates tomorrow's minutes and upcoming average across future incomplete days."""
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="Algorithms",
        target_duration_days=5,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.LOCKED)
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2, d3])
    test_db.commit()

    t1 = Task(day_id=d1.id, title="D1 Task", estimated_minutes=40, order_index=0)
    t2 = Task(day_id=d2.id, title="D2 Task", estimated_minutes=60, order_index=0)
    t3 = Task(day_id=d3.id, title="D3 Task", estimated_minutes=80, order_index=0)
    test_db.add_all([t1, t2, t3])
    test_db.commit()

    res = client.get(f"/api/v1/roadmaps/{roadmap.id}/daily-analysis")
    assert res.status_code == 200
    data = res.json()

    assert data["tomorrow_minutes"] == 60
    # Average of D2 (60) and D3 (80) = 70
    assert data["upcoming_average_minutes"] == 70


def test_analysis_read_only_invariant(client: TestClient, test_db: Session, sample_user: User):
    """Calling daily-analysis endpoint must be strictly read-only."""
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="Immutability Test",
        target_duration_days=5,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()

    day = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    test_db.add(day)
    test_db.commit()

    t = Task(day_id=day.id, title="Task", estimated_minutes=30, order_index=0)
    test_db.add(t)
    test_db.commit()

    task_count_before = test_db.query(Task).count()
    day_count_before = test_db.query(Day).count()
    roadmap_count_before = test_db.query(Roadmap).count()

    res = client.get(f"/api/v1/roadmaps/{roadmap.id}/daily-analysis")
    assert res.status_code == 200

    assert test_db.query(Task).count() == task_count_before
    assert test_db.query(Day).count() == day_count_before
    assert test_db.query(Roadmap).count() == roadmap_count_before
