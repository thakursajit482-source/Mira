from datetime import datetime, timezone, date, timedelta
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
from backend.app.models.day import Day
from backend.app.models.task import Task
from backend.app.services.progress_service import progress_service


@pytest.fixture
def db_session():
    """Create in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client(db_session: Session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def base_user(db_session: Session):
    user = User(email="momentum_test@mira.test", username="momentum_user", daily_available_minutes=60)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# 1. Empty roadmap progress
def test_empty_roadmap_progress(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Empty Roadmap", target_duration_days=5)
    db_session.add(roadmap)
    db_session.commit()
    db_session.refresh(roadmap)

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id)
    assert res.completion.total_days == 0
    assert res.completion.completed_days == 0
    assert res.completion.percentage == 0.0
    assert res.tasks.total_tasks == 0
    assert res.time.total_planned_minutes is None
    assert res.streak.current_days == 0
    assert res.streak.best_days == 0
    assert res.momentum.status == "STEADY"


# 2. Partial roadmap progress
def test_partial_roadmap_progress(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Partial Roadmap", target_duration_days=4)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc))
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.CURRENT)
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.LOCKED)
    d4 = Day(roadmap_id=roadmap.id, day_number=4, status=DayStatus.LOCKED)
    db_session.add_all([d1, d2, d3, d4])
    db_session.commit()

    t1 = Task(day_id=d1.id, title="Task 1", estimated_minutes=30, is_completed=True, completed_at=datetime(2026, 9, 20, 9, 30, tzinfo=timezone.utc))
    t2 = Task(day_id=d2.id, title="Task 2", estimated_minutes=45, is_completed=False)
    db_session.add_all([t1, t2])
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 21))
    assert res.completion.total_days == 4
    assert res.completion.completed_days == 1
    assert res.completion.remaining_days == 3
    assert res.completion.percentage == 25.0


# 3. Fully completed roadmap
def test_fully_completed_roadmap(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Completed Roadmap", target_duration_days=2)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc))
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 21, 11, 0, tzinfo=timezone.utc))
    db_session.add_all([d1, d2])
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=20, is_completed=True, completed_at=datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc))
    t2 = Task(day_id=d2.id, title="T2", estimated_minutes=20, is_completed=True, completed_at=datetime(2026, 9, 21, 10, 0, tzinfo=timezone.utc))
    db_session.add_all([t1, t2])
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 21))
    assert res.completion.total_days == 2
    assert res.completion.completed_days == 2
    assert res.completion.remaining_days == 0
    assert res.completion.percentage == 100.0
    assert res.momentum.status == "COMPLETE"
    assert res.milestones[-1].id == "roadmap_completed"
    assert res.milestones[-1].achieved is True


# 4. Task completion percentage
def test_task_completion_percentage(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Tasks Percentage", target_duration_days=1)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    db_session.add(d1)
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=15, is_completed=True, order_index=1, completed_at=datetime(2026, 9, 21, 8, 0, tzinfo=timezone.utc))
    t2 = Task(day_id=d1.id, title="T2", estimated_minutes=15, is_completed=True, order_index=2, completed_at=datetime(2026, 9, 21, 8, 30, tzinfo=timezone.utc))
    t3 = Task(day_id=d1.id, title="T3", estimated_minutes=15, is_completed=False, order_index=3)
    t4 = Task(day_id=d1.id, title="T4", estimated_minutes=15, is_completed=False, order_index=4)
    db_session.add_all([t1, t2, t3, t4])
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 21))
    assert res.tasks.total_tasks == 4
    assert res.tasks.completed_tasks == 2
    assert res.tasks.remaining_tasks == 2
    assert res.tasks.percentage == 50.0


# 5. Time progress calculation
def test_time_progress_calculation(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Time Progress", target_duration_days=1)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    db_session.add(d1)
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=40, is_completed=True, order_index=1, completed_at=datetime(2026, 9, 21, 8, 0, tzinfo=timezone.utc))
    t2 = Task(day_id=d1.id, title="T2", estimated_minutes=60, is_completed=False, order_index=2)
    db_session.add_all([t1, t2])
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 21))
    assert res.time.total_planned_minutes == 100
    assert res.time.completed_minutes == 40
    assert res.time.remaining_minutes == 60
    assert res.time.percentage == 40.0


# 6. First productive day
def test_first_productive_day(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="First Productive Day", target_duration_days=2)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    db_session.add(d1)
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=20, is_completed=True, completed_at=datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc))
    db_session.add(t1)
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 20))
    assert res.streak.last_productive_date == date(2026, 9, 20)
    assert res.streak.current_days == 1
    assert res.streak.best_days == 1


# 7. Current streak calculation
def test_current_streak(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Streak 3", target_duration_days=5)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED)
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.COMPLETED)
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.CURRENT)
    db_session.add_all([d1, d2, d3])
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=15, is_completed=True, completed_at=datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc))
    t2 = Task(day_id=d2.id, title="T2", estimated_minutes=15, is_completed=True, completed_at=datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc))
    t3 = Task(day_id=d3.id, title="T3", estimated_minutes=15, is_completed=True, completed_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc))
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    # When reference_date is 2026-09-20 (today), streak is 3
    res_today = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 20))
    assert res_today.streak.current_days == 3

    # When reference_date is 2026-09-21 (next day, not yet completed), streak is preserved as 3
    res_next_day = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 21))
    assert res_next_day.streak.current_days == 3


# 8. Broken streak
def test_broken_streak(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Broken Streak", target_duration_days=5)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED)
    db_session.add(d1)
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=15, is_completed=True, completed_at=datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc))
    db_session.add(t1)
    db_session.commit()

    # If reference_date is 2026-09-20 (>1 day since last productive date 9-15), streak breaks to 0
    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 20))
    assert res.streak.current_days == 0
    assert res.streak.best_days == 1


# 9. Best streak preserved across gaps
def test_best_streak_preserved(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Best Streak", target_duration_days=10)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED)
    db_session.add(d1)
    db_session.commit()

    # 4 consecutive days in early September
    for i, d in enumerate([1, 2, 3, 4]):
        t = Task(day_id=d1.id, title=f"T{i}", estimated_minutes=10, is_completed=True, order_index=i+1, completed_at=datetime(2026, 9, d, 10, 0, tzinfo=timezone.utc))
        db_session.add(t)

    # Gap of several days, then 1 day on Sept 20
    t_recent = Task(day_id=d1.id, title="T_recent", estimated_minutes=10, is_completed=True, order_index=10, completed_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc))
    db_session.add(t_recent)
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 20))
    assert res.streak.current_days == 1
    assert res.streak.best_days == 4


# 10. No productive activity
def test_no_productive_activity(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="No Activity", target_duration_days=3)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    db_session.add(d1)
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=10, is_completed=False)
    db_session.add(t1)
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 20))
    assert res.streak.current_days == 0
    assert res.streak.best_days == 0
    assert res.streak.last_productive_date is None
    assert res.momentum.status == "STEADY"


# 11. Milestone achievement (First Task & First Day)
def test_first_task_and_first_day_milestones(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Milestones 1", target_duration_days=5)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc))
    db_session.add(d1)
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=10, is_completed=True, completed_at=datetime(2026, 9, 15, 11, 30, tzinfo=timezone.utc))
    db_session.add(t1)
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 15))
    m_dict = {m.id: m for m in res.milestones}
    assert m_dict["first_task"].achieved is True
    assert m_dict["first_task"].achieved_at.replace(tzinfo=None) == datetime(2026, 9, 15, 11, 30)
    assert m_dict["first_day"].achieved is True


# 12. 25% milestone
def test_milestone_25_percent(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="25% Milestone", target_duration_days=4)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc))
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.CURRENT)
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.LOCKED)
    d4 = Day(roadmap_id=roadmap.id, day_number=4, status=DayStatus.LOCKED)
    db_session.add_all([d1, d2, d3, d4])
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=10, is_completed=True, completed_at=datetime(2026, 9, 16, 11, 0, tzinfo=timezone.utc))
    db_session.add(t1)
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 16))
    m_dict = {m.id: m for m in res.milestones}
    assert m_dict["roadmap_25"].achieved is True
    assert m_dict["roadmap_50"].achieved is False


# 13. 50% milestone
def test_milestone_50_percent(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="50% Milestone", target_duration_days=4)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc))
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc))
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.CURRENT)
    d4 = Day(roadmap_id=roadmap.id, day_number=4, status=DayStatus.LOCKED)
    db_session.add_all([d1, d2, d3, d4])
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=10, is_completed=True, completed_at=datetime(2026, 9, 16, 11, 0, tzinfo=timezone.utc))
    t2 = Task(day_id=d2.id, title="T2", estimated_minutes=10, is_completed=True, completed_at=datetime(2026, 9, 17, 11, 0, tzinfo=timezone.utc))
    db_session.add_all([t1, t2])
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 17))
    m_dict = {m.id: m for m in res.milestones}
    assert m_dict["roadmap_50"].achieved is True
    assert m_dict["roadmap_75"].achieved is False


# 14. 75% milestone
def test_milestone_75_percent(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="75% Milestone", target_duration_days=4)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc))
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc))
    d3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc))
    d4 = Day(roadmap_id=roadmap.id, day_number=4, status=DayStatus.CURRENT)
    db_session.add_all([d1, d2, d3, d4])
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=10, is_completed=True, completed_at=datetime(2026, 9, 16, 11, 0, tzinfo=timezone.utc))
    t2 = Task(day_id=d2.id, title="T2", estimated_minutes=10, is_completed=True, completed_at=datetime(2026, 9, 17, 11, 0, tzinfo=timezone.utc))
    t3 = Task(day_id=d3.id, title="T3", estimated_minutes=10, is_completed=True, completed_at=datetime(2026, 9, 18, 11, 0, tzinfo=timezone.utc))
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 18))
    m_dict = {m.id: m for m in res.milestones}
    assert m_dict["roadmap_75"].achieved is True
    assert m_dict["roadmap_completed"].achieved is False


# 15. Full completion milestone
def test_full_completion_milestone(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="100% Milestone", target_duration_days=2)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc))
    d2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc))
    db_session.add_all([d1, d2])
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=10, is_completed=True, completed_at=datetime(2026, 9, 16, 11, 0, tzinfo=timezone.utc))
    t2 = Task(day_id=d2.id, title="T2", estimated_minutes=10, is_completed=True, completed_at=datetime(2026, 9, 17, 11, 0, tzinfo=timezone.utc))
    db_session.add_all([t1, t2])
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 17))
    m_dict = {m.id: m for m in res.milestones}
    assert m_dict["roadmap_completed"].achieved is True


# 16. Recent activity ordering
def test_recent_activity_ordering(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Recent Activity", target_duration_days=2)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc))
    db_session.add(d1)
    db_session.commit()

    t1 = Task(day_id=d1.id, title="Early Task", estimated_minutes=10, is_completed=True, order_index=1, completed_at=datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc))
    t2 = Task(day_id=d1.id, title="Later Task", estimated_minutes=10, is_completed=True, order_index=2, completed_at=datetime(2026, 9, 18, 11, 0, tzinfo=timezone.utc))
    db_session.add_all([t1, t2])
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 18))
    activities = res.recent_activity
    assert len(activities) >= 2
    # Verify sorted newest first
    for i in range(len(activities) - 1):
        assert activities[i].timestamp >= activities[i + 1].timestamp


# 17. Momentum BUILDING
def test_momentum_building(db_session: Session, base_user: User):
    # 2 tasks completed in recent week (Sept 14-20), 0 in preceding week (Sept 7-13)
    roadmap = Roadmap(user_id=base_user.id, title="Building", target_duration_days=5)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    db_session.add(d1)
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=10, is_completed=True, order_index=1, completed_at=datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc))
    t2 = Task(day_id=d1.id, title="T2", estimated_minutes=10, is_completed=True, order_index=2, completed_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc))
    t3 = Task(day_id=d1.id, title="T3", estimated_minutes=10, is_completed=False, order_index=3)
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 20))
    assert res.momentum.status == "BUILDING"


# 18. Momentum STEADY
def test_momentum_steady(db_session: Session, base_user: User):
    # 2 tasks in recent week (Sept 14-20), 2 tasks in preceding week (Sept 7-13)
    roadmap = Roadmap(user_id=base_user.id, title="Steady", target_duration_days=5)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    db_session.add(d1)
    db_session.commit()

    t_prev1 = Task(day_id=d1.id, title="TP1", estimated_minutes=10, is_completed=True, order_index=1, completed_at=datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc))
    t_prev2 = Task(day_id=d1.id, title="TP2", estimated_minutes=10, is_completed=True, order_index=2, completed_at=datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc))
    t_rec1 = Task(day_id=d1.id, title="TR1", estimated_minutes=10, is_completed=True, order_index=3, completed_at=datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc))
    t_rec2 = Task(day_id=d1.id, title="TR2", estimated_minutes=10, is_completed=True, order_index=4, completed_at=datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc))
    t_inc = Task(day_id=d1.id, title="TInc", estimated_minutes=10, is_completed=False, order_index=5)
    db_session.add_all([t_prev1, t_prev2, t_rec1, t_rec2, t_inc])
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 20))
    assert res.momentum.status == "STEADY"


# 19. Momentum SLOWING
def test_momentum_slowing(db_session: Session, base_user: User):
    # 3 tasks in preceding week (Sept 7-13), 1 task in recent week (Sept 14-20)
    roadmap = Roadmap(user_id=base_user.id, title="Slowing", target_duration_days=5)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    db_session.add(d1)
    db_session.commit()

    t_prev1 = Task(day_id=d1.id, title="TP1", estimated_minutes=10, is_completed=True, order_index=1, completed_at=datetime(2026, 9, 8, 10, 0, tzinfo=timezone.utc))
    t_prev2 = Task(day_id=d1.id, title="TP2", estimated_minutes=10, is_completed=True, order_index=2, completed_at=datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc))
    t_prev3 = Task(day_id=d1.id, title="TP3", estimated_minutes=10, is_completed=True, order_index=3, completed_at=datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc))
    t_rec = Task(day_id=d1.id, title="TR", estimated_minutes=10, is_completed=True, order_index=4, completed_at=datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc))
    t_inc = Task(day_id=d1.id, title="TInc", estimated_minutes=10, is_completed=False, order_index=5)
    db_session.add_all([t_prev1, t_prev2, t_prev3, t_rec, t_inc])
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 20))
    assert res.momentum.status == "SLOWING"


# 20. Momentum PAUSED
def test_momentum_paused(db_session: Session, base_user: User):
    # Completed tasks in the past (e.g. Sept 1), but 0 in recent week (Sept 14-20)
    roadmap = Roadmap(user_id=base_user.id, title="Paused", target_duration_days=5)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    db_session.add(d1)
    db_session.commit()

    t_old = Task(day_id=d1.id, title="Old Task", estimated_minutes=10, is_completed=True, order_index=1, completed_at=datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc))
    t_inc = Task(day_id=d1.id, title="Incomplete", estimated_minutes=10, is_completed=False, order_index=2)
    db_session.add_all([t_old, t_inc])
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 20))
    assert res.momentum.status == "PAUSED"


# 21. Momentum COMPLETE
def test_momentum_complete(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Complete Momentum", target_duration_days=1)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED, completed_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc))
    db_session.add(d1)
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=10, is_completed=True, completed_at=datetime(2026, 9, 20, 9, 0, tzinfo=timezone.utc))
    db_session.add(t1)
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 20))
    assert res.momentum.status == "COMPLETE"
    assert res.momentum.label == "Roadmap Complete"


# 22. Insufficient historical data
def test_insufficient_historical_data(db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Brand New", target_duration_days=5)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    db_session.add(d1)
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=10, is_completed=False)
    db_session.add(t1)
    db_session.commit()

    res = progress_service.calculate_roadmap_momentum(db_session, roadmap.id, reference_date=date(2026, 9, 20))
    assert res.momentum.status == "STEADY"


# 23. Nonexistent roadmap returns 404
def test_nonexistent_roadmap_404(client: TestClient):
    response = client.get("/api/v1/roadmaps/999999/momentum")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# 24. Endpoint is read-only
def test_endpoint_is_read_only(client: TestClient, db_session: Session, base_user: User):
    roadmap = Roadmap(user_id=base_user.id, title="Read Only Check", target_duration_days=2)
    db_session.add(roadmap)
    db_session.commit()

    d1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    db_session.add(d1)
    db_session.commit()

    t1 = Task(day_id=d1.id, title="T1", estimated_minutes=25, is_completed=False)
    db_session.add(t1)
    db_session.commit()

    count_roadmaps_before = db_session.query(Roadmap).count()
    count_days_before = db_session.query(Day).count()
    count_tasks_before = db_session.query(Task).count()

    response = client.get(f"/api/v1/roadmaps/{roadmap.id}/momentum")
    assert response.status_code == 200

    assert db_session.query(Roadmap).count() == count_roadmaps_before
    assert db_session.query(Day).count() == count_days_before
    assert db_session.query(Task).count() == count_tasks_before
