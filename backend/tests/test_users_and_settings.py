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
        email="settings_tester@mira.test",
        username="settings_tester",
        daily_available_minutes=120,
        theme="system",
        timezone="UTC",
        notifications_enabled=True,
        daily_reminder_enabled=True,
        daily_reminder_time="19:00",
        ask_before_reschedule=True,
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def sample_roadmap(test_db: Session, sample_user: User) -> Roadmap:
    """Create a sample roadmap with days and tasks."""
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="Golang Roadmap",
        description="Learn Go from scratch",
        target_duration_days=2,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()
    test_db.refresh(roadmap)

    day1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    test_db.add(day1)
    test_db.commit()
    test_db.refresh(day1)

    t1 = Task(day_id=day1.id, title="Syntax Basics", estimated_minutes=30, status=TaskStatus.PENDING, order_index=1)
    t2 = Task(day_id=day1.id, title="Goroutines", estimated_minutes=45, status=TaskStatus.PENDING, order_index=2)
    test_db.add_all([t1, t2])
    test_db.commit()
    test_db.refresh(roadmap)
    return roadmap


def test_get_user_preferences(client: TestClient, sample_user: User):
    """Test retrieving user preferences and profile information."""
    resp = client.get(f"/api/v1/users/preferences?user_id={sample_user.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == sample_user.id
    assert data["username"] == "settings_tester"
    assert data["email"] == "settings_tester@mira.test"
    assert data["daily_available_minutes"] == 120
    assert data["theme"] == "system"
    assert data["timezone"] == "UTC"
    assert data["ask_before_reschedule"] is True


def test_update_daily_available_minutes_valid(client: TestClient, sample_user: User):
    """Test updating daily available time with a valid value."""
    resp = client.patch(
        f"/api/v1/users/preferences?user_id={sample_user.id}",
        json={"daily_available_minutes": 90},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["daily_available_minutes"] == 90


def test_update_daily_available_minutes_invalid_bounds(client: TestClient, sample_user: User):
    """Test updating daily available time with nonsensical values (0, negative, >1440)."""
    # 0 or negative
    resp_zero = client.patch(
        f"/api/v1/users/preferences?user_id={sample_user.id}",
        json={"daily_available_minutes": 0},
    )
    assert resp_zero.status_code in (400, 422)

    resp_neg = client.patch(
        f"/api/v1/users/preferences?user_id={sample_user.id}",
        json={"daily_available_minutes": -10},
    )
    assert resp_neg.status_code in (400, 422)

    # Above 1440 (24 hours)
    resp_too_high = client.patch(
        f"/api/v1/users/preferences?user_id={sample_user.id}",
        json={"daily_available_minutes": 99999},
    )
    assert resp_too_high.status_code in (400, 422)


def test_update_theme_preferences(client: TestClient, sample_user: User):
    """Test updating theme preference to light, dark, and system."""
    for theme in ("light", "dark", "system"):
        resp = client.patch(
            f"/api/v1/users/preferences?user_id={sample_user.id}",
            json={"theme": theme},
        )
        assert resp.status_code == 200
        assert resp.json()["theme"] == theme

    # Invalid theme
    resp_inv = client.patch(
        f"/api/v1/users/preferences?user_id={sample_user.id}",
        json={"theme": "neon-glow"},
    )
    assert resp_inv.status_code in (400, 422)


def test_update_timezone_valid_and_invalid(client: TestClient, sample_user: User):
    """Test updating timezone with valid vs invalid IANA timezones."""
    resp_valid = client.patch(
        f"/api/v1/users/preferences?user_id={sample_user.id}",
        json={"timezone": "Asia/Kolkata"},
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["timezone"] == "Asia/Kolkata"

    resp_invalid = client.patch(
        f"/api/v1/users/preferences?user_id={sample_user.id}",
        json={"timezone": "Not/A_Real_Timezone"},
    )
    assert resp_invalid.status_code == 400


def test_settings_update_does_not_mutate_roadmap(
    client: TestClient, test_db: Session, sample_user: User, sample_roadmap: Roadmap
):
    """Updating user capacity must NOT automatically reschedule or mutate existing roadmap tasks."""
    day1 = sample_roadmap.days[0]
    task_count_before = len(day1.tasks)
    task1_minutes_before = day1.tasks[0].estimated_minutes

    resp = client.patch(
        f"/api/v1/users/preferences?user_id={sample_user.id}",
        json={"daily_available_minutes": 45},  # smaller than total day minutes (75)
    )
    assert resp.status_code == 200

    test_db.refresh(day1)
    # Tasks and days remain unchanged
    assert len(day1.tasks) == task_count_before
    assert day1.tasks[0].estimated_minutes == task1_minutes_before


def test_export_roadmap(client: TestClient, sample_roadmap: Roadmap):
    """Test exporting roadmap data returns clean, structured JSON."""
    resp = client.get(f"/api/v1/roadmaps/{sample_roadmap.id}/export")
    assert resp.status_code == 200
    data = resp.json()

    assert "roadmap" in data
    assert data["roadmap"]["title"] == "Golang Roadmap"
    assert "days" in data
    assert len(data["days"]) == 1
    assert "tasks" in data
    assert len(data["tasks"]) == 2
    assert "history" in data
    assert "exported_at" in data

    # Ensure no internal secrets or sensitive columns exposed
    for key in ("password", "api_key", "secret", "token"):
        assert key not in data["roadmap"]


def test_export_nonexistent_roadmap(client: TestClient):
    """Test exporting a nonexistent roadmap returns 404."""
    resp = client.get("/api/v1/roadmaps/999999/export")
    assert resp.status_code == 404


def test_delete_roadmap_cascades(client: TestClient, test_db: Session, sample_roadmap: Roadmap):
    """Test deleting roadmap deletes it and cascades associated days and tasks."""
    roadmap_id = sample_roadmap.id
    resp = client.delete(f"/api/v1/roadmaps/{roadmap_id}")
    assert resp.status_code == 204

    # Verification: roadmap no longer exists
    get_resp = client.get(f"/api/v1/roadmaps/{roadmap_id}")
    assert get_resp.status_code == 404

    # Days and tasks deleted
    remaining_days = test_db.query(Day).filter(Day.roadmap_id == roadmap_id).all()
    assert len(remaining_days) == 0


def test_nonexistent_user_preferences(client: TestClient):
    """Test querying preferences for nonexistent user returns 404."""
    resp = client.get("/api/v1/users/preferences?user_id=999999")
    assert resp.status_code == 404
