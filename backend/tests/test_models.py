import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from backend.app.models.base import Base
from backend.app.models.enums import (
    RoadmapStatus,
    DayStatus,
    TaskStatus,
    RoadmapChangeType,
)
from backend.app.models.user import User
from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.models.task import Task
from backend.app.models.versioning import RoadmapVersion, RoadmapChange


@pytest.fixture
def db_session() -> Session:
    """Creates a fresh, isolated in-memory SQLite database session for each test."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_create_user_and_roadmap(db_session: Session):
    """Verify creating a user with an active roadmap."""
    user = User(
        email="learner@example.com",
        username="mira_user",
        daily_available_minutes=90,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.email == "learner@example.com"
    assert user.daily_available_minutes == 90

    roadmap = Roadmap(
        user_id=user.id,
        title="Full Stack Mastery",
        description="40-day intensive program",
        target_duration_days=40,
        status=RoadmapStatus.ACTIVE,
    )
    db_session.add(roadmap)
    db_session.commit()
    db_session.refresh(roadmap)

    assert roadmap.id is not None
    assert roadmap.target_duration_days == 40
    assert roadmap.status == RoadmapStatus.ACTIVE
    assert len(user.roadmaps) == 1
    assert user.roadmaps[0].title == "Full Stack Mastery"


def test_day_and_task_hierarchy(db_session: Session):
    """Verify Day contains multiple Tasks with independent completion states."""
    user = User(email="test@example.com", username="testuser")
    db_session.add(user)
    db_session.commit()

    roadmap = Roadmap(
        user_id=user.id,
        title="Python Roadmap",
        target_duration_days=10,
    )
    db_session.add(roadmap)
    db_session.commit()

    # Day 1: Completed day with 2 completed tasks
    day_1 = Day(
        roadmap_id=roadmap.id,
        day_number=1,
        status=DayStatus.COMPLETED,
        completed_at=datetime.now(timezone.utc),
    )
    db_session.add(day_1)
    db_session.commit()

    task_1 = Task(
        day_id=day_1.id,
        title="Install Python",
        estimated_minutes=30,
        order_index=0,
        status=TaskStatus.COMPLETED,
        is_completed=True,
    )
    task_2 = Task(
        day_id=day_1.id,
        title="Hello World",
        estimated_minutes=15,
        order_index=1,
        status=TaskStatus.COMPLETED,
        is_completed=True,
    )
    db_session.add_all([task_1, task_2])
    db_session.commit()

    # Day 2: In-Progress day with 1 completed, 1 pending task
    day_2 = Day(
        roadmap_id=roadmap.id,
        day_number=2,
        status=DayStatus.IN_PROGRESS,
    )
    db_session.add(day_2)
    db_session.commit()

    task_3 = Task(
        day_id=day_2.id,
        title="Variables and Data Types",
        estimated_minutes=45,
        order_index=0,
        status=TaskStatus.COMPLETED,
        is_completed=True,
    )
    task_4 = Task(
        day_id=day_2.id,
        title="Loops Exercise",
        estimated_minutes=45,
        order_index=1,
        status=TaskStatus.PENDING,
        is_completed=False,
    )
    db_session.add_all([task_3, task_4])
    db_session.commit()

    # Verify relationships & ordering
    db_session.refresh(roadmap)
    assert len(roadmap.days) == 2
    assert roadmap.days[0].day_number == 1
    assert roadmap.days[0].status == DayStatus.COMPLETED
    assert len(roadmap.days[0].tasks) == 2
    assert all(t.is_completed for t in roadmap.days[0].tasks)

    assert roadmap.days[1].day_number == 2
    assert roadmap.days[1].status == DayStatus.IN_PROGRESS
    assert len(roadmap.days[1].tasks) == 2
    assert roadmap.days[1].tasks[0].is_completed is True
    assert roadmap.days[1].tasks[1].is_completed is False


def test_unique_day_number_constraint(db_session: Session):
    """Verify that duplicate day numbers within the same roadmap are rejected."""
    user = User(email="unique_day@example.com", username="uniqueday")
    db_session.add(user)
    db_session.commit()

    roadmap = Roadmap(user_id=user.id, title="Test", target_duration_days=5)
    db_session.add(roadmap)
    db_session.commit()

    day_a = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.LOCKED)
    db_session.add(day_a)
    db_session.commit()

    day_b = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.LOCKED)
    db_session.add(day_b)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_unique_task_order_constraint(db_session: Session):
    """Verify that duplicate order_index values within the same day are rejected."""
    user = User(email="unique_task@example.com", username="uniquetask")
    db_session.add(user)
    db_session.commit()

    roadmap = Roadmap(user_id=user.id, title="Test", target_duration_days=5)
    db_session.add(roadmap)
    db_session.commit()

    day = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    db_session.add(day)
    db_session.commit()

    task_a = Task(day_id=day.id, title="Task 1", order_index=0)
    db_session.add(task_a)
    db_session.commit()

    task_b = Task(day_id=day.id, title="Task 2", order_index=0)
    db_session.add(task_b)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_versioning_and_change_history(db_session: Session):
    """Verify RoadmapVersion snapshot and RoadmapChange audit log."""
    user = User(email="audit@example.com", username="auditor")
    db_session.add(user)
    db_session.commit()

    roadmap = Roadmap(user_id=user.id, title="Versioned Roadmap", target_duration_days=20)
    db_session.add(roadmap)
    db_session.commit()

    # Create a version snapshot
    version = RoadmapVersion(
        roadmap_id=roadmap.id,
        version_number=1,
        change_summary="Initial roadmap generated",
        snapshot_data={"days": [{"day_number": 1, "tasks": ["Task A", "Task B"]}]},
    )
    db_session.add(version)
    db_session.commit()

    # Create a change log
    change = RoadmapChange(
        roadmap_id=roadmap.id,
        version_id=version.id,
        change_type=RoadmapChangeType.INITIAL_GENERATION,
        description="Generated initial 20-day plan",
        metadata_info={"source": "user_prompt", "target_days": 20},
    )
    db_session.add(change)
    db_session.commit()

    db_session.refresh(roadmap)
    assert len(roadmap.versions) == 1
    assert roadmap.versions[0].version_number == 1
    assert len(roadmap.changes) == 1
    assert roadmap.changes[0].change_type == RoadmapChangeType.INITIAL_GENERATION
    assert roadmap.changes[0].version.id == version.id


def test_cascade_deletion(db_session: Session):
    """Verify deleting a roadmap cascades to days, tasks, versions, and changes."""
    user = User(email="cascade@example.com", username="cascadetest")
    db_session.add(user)
    db_session.commit()

    roadmap = Roadmap(user_id=user.id, title="To Delete", target_duration_days=5)
    db_session.add(roadmap)
    db_session.commit()

    day = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    db_session.add(day)
    db_session.commit()

    task = Task(day_id=day.id, title="Task", order_index=0)
    version = RoadmapVersion(
        roadmap_id=roadmap.id,
        version_number=1,
        change_summary="v1",
        snapshot_data={},
    )
    change = RoadmapChange(
        roadmap_id=roadmap.id,
        change_type=RoadmapChangeType.INITIAL_GENERATION,
        description="Initial",
    )
    db_session.add_all([task, version, change])
    db_session.commit()

    # Delete roadmap
    db_session.delete(roadmap)
    db_session.commit()

    # Assert children are deleted
    assert db_session.query(Day).filter_by(roadmap_id=roadmap.id).count() == 0
    assert db_session.query(Task).filter_by(day_id=day.id).count() == 0
    assert db_session.query(RoadmapVersion).filter_by(roadmap_id=roadmap.id).count() == 0
    assert db_session.query(RoadmapChange).filter_by(roadmap_id=roadmap.id).count() == 0
    # User remains intact
    assert db_session.query(User).filter_by(id=user.id).count() == 1
