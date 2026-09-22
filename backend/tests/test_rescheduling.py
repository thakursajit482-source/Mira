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
from backend.app.schemas.rescheduling import RoadmapRescheduleRequest
from backend.app.roadmap_engine.rescheduler import rescheduling_engine


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
    user = User(email="reschedule_user@example.com", username="reschedule_user", daily_available_minutes=120)
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


# 1. Rescheduling distributes incomplete tasks across future days
# 5. Task identity remains unchanged
# 6. Daily capacity is respected when possible
# 7. Missed/incomplete future work can be redistributed
# 17. Fixed target_duration_days remains unchanged
def test_reschedule_distributes_incomplete_tasks_respecting_capacity(
    client: TestClient, sample_user: User, test_db: Session
):
    roadmap = Roadmap(user_id=sample_user.id, title="5-day plan", target_duration_days=5)
    test_db.add(roadmap)
    test_db.commit()

    completed_ts = datetime(2026, 9, 10, 10, 0, 0)
    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=completed_ts)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.CURRENT)
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.LOCKED)
    d4 = Day(roadmap_id=roadmap.id, day_number=4, status=DayStatus.LOCKED)
    d5 = Day(roadmap_id=roadmap.id, day_number=5, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2, d3, d4, d5])
    test_db.commit()

    # Day 1 has completed tasks
    t1 = Task(day_id=d1.id, title="Completed Task 1", order_index=0, estimated_minutes=60, status=TaskStatus.COMPLETED, is_completed=True)
    # Day 2 is overloaded with 4 tasks of 60 mins each = 240 mins (capacity is 120 mins)
    t2a = Task(day_id=d2.id, title="Task 2A", order_index=0, estimated_minutes=60, status=TaskStatus.PENDING, is_completed=False)
    t2b = Task(day_id=d2.id, title="Task 2B", order_index=1, estimated_minutes=60, status=TaskStatus.PENDING, is_completed=False)
    t2c = Task(day_id=d2.id, title="Task 2C", order_index=2, estimated_minutes=60, status=TaskStatus.PENDING, is_completed=False)
    t2d = Task(day_id=d2.id, title="Task 2D", order_index=3, estimated_minutes=60, status=TaskStatus.PENDING, is_completed=False)
    test_db.add_all([t1, t2a, t2b, t2c, t2d])
    test_db.commit()

    # Apply reschedule
    resp = client.post(f"/api/v1/roadmaps/{roadmap.id}/reschedule", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["conflict"] is False
    assert data["target_duration_days"] == 5
    assert data["daily_capacity_minutes"] == 120
    assert data["moved_tasks_count"] == 2  # 2 tasks stay on Day 2, 2 tasks move to Day 3

    # Verify task identity preserved
    test_db.expire_all()
    reloaded_t2a = test_db.get(Task, t2a.id)
    reloaded_t2b = test_db.get(Task, t2b.id)
    reloaded_t2c = test_db.get(Task, t2c.id)
    reloaded_t2d = test_db.get(Task, t2d.id)

    assert reloaded_t2a.day_id == d2.id
    assert reloaded_t2b.day_id == d2.id
    assert reloaded_t2c.day_id == d3.id  # Moved to Day 3
    assert reloaded_t2d.day_id == d3.id  # Moved to Day 3

    # Check workload comparison
    comp = data["workload_comparison"]
    assert comp is not None
    # Before: Day 2 had 240 mins (is_overloaded=True)
    before_d2 = next(w for w in comp["before"] if w["day_number"] == 2)
    assert before_d2["total_estimated_minutes"] == 240
    assert before_d2["is_overloaded"] is True

    # After: Day 2 has 120 mins, Day 3 has 120 mins (neither is overloaded)
    after_d2 = next(w for w in comp["after"] if w["day_number"] == 2)
    after_d3 = next(w for w in comp["after"] if w["day_number"] == 3)
    assert after_d2["total_estimated_minutes"] == 120
    assert after_d2["is_overloaded"] is False
    assert after_d3["total_estimated_minutes"] == 120
    assert after_d3["is_overloaded"] is False


# 2. Completed tasks are never moved
# 3. Completed days are never modified
# 4. Partially completed days preserve completed tasks
# 14. No duplicate CURRENT days
def test_completed_history_and_partially_completed_days_immutable(
    client: TestClient, sample_user: User, test_db: Session
):
    roadmap = Roadmap(user_id=sample_user.id, title="Partial Day Test", target_duration_days=4)
    test_db.add(roadmap)
    test_db.commit()

    completed_ts_1 = datetime(2026, 9, 1, 10, 0, 0)
    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=completed_ts_1)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.IN_PROGRESS)
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.LOCKED)
    d4 = Day(roadmap_id=roadmap.id, day_number=4, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2, d3, d4])
    test_db.commit()

    # Day 1: completed task
    t1 = Task(day_id=d1.id, title="Day 1 Complete", order_index=0, estimated_minutes=90, status=TaskStatus.COMPLETED, is_completed=True)
    # Day 2: 1 completed task (60 mins) and 2 incomplete tasks (60 mins each)
    t2_done = Task(day_id=d2.id, title="Day 2 Done", order_index=0, estimated_minutes=60, status=TaskStatus.COMPLETED, is_completed=True)
    t2_pend1 = Task(day_id=d2.id, title="Day 2 Pend 1", order_index=1, estimated_minutes=60, status=TaskStatus.PENDING, is_completed=False)
    t2_pend2 = Task(day_id=d2.id, title="Day 2 Pend 2", order_index=2, estimated_minutes=60, status=TaskStatus.PENDING, is_completed=False)
    test_db.add_all([t1, t2_done, t2_pend1, t2_pend2])
    test_db.commit()

    resp = client.post(f"/api/v1/roadmaps/{roadmap.id}/reschedule", json={})
    assert resp.status_code == 200

    test_db.expire_all()
    # 1. Day 1 is completely untouched
    d1_reloaded = test_db.get(Day, d1.id)
    assert d1_reloaded.status == DayStatus.COMPLETED
    assert d1_reloaded.completed_at == completed_ts_1
    t1_reloaded = test_db.get(Task, t1.id)
    assert t1_reloaded.day_id == d1.id
    assert t1_reloaded.is_completed is True

    # 2. Day 2: completed task remains on Day 2
    t2_done_reloaded = test_db.get(Task, t2_done.id)
    assert t2_done_reloaded.day_id == d2.id
    assert t2_done_reloaded.is_completed is True

    # 3. Day 2 has 60 min used by t2_done. Remaining capacity is 60 min.
    # So t2_pend1 (60 min) fits on Day 2. t2_pend2 (60 min) moves to Day 3.
    t2_pend1_reloaded = test_db.get(Task, t2_pend1.id)
    t2_pend2_reloaded = test_db.get(Task, t2_pend2.id)
    assert t2_pend1_reloaded.day_id == d2.id
    assert t2_pend2_reloaded.day_id == d3.id

    # 4. Status invariant: Day 2 has completed task -> IN_PROGRESS. Days 3 and 4 -> LOCKED.
    d2_reloaded = test_db.get(Day, d2.id)
    d3_reloaded = test_db.get(Day, d3.id)
    d4_reloaded = test_db.get(Day, d4.id)
    assert d2_reloaded.status == DayStatus.IN_PROGRESS
    assert d3_reloaded.status == DayStatus.LOCKED
    assert d4_reloaded.status == DayStatus.LOCKED

    # No duplicate CURRENT days
    days = test_db.query(Day).filter_by(roadmap_id=roadmap.id).all()
    current_days = [d for d in days if d.status == DayStatus.CURRENT]
    assert len(current_days) == 0  # Day 2 is IN_PROGRESS


# 8. Insufficient capacity produces a conflict
# 9. Conflict produces zero database mutation
def test_insufficient_capacity_produces_conflict_and_zero_db_mutation(
    client: TestClient, sample_user: User, test_db: Session
):
    roadmap = Roadmap(user_id=sample_user.id, title="Tight Schedule", target_duration_days=3)
    test_db.add(roadmap)
    test_db.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.CURRENT)
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2, d3])
    test_db.commit()

    # Days 2 and 3 available = 2 * 120 mins = 240 mins capacity.
    # Add 5 tasks of 60 mins each = 300 mins (> 240 mins)
    for i in range(5):
        test_db.add(Task(day_id=d2.id, title=f"Task {i}", order_index=i, estimated_minutes=60))
    test_db.commit()

    # 1. Preview detects conflict
    prev = client.post(f"/api/v1/roadmaps/{roadmap.id}/reschedule/preview", json={}).json()
    assert prev["status"] == "CONFLICT"
    assert prev["conflict"] is True
    assert prev["conflict_reason"] == "INSUFFICIENT_CAPACITY"

    # 2. Reschedule returns 409 Conflict
    resp = client.post(f"/api/v1/roadmaps/{roadmap.id}/reschedule", json={})
    assert resp.status_code == 409
    data = resp.json()
    assert data["status"] == "CONFLICT"
    assert data["conflict"] is True
    assert data["conflict_reason"] == "INSUFFICIENT_CAPACITY"

    # 3. Database is completely unmutated
    test_db.expire_all()
    tasks_d2 = test_db.query(Task).filter_by(day_id=d2.id).all()
    assert len(tasks_d2) == 5
    assert test_db.query(Task).filter_by(day_id=d3.id).count() == 0
    assert test_db.query(RoadmapVersion).count() == 0
    assert test_db.query(RoadmapChange).count() == 0


# 10. Preview produces zero database mutation
def test_preview_produces_zero_database_mutation(
    client: TestClient, sample_user: User, test_db: Session
):
    roadmap = Roadmap(user_id=sample_user.id, title="Preview Test", target_duration_days=5)
    test_db.add(roadmap)
    test_db.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2])
    test_db.commit()

    # Add 3 tasks of 60 mins to Day 1 (180 mins > 120 mins capacity)
    for i in range(3):
        test_db.add(Task(day_id=d1.id, title=f"Task {i}", order_index=i, estimated_minutes=60))
    test_db.commit()

    resp = client.post(f"/api/v1/roadmaps/{roadmap.id}/reschedule/preview", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["conflict"] is False
    assert len(data["task_movements"]) == 1  # Third task proposed to move to Day 2

    # Assert zero DB mutation
    test_db.expire_all()
    tasks_d1 = test_db.query(Task).filter_by(day_id=d1.id).all()
    assert len(tasks_d1) == 3
    assert test_db.query(Task).filter_by(day_id=d2.id).count() == 0
    assert test_db.query(RoadmapVersion).count() == 0
    assert test_db.query(RoadmapChange).count() == 0


# 11. Successful rescheduling creates RoadmapVersion
# 12. Successful rescheduling creates RoadmapChange
def test_successful_rescheduling_creates_version_and_audit_change(
    client: TestClient, sample_user: User, test_db: Session
):
    roadmap = Roadmap(user_id=sample_user.id, title="Audit Test", target_duration_days=4)
    test_db.add(roadmap)
    test_db.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2])
    test_db.commit()

    t1 = Task(day_id=d1.id, title="T1", order_index=0, estimated_minutes=80)
    t2 = Task(day_id=d1.id, title="T2", order_index=1, estimated_minutes=80)
    test_db.add_all([t1, t2])
    test_db.commit()

    resp = client.post(f"/api/v1/roadmaps/{roadmap.id}/reschedule", json={"metadata": {"reason": "Overload"}})
    assert resp.status_code == 200

    # Verify RoadmapVersion
    versions = test_db.query(RoadmapVersion).filter_by(roadmap_id=roadmap.id).all()
    assert len(versions) == 1
    assert versions[0].version_number == 1
    assert "Rescheduled 1 tasks" in versions[0].change_summary
    assert "days" in versions[0].snapshot_data

    # Verify RoadmapChange
    changes = test_db.query(RoadmapChange).filter_by(roadmap_id=roadmap.id).all()
    assert len(changes) == 1
    assert changes[0].change_type == RoadmapChangeType.WORKLOAD_REBALANCE
    assert changes[0].version_id == versions[0].id
    assert changes[0].metadata_info["user_metadata"] == {"reason": "Overload"}


# 13. Rollback leaves no partial task movements
def test_reschedule_rollback_leaves_no_partial_movements(
    sample_user: User, test_db: Session, monkeypatch
):
    roadmap = Roadmap(user_id=sample_user.id, title="Rollback Test", target_duration_days=4)
    test_db.add(roadmap)
    test_db.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2])
    test_db.commit()

    t1 = Task(day_id=d1.id, title="T1", order_index=0, estimated_minutes=80)
    t2 = Task(day_id=d1.id, title="T2", order_index=1, estimated_minutes=80)
    test_db.add_all([t1, t2])
    test_db.commit()

    # Monkeypatch commit to simulate unexpected failure
    def broken_commit():
        raise RuntimeError("Simulated failure during reschedule commit")

    monkeypatch.setattr(test_db, "commit", broken_commit)

    req = RoadmapRescheduleRequest()
    with pytest.raises(RuntimeError, match="Simulated failure during reschedule commit"):
        rescheduling_engine.apply_reschedule(test_db, roadmap, sample_user, req)

    # Verify rollback: tasks retain original day_id and order_index
    test_db.expire_all()
    reloaded_t1 = test_db.get(Task, t1.id)
    reloaded_t2 = test_db.get(Task, t2.id)
    assert reloaded_t1.day_id == d1.id
    assert reloaded_t1.order_index == 0
    assert reloaded_t2.day_id == d1.id
    assert reloaded_t2.order_index == 1

    assert test_db.query(RoadmapVersion).count() == 0
    assert test_db.query(RoadmapChange).count() == 0


# 15. All-completed roadmap returns NO_MOVABLE_TASKS
def test_all_completed_roadmap_returns_no_movable_tasks(
    client: TestClient, sample_user: User, test_db: Session
):
    roadmap = Roadmap(user_id=sample_user.id, title="Finished", target_duration_days=2)
    test_db.add(roadmap)
    test_db.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.COMPLETED)
    test_db.add_all([d1, d2])
    test_db.commit()

    t1 = Task(day_id=d1.id, title="T1", order_index=0, status=TaskStatus.COMPLETED, is_completed=True)
    t2 = Task(day_id=d2.id, title="T2", order_index=0, status=TaskStatus.COMPLETED, is_completed=True)
    test_db.add_all([t1, t2])
    test_db.commit()

    prev = client.post(f"/api/v1/roadmaps/{roadmap.id}/reschedule/preview", json={}).json()
    assert prev["status"] == "CONFLICT"
    assert prev["conflict_reason"] == "NO_MOVABLE_TASKS"

    res = client.post(f"/api/v1/roadmaps/{roadmap.id}/reschedule", json={})
    assert res.status_code == 409
    assert res.json()["conflict_reason"] == "NO_MOVABLE_TASKS"


# 16. Zero-task / empty-workload edge case
def test_zero_task_empty_workload_edge_case(
    client: TestClient, sample_user: User, test_db: Session
):
    roadmap = Roadmap(user_id=sample_user.id, title="Empty", target_duration_days=3)
    test_db.add(roadmap)
    test_db.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    test_db.add(d1)
    test_db.commit()

    # No tasks exist
    res = client.post(f"/api/v1/roadmaps/{roadmap.id}/reschedule", json={})
    assert res.status_code == 409
    assert res.json()["conflict_reason"] == "NO_MOVABLE_TASKS"


# User daily available time override is transient and does NOT modify User record
def test_override_daily_available_minutes_in_request(
    client: TestClient, sample_user: User, test_db: Session
):
    # 1. Create a User with daily_available_minutes = 120 (provided by sample_user fixture)
    assert sample_user.daily_available_minutes == 120

    roadmap = Roadmap(user_id=sample_user.id, title="Transient Override Test", target_duration_days=3)
    test_db.add(roadmap)
    test_db.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.LOCKED)
    test_db.add_all([d1, d2])
    test_db.commit()

    # 2 tasks of 60 mins each = 120 mins.
    # At user's default capacity of 120 mins, both would fit on Day 1 (0 moved).
    t1 = Task(day_id=d1.id, title="Task 1", order_index=0, estimated_minutes=60)
    t2 = Task(day_id=d1.id, title="Task 2", order_index=1, estimated_minutes=60)
    test_db.add_all([t1, t2])
    test_db.commit()

    # 2. Call reschedule with transient daily_available_minutes = 60
    resp = client.post(
        f"/api/v1/roadmaps/{roadmap.id}/reschedule",
        json={"daily_available_minutes": 60},
    )
    assert resp.status_code == 200
    data = resp.json()

    # 3. Verify the rescheduling calculation uses 60 (moves Task 2 to Day 2)
    assert data["daily_capacity_minutes"] == 60
    assert data["moved_tasks_count"] == 1
    assert data["status"] == "SUCCESS"

    # 4. Verify after the operation: user.daily_available_minutes == 120 (NOT permanently modified)
    test_db.expire_all()
    reloaded_user = test_db.get(User, sample_user.id)
    assert reloaded_user.daily_available_minutes == 120

    # 5. Verify the roadmap rescheduling itself succeeded correctly
    reloaded_t1 = test_db.get(Task, t1.id)
    reloaded_t2 = test_db.get(Task, t2.id)
    assert reloaded_t1.day_id == d1.id
    assert reloaded_t2.day_id == d2.id


# Nonexistent roadmap returns 404
def test_nonexistent_roadmap_returns_404(client: TestClient):
    prev = client.post("/api/v1/roadmaps/99999/reschedule/preview", json={})
    assert prev.status_code == 404

    res = client.post("/api/v1/roadmaps/99999/reschedule", json={})
    assert res.status_code == 404
