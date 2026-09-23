from datetime import datetime, timezone
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
from backend.app.models.notification import Notification, NotificationType, NotificationSeverity


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
    """Create a sample user with default notification settings."""
    user = User(
        email="notify_tester@mira.test",
        username="notify_tester",
        daily_available_minutes=60,
        notifications_enabled=True,
        daily_reminder_enabled=True,
        daily_reminder_time="19:00",
        timezone="UTC",
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def sample_roadmap(test_db: Session, sample_user: User) -> Roadmap:
    """Create a sample active roadmap with 2 days."""
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="Python Mastery",
        description="Learn Python",
        target_duration_days=2,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()
    test_db.refresh(roadmap)

    # Day 1 - Current with 2 tasks totaling 90 min (over capacity of 60)
    day1 = Day(
        roadmap_id=roadmap.id,
        day_number=1,
        status=DayStatus.CURRENT,
    )
    test_db.add(day1)
    test_db.commit()
    test_db.refresh(day1)

    t1 = Task(day_id=day1.id, title="Syntax", estimated_minutes=45, status=TaskStatus.PENDING, order_index=1)
    t2 = Task(day_id=day1.id, title="Functions", estimated_minutes=45, status=TaskStatus.PENDING, order_index=2)
    test_db.add_all([t1, t2])

    # Day 2 - Pending
    day2 = Day(
        roadmap_id=roadmap.id,
        day_number=2,
        status=DayStatus.LOCKED,
    )
    test_db.add(day2)
    test_db.commit()
    test_db.refresh(day2)

    t3 = Task(day_id=day2.id, title="Classes", estimated_minutes=60, status=TaskStatus.PENDING, order_index=1)
    test_db.add(t3)
    test_db.commit()
    test_db.refresh(roadmap)
    return roadmap


def test_notifications_disabled(client: TestClient, test_db: Session, sample_user: User, sample_roadmap: Roadmap):
    """When notifications_enabled is False, no notifications are generated."""
    sample_user.notifications_enabled = False
    test_db.commit()

    resp = client.get(f"/api/v1/notifications?user_id={sample_user.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unread_count"] == 0
    assert len(data["notifications"]) == 0


def test_daily_reminder_disabled(client: TestClient, test_db: Session, sample_user: User, sample_roadmap: Roadmap):
    """When daily_reminder_enabled is False, over-capacity triggers but no daily reminders trigger."""
    sample_user.daily_reminder_enabled = False
    test_db.commit()

    # Time at 20:00 UTC (after reminder time 19:00)
    ref_time = datetime(2026, 9, 23, 20, 0, 0, tzinfo=timezone.utc).isoformat()
    resp = client.get(f"/api/v1/notifications?user_id={sample_user.id}&reference_time={ref_time}")
    assert resp.status_code == 200
    data = resp.json()

    types = [n["type"] for n in data["notifications"]]
    assert NotificationType.OVER_CAPACITY in types
    assert NotificationType.DAY_INCOMPLETE not in types
    assert NotificationType.DAILY_FOCUS not in types


def test_daily_focus_notification(client: TestClient, sample_user: User, sample_roadmap: Roadmap):
    """Before reminder time (e.g. 10:00 AM UTC), DAILY_FOCUS is generated."""
    # User capacity is 60 min, day 1 is 90 min. But let's check morning time 10:00 UTC.
    ref_time = datetime(2026, 9, 23, 10, 0, 0, tzinfo=timezone.utc).isoformat()
    resp = client.get(f"/api/v1/notifications?user_id={sample_user.id}&reference_time={ref_time}")
    assert resp.status_code == 200
    data = resp.json()

    types = [n["type"] for n in data["notifications"]]
    assert NotificationType.DAILY_FOCUS in types
    focus_n = next(n for n in data["notifications"] if n["type"] == NotificationType.DAILY_FOCUS)
    assert "Day 1" in focus_n["title"]
    assert "2 tasks planned" in focus_n["message"]


def test_day_incomplete_notification(client: TestClient, sample_user: User, sample_roadmap: Roadmap):
    """After reminder time (e.g. 20:00 UTC), DAY_INCOMPLETE is generated."""
    ref_time = datetime(2026, 9, 23, 20, 0, 0, tzinfo=timezone.utc).isoformat()
    resp = client.get(f"/api/v1/notifications?user_id={sample_user.id}&reference_time={ref_time}")
    assert resp.status_code == 200
    data = resp.json()

    types = [n["type"] for n in data["notifications"]]
    assert NotificationType.DAY_INCOMPLETE in types
    inc_n = next(n for n in data["notifications"] if n["type"] == NotificationType.DAY_INCOMPLETE)
    assert "Day 1 plan is incomplete" in inc_n["title"]
    assert "2 tasks remaining" in inc_n["message"]


def test_completed_day_no_reminder(client: TestClient, test_db: Session, sample_user: User, sample_roadmap: Roadmap):
    """If all tasks on all days are completed, no daily reminder is generated, only ROADMAP_COMPLETE."""
    for d in sample_roadmap.days:
        for t in d.tasks:
            t.status = TaskStatus.COMPLETED
            t.is_completed = True
        d.status = DayStatus.COMPLETED
    test_db.commit()

    ref_time = datetime(2026, 9, 23, 21, 0, 0, tzinfo=timezone.utc).isoformat()
    resp = client.get(f"/api/v1/notifications?user_id={sample_user.id}&reference_time={ref_time}")
    assert resp.status_code == 200
    data = resp.json()
    types = [n["type"] for n in data["notifications"]]
    assert NotificationType.DAY_INCOMPLETE not in types
    assert NotificationType.DAILY_FOCUS not in types
    assert NotificationType.ROADMAP_COMPLETE in types


def test_over_capacity_notification(client: TestClient, sample_user: User, sample_roadmap: Roadmap):
    """When day tasks exceed daily_available_minutes, OVER_CAPACITY notification is triggered."""
    ref_time = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    resp = client.get(f"/api/v1/notifications?user_id={sample_user.id}&reference_time={ref_time}")
    assert resp.status_code == 200
    data = resp.json()

    types = [n["type"] for n in data["notifications"]]
    assert NotificationType.OVER_CAPACITY in types
    over_n = next(n for n in data["notifications"] if n["type"] == NotificationType.OVER_CAPACITY)
    assert over_n["title"] == "Plan is over capacity"
    # User available is 60, day 1 is 90 -> 30 min over
    assert "30 minutes over" in over_n["message"]


def test_deduplication_idempotency(client: TestClient, sample_user: User, sample_roadmap: Roadmap):
    """Multiple calls do not create duplicate notifications."""
    ref_time = datetime(2026, 9, 23, 14, 0, 0, tzinfo=timezone.utc).isoformat()
    resp1 = client.get(f"/api/v1/notifications?user_id={sample_user.id}&reference_time={ref_time}")
    assert resp1.status_code == 200
    count1 = resp1.json()["total_count"]

    resp2 = client.get(f"/api/v1/notifications?user_id={sample_user.id}&reference_time={ref_time}")
    assert resp2.status_code == 200
    count2 = resp2.json()["total_count"]
    assert count1 == count2


def test_mark_as_read(client: TestClient, sample_user: User, sample_roadmap: Roadmap):
    """Mark a notification as read."""
    ref_time = datetime(2026, 9, 23, 14, 0, 0, tzinfo=timezone.utc).isoformat()
    resp = client.get(f"/api/v1/notifications?user_id={sample_user.id}&reference_time={ref_time}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["unread_count"] > 0
    first_id = data["notifications"][0]["id"]

    # Mark as read
    patch_resp = client.patch(f"/api/v1/notifications/{first_id}/read?user_id={sample_user.id}")
    assert patch_resp.status_code == 200
    assert patch_resp.json()["read"] is True

    # Check updated unread count
    resp_after = client.get(f"/api/v1/notifications?user_id={sample_user.id}&reference_time={ref_time}")
    assert resp_after.json()["unread_count"] == data["unread_count"] - 1


def test_mark_all_as_read(client: TestClient, sample_user: User, sample_roadmap: Roadmap):
    """Mark all notifications as read."""
    ref_time = datetime(2026, 9, 23, 14, 0, 0, tzinfo=timezone.utc).isoformat()
    client.get(f"/api/v1/notifications?user_id={sample_user.id}&reference_time={ref_time}")

    # Mark all read
    resp = client.patch(f"/api/v1/notifications/read-all?user_id={sample_user.id}")
    assert resp.status_code == 200
    assert resp.json()["updated_count"] >= 1

    # Check that unread count is 0
    resp_after = client.get(f"/api/v1/notifications?user_id={sample_user.id}&reference_time={ref_time}")
    assert resp_after.json()["unread_count"] == 0


def test_timezone_awareness(client: TestClient, test_db: Session, sample_user: User, sample_roadmap: Roadmap):
    """User in Asia/Kolkata (+05:30) vs UTC evaluates reminder time according to their local clock."""
    # At 14:00 UTC, in UTC it's 14:00 (before 19:00 -> DAILY_FOCUS)
    # But in Asia/Kolkata (+05:30), 14:00 UTC is 19:30 local time (after 19:00 -> DAY_INCOMPLETE)
    sample_user.timezone = "Asia/Kolkata"
    test_db.commit()

    ref_time = datetime(2026, 9, 23, 14, 0, 0, tzinfo=timezone.utc).isoformat()
    resp = client.get(f"/api/v1/notifications?user_id={sample_user.id}&reference_time={ref_time}")
    assert resp.status_code == 200
    types = [n["type"] for n in resp.json()["notifications"]]
    assert NotificationType.DAY_INCOMPLETE in types


def test_notification_404_errors(client: TestClient):
    """Returns 404 for nonexistent user or nonexistent notification."""
    # Nonexistent user
    resp = client.get("/api/v1/notifications?user_id=999999")
    assert resp.status_code == 404

    # Nonexistent notification
    resp = client.patch("/api/v1/notifications/999999/read?user_id=1")
    assert resp.status_code == 404


def test_notification_preferences_get_and_patch(client: TestClient, sample_user: User):
    """Get and update notification preferences."""
    # GET preferences
    resp = client.get(f"/api/v1/notifications/preferences?user_id={sample_user.id}")
    assert resp.status_code == 200
    pref = resp.json()
    assert pref["notifications_enabled"] is True
    assert pref["daily_reminder_time"] == "19:00"

    # PATCH preferences with valid data
    patch_resp = client.patch(
        f"/api/v1/notifications/preferences?user_id={sample_user.id}",
        json={
            "daily_reminder_time": "20:30",
            "timezone": "America/New_York",
            "daily_reminder_enabled": False,
        },
    )
    assert patch_resp.status_code == 200
    updated = patch_resp.json()
    assert updated["daily_reminder_time"] == "20:30"
    assert updated["timezone"] == "America/New_York"
    assert updated["daily_reminder_enabled"] is False

    # PATCH preferences with invalid timezone returns 400
    invalid_resp = client.patch(
        f"/api/v1/notifications/preferences?user_id={sample_user.id}",
        json={"timezone": "Invalid/Timezone_Not_Real"},
    )
    assert invalid_resp.status_code == 400
