import pytest
from datetime import datetime, timezone
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
from backend.app.roadmap_engine.engine import roadmap_engine


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
    user = User(email="engine_user@example.com", username="engine_user")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


# 1. Find first incomplete Day
def test_find_first_incomplete_day():
    day1 = Day(day_number=1, status=DayStatus.COMPLETED)
    day2 = Day(day_number=2, status=DayStatus.COMPLETED)
    day3 = Day(day_number=3, status=DayStatus.IN_PROGRESS)
    day4 = Day(day_number=4, status=DayStatus.LOCKED)

    first = roadmap_engine.find_first_incomplete_day([day1, day2, day3, day4])
    assert first is not None
    assert first.day_number == 3

    # All completed
    first_none = roadmap_engine.find_first_incomplete_day([day1, day2])
    assert first_none is None


# 2. Completed Days remain unchanged
# 3. Insert 1 new Day
# 5. Existing future Days shift correctly
# 6. Existing tasks remain attached to shifted Days
# 7. New tasks are created correctly
# 8. New Days start incomplete
# 10. Successful insertion preserves target_duration_days
# 15. Day-number uniqueness remains valid
# 16. Task ordering remains valid
# 17. Existing completion timestamps remain unchanged
# 18. Existing completed Days remain completed
# 20. RoadmapVersion/RoadmapChange audit record is created
def test_successful_insertion_and_shifting(client: TestClient, sample_user: User, test_db: Session):
    # Setup: 10-day roadmap with 2 completed days and 2 incomplete days (capacity = 10, total used = 4)
    roadmap = Roadmap(user_id=sample_user.id, title="10-day plan", target_duration_days=10)
    test_db.add(roadmap)
    test_db.commit()

    completed_ts_1 = datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc)
    completed_ts_2 = datetime(2026, 9, 2, 11, 0, 0, tzinfo=timezone.utc)

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=completed_ts_1)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.COMPLETED, completed_at=completed_ts_2)
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.CURRENT)
    d4 = Day(roadmap_id=roadmap.id, day_number=4, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2, d3, d4])
    test_db.commit()

    # Tasks on d3 (to verify they shift with d3)
    t3 = Task(day_id=d3.id, title="Old Task 3.1", order_index=0, estimated_minutes=45)
    t4 = Task(day_id=d4.id, title="Old Task 4.1", order_index=0, estimated_minutes=60)
    test_db.add_all([t3, t4])
    test_db.commit()

    # Insert 2 new days at first incomplete day (Day 3)
    payload = {
        "new_days": [
            {
                "tasks": [
                    {"title": "New Task A1", "order_index": 0, "estimated_minutes": 30},
                    {"title": "New Task A2", "order_index": 1, "estimated_minutes": 30},
                ]
            },
            {
                "tasks": [
                    {"title": "New Task B1", "order_index": 0, "estimated_minutes": 40},
                ]
            },
        ],
        "metadata": {"source": "Git Course"},
    }

    resp = client.post(f"/api/v1/roadmaps/{roadmap.id}/insert", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["conflict"] is False
    assert data["inserted_days_count"] == 2
    assert data["shifted_days_count"] == 2
    assert data["first_incomplete_day"] == 3
    assert data["target_duration_days"] == 10

    # Fetch updated details
    details_resp = client.get(f"/api/v1/roadmaps/{roadmap.id}/details")
    assert details_resp.status_code == 200
    details = details_resp.json()
    days = details["days"]
    assert len(days) == 6  # 2 completed + 2 new + 2 shifted = 6

    # Verify Day 1 & 2: completed history is completely intact
    assert days[0]["day_number"] == 1
    assert days[0]["status"] == "COMPLETED"
    assert days[1]["day_number"] == 2
    assert days[1]["status"] == "COMPLETED"

    # Verify Day 3 & 4: New content inserted
    assert days[2]["day_number"] == 3
    assert days[2]["status"] == "CURRENT"
    assert len(days[2]["tasks"]) == 2
    assert days[2]["tasks"][0]["title"] == "New Task A1"
    assert days[2]["tasks"][1]["title"] == "New Task A2"

    assert days[3]["day_number"] == 4
    assert days[3]["status"] == "LOCKED"
    assert len(days[3]["tasks"]) == 1
    assert days[3]["tasks"][0]["title"] == "New Task B1"

    # Verify Day 5 & 6: Old Day 3 and Day 4 shifted forward
    assert days[4]["day_number"] == 5
    assert days[4]["status"] == "LOCKED"
    assert len(days[4]["tasks"]) == 1
    assert days[4]["tasks"][0]["title"] == "Old Task 3.1"
    assert days[4]["tasks"][0]["id"] == t3.id  # Task preservation

    assert days[5]["day_number"] == 6
    assert days[5]["status"] == "LOCKED"
    assert len(days[5]["tasks"]) == 1
    assert days[5]["tasks"][0]["title"] == "Old Task 4.1"
    assert days[5]["tasks"][0]["id"] == t4.id

    # Verify exactly one CURRENT day exists
    current_days = [d for d in days if d["status"] == "CURRENT"]
    assert len(current_days) == 1
    assert current_days[0]["day_number"] == 3

    # Verify audit version and change log were created
    versions = test_db.query(RoadmapVersion).filter_by(roadmap_id=roadmap.id).all()
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert "Inserted 2 days starting at Day 3" in versions[0].change_summary

    changes = test_db.query(RoadmapChange).filter_by(roadmap_id=roadmap.id).all()
    assert len(changes) == 1
    assert changes[0].change_type == RoadmapChangeType.CONTENT_INSERTION
    assert changes[0].version_id == versions[0].id


# 9. Preview does not mutate database
def test_preview_does_not_mutate_database(client: TestClient, sample_user: User, test_db: Session):
    roadmap = Roadmap(user_id=sample_user.id, title="Preview Test", target_duration_days=10)
    test_db.add(roadmap)
    test_db.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.CURRENT)
    test_db.add_all([d1, d2])
    test_db.commit()

    payload = {
        "new_days": [
            {"tasks": [{"title": "Preview Task", "order_index": 0}]}
        ]
    }

    # Call preview
    preview_resp = client.post(f"/api/v1/roadmaps/{roadmap.id}/insert/preview", json=payload)
    assert preview_resp.status_code == 200
    data = preview_resp.json()
    assert data["status"] == "SUCCESS"
    assert data["conflict"] is False
    assert data["first_incomplete_day"] == 2
    assert data["inserted_days_count"] == 1
    assert data["shifted_days_count"] == 1
    assert len(data["shifted_days"]) == 1
    assert data["shifted_days"][0]["old_day_number"] == 2
    assert data["shifted_days"][0]["new_day_number"] == 3

    # Assert database was NOT mutated
    test_db.expire_all()
    days_in_db = test_db.query(Day).filter_by(roadmap_id=roadmap.id).all()
    assert len(days_in_db) == 2
    assert [d.day_number for d in sorted(days_in_db, key=lambda d: d.day_number)] == [1, 2]
    assert test_db.query(RoadmapVersion).count() == 0
    assert test_db.query(RoadmapChange).count() == 0


# 11. Insufficient capacity produces conflict
# 12. Insufficient capacity does not mutate database
# 21. Critical Integration Test (Section 27):
# 10-day roadmap with 3 completed, 7 incomplete. Insert 3 days -> conflict!
def test_critical_insufficient_capacity_conflict(client: TestClient, sample_user: User, test_db: Session):
    roadmap = Roadmap(user_id=sample_user.id, title="Strict 10-day roadmap", target_duration_days=10)
    test_db.add(roadmap)
    test_db.commit()

    # Days 1..3 COMPLETED
    for num in range(1, 4):
        test_db.add(Day(roadmap_id=roadmap.id, day_number=num, status=DayStatus.COMPLETED))

    # Days 4..10 incomplete
    for num in range(4, 11):
        status = DayStatus.CURRENT if num == 4 else DayStatus.LOCKED
        test_db.add(Day(roadmap_id=roadmap.id, day_number=num, status=status))

    test_db.commit()
    assert test_db.query(Day).filter_by(roadmap_id=roadmap.id).count() == 10

    # User attempts to insert 3 new days at Day 4:
    # 3 completed + 3 new + 7 future = 13 > 10 (Insufficient capacity!)
    payload = {
        "new_days": [
            {"tasks": [{"title": "Day A", "order_index": 0}]},
            {"tasks": [{"title": "Day B", "order_index": 0}]},
            {"tasks": [{"title": "Day C", "order_index": 0}]},
        ]
    }

    # 1. Preview detects conflict
    preview_resp = client.post(f"/api/v1/roadmaps/{roadmap.id}/insert/preview", json=payload)
    assert preview_resp.status_code == 200
    prev_data = preview_resp.json()
    assert prev_data["status"] == "CONFLICT"
    assert prev_data["conflict"] is True
    assert prev_data["conflict_reason"] == "INSUFFICIENT_CAPACITY"
    assert prev_data["required_total_days"] == 13
    assert prev_data["target_duration_days"] == 10

    # 2. Actual insert returns 409 Conflict with conflict payload
    insert_resp = client.post(f"/api/v1/roadmaps/{roadmap.id}/insert", json=payload)
    assert insert_resp.status_code == 409
    ins_data = insert_resp.json()
    assert ins_data["status"] == "CONFLICT"
    assert ins_data["conflict"] is True
    assert ins_data["conflict_reason"] == "INSUFFICIENT_CAPACITY"

    # 3. Database is COMPLETELY UNTOUCHED: no silent deletion, no silent extension!
    test_db.expire_all()
    days_after = sorted(test_db.query(Day).filter_by(roadmap_id=roadmap.id).all(), key=lambda d: d.day_number)
    assert len(days_after) == 10
    assert [d.day_number for d in days_after] == list(range(1, 11))
    assert days_after[0].status == DayStatus.COMPLETED
    assert days_after[1].status == DayStatus.COMPLETED
    assert days_after[2].status == DayStatus.COMPLETED
    assert days_after[3].status == DayStatus.CURRENT
    assert test_db.query(RoadmapVersion).count() == 0


# 13. All Days completed case returns NO_INCOMPLETE_DAY
def test_all_days_completed_returns_conflict(client: TestClient, sample_user: User, test_db: Session):
    roadmap = Roadmap(user_id=sample_user.id, title="Finished Roadmap", target_duration_days=5)
    test_db.add(roadmap)
    test_db.commit()

    for num in range(1, 6):
        test_db.add(Day(roadmap_id=roadmap.id, day_number=num, status=DayStatus.COMPLETED))
    test_db.commit()

    payload = {
        "new_days": [
            {"tasks": [{"title": "Post-grad Task", "order_index": 0}]}
        ]
    }

    # Preview
    prev = client.post(f"/api/v1/roadmaps/{roadmap.id}/insert/preview", json=payload).json()
    assert prev["status"] == "CONFLICT"
    assert prev["conflict_reason"] == "NO_INCOMPLETE_DAY"

    # Insert
    ins = client.post(f"/api/v1/roadmaps/{roadmap.id}/insert", json=payload)
    assert ins.status_code == 409
    assert ins.json()["conflict_reason"] == "NO_INCOMPLETE_DAY"


# 14. Zero-Day roadmap case
def test_zero_day_roadmap_insertion(client: TestClient, sample_user: User, test_db: Session):
    roadmap = Roadmap(user_id=sample_user.id, title="Fresh Roadmap", target_duration_days=5)
    test_db.add(roadmap)
    test_db.commit()

    # Insert 2 days into empty roadmap
    payload = {
        "new_days": [
            {"tasks": [{"title": "Day 1 Task", "order_index": 0}]},
            {"tasks": [{"title": "Day 2 Task", "order_index": 0}]},
        ]
    }

    resp = client.post(f"/api/v1/roadmaps/{roadmap.id}/insert", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["inserted_days_count"] == 2
    assert data["first_incomplete_day"] == 1

    days = test_db.query(Day).filter_by(roadmap_id=roadmap.id).all()
    assert len(days) == 2
    assert [d.day_number for d in sorted(days, key=lambda d: d.day_number)] == [1, 2]


# Zero-day roadmap exceeding target duration
def test_zero_day_roadmap_overflow_conflict(client: TestClient, sample_user: User, test_db: Session):
    roadmap = Roadmap(user_id=sample_user.id, title="Small Roadmap", target_duration_days=2)
    test_db.add(roadmap)
    test_db.commit()

    # Try inserting 3 days into a 2-day roadmap
    payload = {
        "new_days": [
            {"tasks": [{"title": "T1", "order_index": 0}]},
            {"tasks": [{"title": "T2", "order_index": 0}]},
            {"tasks": [{"title": "T3", "order_index": 0}]},
        ]
    }

    ins = client.post(f"/api/v1/roadmaps/{roadmap.id}/insert", json=payload)
    assert ins.status_code == 409
    assert ins.json()["conflict_reason"] == "INSUFFICIENT_CAPACITY"
    assert test_db.query(Day).filter_by(roadmap_id=roadmap.id).count() == 0


# Validation: Duplicate task order within day rejected
def test_duplicate_task_order_rejected(client: TestClient, sample_user: User, test_db: Session):
    roadmap = Roadmap(user_id=sample_user.id, title="Test", target_duration_days=5)
    test_db.add(roadmap)
    test_db.commit()

    payload = {
        "new_days": [
            {
                "tasks": [
                    {"title": "Task 1", "order_index": 0},
                    {"title": "Task 2", "order_index": 0},  # Duplicate order_index
                ]
            }
        ]
    }

    resp = client.post(f"/api/v1/roadmaps/{roadmap.id}/insert", json=payload)
    assert resp.status_code == 422


# Validation: Nonexistent roadmap returns 404
def test_nonexistent_roadmap_returns_404(client: TestClient):
    payload = {
        "new_days": [
            {"tasks": [{"title": "Task", "order_index": 0}]}
        ]
    }
    prev = client.post("/api/v1/roadmaps/99999/insert/preview", json=payload)
    assert prev.status_code == 404

    ins = client.post("/api/v1/roadmaps/99999/insert", json=payload)
    assert ins.status_code == 404


# Fix 1: Current Day Status Verification
def test_current_day_status_transition_on_insertion(client: TestClient, sample_user: User, test_db: Session):
    roadmap = Roadmap(user_id=sample_user.id, title="Status Test", target_duration_days=10)
    test_db.add(roadmap)
    test_db.commit()

    completed_ts = datetime(2026, 9, 15, 12, 0, 0)
    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=completed_ts)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.CURRENT)
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2, d3])
    test_db.commit()

    payload = {
        "new_days": [
            {"tasks": [{"title": "Inserted Day 2 Task", "order_index": 0}]}
        ]
    }

    resp = client.post(f"/api/v1/roadmaps/{roadmap.id}/insert", json=payload)
    assert resp.status_code == 200

    test_db.expire_all()
    days = sorted(test_db.query(Day).filter_by(roadmap_id=roadmap.id).all(), key=lambda d: d.day_number)
    assert len(days) == 4

    # 1. Completed days remain unchanged
    assert days[0].day_number == 1
    assert days[0].status == DayStatus.COMPLETED
    assert days[0].completed_at == completed_ts

    # 2. Newly inserted first day is CURRENT
    assert days[1].day_number == 2
    assert days[1].status == DayStatus.CURRENT

    # 3. Old CURRENT day (previously Day 2) is shifted to Day 3 and changed to LOCKED
    assert days[2].day_number == 3
    assert days[2].id == d2.id
    assert days[2].status == DayStatus.LOCKED

    # 4. Old Day 3 shifted to Day 4 remains LOCKED
    assert days[3].day_number == 4
    assert days[3].id == d3.id
    assert days[3].status == DayStatus.LOCKED

    # 5. Exactly one CURRENT day exists in the entire roadmap
    current_days = [d for d in days if d.status == DayStatus.CURRENT]
    assert len(current_days) == 1
    assert current_days[0].day_number == 2


# Fix 2: Explicit Transaction Rollback Verification
def test_insertion_rollback_leaves_no_partial_shifts(sample_user: User, test_db: Session, monkeypatch):
    roadmap = Roadmap(user_id=sample_user.id, title="Rollback Test", target_duration_days=10)
    test_db.add(roadmap)
    test_db.commit()

    completed_ts = datetime(2026, 9, 15, 12, 0, 0)
    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=completed_ts)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.CURRENT)
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2, d3])
    test_db.commit()

    from backend.app.schemas.insertion import RoadmapInsertionRequest, NewDayDefinition, NewTaskDefinition
    request = RoadmapInsertionRequest(
        new_days=[
            NewDayDefinition(
                tasks=[NewTaskDefinition(title="Rollback Task", order_index=0)]
            )
        ]
    )

    # Monkeypatch test_db.commit to simulate an unexpected error during mutation
    def broken_commit():
        raise RuntimeError("Simulated failure during commit")

    monkeypatch.setattr(test_db, "commit", broken_commit)

    with pytest.raises(RuntimeError, match="Simulated failure during commit"):
        roadmap_engine.apply_insertion(test_db, roadmap, request)

    # Verify rollback: database state is completely preserved
    test_db.expire_all()
    days = sorted(test_db.query(Day).filter_by(roadmap_id=roadmap.id).all(), key=lambda d: d.day_number)
    assert len(days) == 3

    # Assert no negative or partially shifted day numbers exist
    assert [d.day_number for d in days] == [1, 2, 3]

    # Assert statuses and timestamps remain untouched
    assert days[0].status == DayStatus.COMPLETED
    assert days[0].completed_at == completed_ts
    assert days[1].status == DayStatus.CURRENT
    assert days[2].status == DayStatus.LOCKED

    # Assert no version or change audit records were created
    assert test_db.query(RoadmapVersion).count() == 0
    assert test_db.query(RoadmapChange).count() == 0

