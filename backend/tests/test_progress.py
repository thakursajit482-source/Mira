import pytest
from datetime import datetime
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
def sample_hierarchy(test_db: Session):
    """
    Creates:
    - User
    - Roadmap (total_duration_days=3)
    - Day 1 with 2 tasks (Task 1.1, Task 1.2)
    - Day 2 with 1 task (Task 2.1)
    - Day 3 with 0 tasks (Empty Day)
    """
    user = User(email="progress@example.com", username="progressuser", daily_available_minutes=120)
    test_db.add(user)
    test_db.commit()

    roadmap = Roadmap(
        user_id=user.id,
        title="Progress Test Roadmap",
        target_duration_days=3,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()

    day_1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.CURRENT)
    day_2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.LOCKED)
    day_3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.LOCKED)
    test_db.add_all([day_1, day_2, day_3])
    test_db.commit()

    task_1a = Task(day_id=day_1.id, title="Task 1.1", order_index=0, estimated_minutes=30)
    task_1b = Task(day_id=day_1.id, title="Task 1.2", order_index=1, estimated_minutes=45)
    task_2a = Task(day_id=day_2.id, title="Task 2.1", order_index=0, estimated_minutes=60)
    test_db.add_all([task_1a, task_1b, task_2a])
    test_db.commit()

    return {
        "user": user,
        "roadmap": roadmap,
        "day_1": day_1,
        "day_2": day_2,
        "day_3": day_3,
        "task_1a": task_1a,
        "task_1b": task_1b,
        "task_2a": task_2a,
    }


# 1. Complete task successfully
# 5. completed_at is set correctly
def test_complete_task_success(client: TestClient, sample_hierarchy: dict):
    task = sample_hierarchy["task_1a"]
    response = client.patch(f"/api/v1/tasks/{task.id}/complete")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task.id
    assert data["status"] == "COMPLETED"
    assert data["is_completed"] is True
    assert data["completed_at"] is not None


# 2. Completing already-completed task is safe (idempotent)
def test_complete_task_idempotent(client: TestClient, sample_hierarchy: dict):
    task = sample_hierarchy["task_1a"]
    resp1 = client.patch(f"/api/v1/tasks/{task.id}/complete")
    assert resp1.status_code == 200
    completed_at_1 = resp1.json()["completed_at"]

    resp2 = client.patch(f"/api/v1/tasks/{task.id}/complete")
    assert resp2.status_code == 200
    assert resp2.json()["completed_at"] == completed_at_1
    assert resp2.json()["is_completed"] is True


# 3. Uncomplete task successfully
# 6. completed_at is cleared when uncompleted
def test_uncomplete_task_success(client: TestClient, sample_hierarchy: dict):
    task = sample_hierarchy["task_1a"]
    client.patch(f"/api/v1/tasks/{task.id}/complete")

    response = client.patch(f"/api/v1/tasks/{task.id}/uncomplete")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["is_completed"] is False
    assert data["completed_at"] is None


# 4. Uncompleting already-incomplete task is safe (idempotent)
def test_uncomplete_task_idempotent(client: TestClient, sample_hierarchy: dict):
    task = sample_hierarchy["task_1a"]
    # Task is already incomplete initially
    response = client.patch(f"/api/v1/tasks/{task.id}/uncomplete")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PENDING"
    assert data["is_completed"] is False
    assert data["completed_at"] is None


# 7. Day remains incomplete when only some tasks are complete
def test_day_remains_incomplete_when_partially_completed(client: TestClient, sample_hierarchy: dict):
    task_1a = sample_hierarchy["task_1a"]
    day_1 = sample_hierarchy["day_1"]

    client.patch(f"/api/v1/tasks/{task_1a.id}/complete")

    day_resp = client.get(f"/api/v1/days/{day_1.id}")
    assert day_resp.status_code == 200
    data = day_resp.json()
    assert data["status"] == "IN_PROGRESS"
    assert data["completed_at"] is None


# 8. Day becomes completed when all tasks are complete
# 9. Day completed_at is set
def test_day_becomes_completed_when_all_tasks_complete(client: TestClient, sample_hierarchy: dict):
    task_1a = sample_hierarchy["task_1a"]
    task_1b = sample_hierarchy["task_1b"]
    day_1 = sample_hierarchy["day_1"]

    client.patch(f"/api/v1/tasks/{task_1a.id}/complete")
    client.patch(f"/api/v1/tasks/{task_1b.id}/complete")

    day_resp = client.get(f"/api/v1/days/{day_1.id}")
    assert day_resp.status_code == 200
    data = day_resp.json()
    assert data["status"] == "COMPLETED"
    assert data["completed_at"] is not None


# 10. Day becomes incomplete when a completed task is uncompleted
# 11. Day completed_at is cleared after uncompletion
def test_day_reverts_to_incomplete_on_task_uncompletion(client: TestClient, sample_hierarchy: dict):
    task_1a = sample_hierarchy["task_1a"]
    task_1b = sample_hierarchy["task_1b"]
    day_1 = sample_hierarchy["day_1"]

    # Complete both tasks -> Day completes
    client.patch(f"/api/v1/tasks/{task_1a.id}/complete")
    client.patch(f"/api/v1/tasks/{task_1b.id}/complete")

    day_resp1 = client.get(f"/api/v1/days/{day_1.id}")
    assert day_resp1.json()["status"] == "COMPLETED"

    # Uncomplete task_1b -> Day reverts to IN_PROGRESS
    client.patch(f"/api/v1/tasks/{task_1b.id}/uncomplete")
    day_resp2 = client.get(f"/api/v1/days/{day_1.id}")
    assert day_resp2.json()["status"] == "IN_PROGRESS"
    assert day_resp2.json()["completed_at"] is None

    # Uncomplete task_1a -> Day reverts to CURRENT (0 completed tasks)
    client.patch(f"/api/v1/tasks/{task_1a.id}/uncomplete")
    day_resp3 = client.get(f"/api/v1/days/{day_1.id}")
    assert day_resp3.json()["status"] == "CURRENT"
    assert day_resp3.json()["completed_at"] is None


# 12. Empty Day does not become completed
def test_empty_day_does_not_become_completed(client: TestClient, sample_hierarchy: dict, test_db: Session):
    day_3 = sample_hierarchy["day_3"]
    # Day 3 has 0 tasks
    day_resp = client.get(f"/api/v1/days/{day_3.id}")
    assert day_resp.status_code == 200
    assert day_resp.json()["status"] != "COMPLETED"
    assert len(day_resp.json()["tasks"]) == 0


# 13. Roadmap progress is calculated correctly
# 14. Roadmap progress changes after task completion
# 15. Roadmap progress changes after task uncompletion
def test_roadmap_progress_lifecycle(client: TestClient, sample_hierarchy: dict):
    roadmap = sample_hierarchy["roadmap"]
    task_1a = sample_hierarchy["task_1a"]
    task_1b = sample_hierarchy["task_1b"]
    task_2a = sample_hierarchy["task_2a"]

    # Initially: 0 completed days out of 3 total days -> 0.0%
    prog0 = client.get(f"/api/v1/roadmaps/{roadmap.id}/progress").json()
    assert prog0["total_days"] == 3
    assert prog0["completed_days"] == 0
    assert prog0["progress_percentage"] == 0.0
    assert prog0["total_tasks"] == 3
    assert prog0["completed_tasks"] == 0

    # Complete Task 1a (Day 1 partially complete): still 0 completed days
    client.patch(f"/api/v1/tasks/{task_1a.id}/complete")
    prog1 = client.get(f"/api/v1/roadmaps/{roadmap.id}/progress").json()
    assert prog1["completed_days"] == 0
    assert prog1["completed_tasks"] == 1
    assert prog1["progress_percentage"] == 0.0

    # Complete Task 1b (Day 1 fully complete): 1 of 3 days complete -> 33.33%
    client.patch(f"/api/v1/tasks/{task_1b.id}/complete")
    prog2 = client.get(f"/api/v1/roadmaps/{roadmap.id}/progress").json()
    assert prog2["completed_days"] == 1
    assert prog2["completed_tasks"] == 2
    assert prog2["progress_percentage"] == 33.33

    # Complete Task 2a (Day 2 fully complete): 2 of 3 days complete -> 66.67%
    client.patch(f"/api/v1/tasks/{task_2a.id}/complete")
    prog3 = client.get(f"/api/v1/roadmaps/{roadmap.id}/progress").json()
    assert prog3["completed_days"] == 2
    assert prog3["completed_tasks"] == 3
    assert prog3["progress_percentage"] == 66.67

    # Uncomplete Task 1a: Day 1 becomes incomplete -> drops to 1 of 3 days -> 33.33%
    client.patch(f"/api/v1/tasks/{task_1a.id}/uncomplete")
    prog4 = client.get(f"/api/v1/roadmaps/{roadmap.id}/progress").json()
    assert prog4["completed_days"] == 1
    assert prog4["completed_tasks"] == 2
    assert prog4["progress_percentage"] == 33.33


# 16. Zero-day roadmap returns 0% progress
def test_zero_day_roadmap_progress(client: TestClient, sample_hierarchy: dict, test_db: Session):
    user = sample_hierarchy["user"]
    empty_roadmap = Roadmap(user_id=user.id, title="Empty Roadmap", target_duration_days=5)
    test_db.add(empty_roadmap)
    test_db.commit()

    resp = client.get(f"/api/v1/roadmaps/{empty_roadmap.id}/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_days"] == 0
    assert data["completed_days"] == 0
    assert data["progress_percentage"] == 0.0
    assert data["total_tasks"] == 0
    assert data["completed_tasks"] == 0


# 17. Task not found returns 404
def test_task_not_found_returns_404(client: TestClient):
    resp_get = client.get("/api/v1/tasks/99999")
    assert resp_get.status_code == 404
    assert "Task with id 99999 not found" in resp_get.json()["detail"]

    resp_comp = client.patch("/api/v1/tasks/99999/complete")
    assert resp_comp.status_code == 404

    resp_uncomp = client.patch("/api/v1/tasks/99999/uncomplete")
    assert resp_uncomp.status_code == 404


# 18. Day not found returns 404
def test_day_not_found_returns_404(client: TestClient):
    response = client.get("/api/v1/days/99999")
    assert response.status_code == 404
    assert "Day with id 99999 not found" in response.json()["detail"]


# 19. Roadmap not found returns 404
def test_roadmap_progress_not_found_returns_404(client: TestClient):
    response = client.get("/api/v1/roadmaps/99999/progress")
    assert response.status_code == 404
    assert "Roadmap with id 99999 not found" in response.json()["detail"]


# 20. Get task by ID returns all expected fields
def test_get_task_by_id(client: TestClient, sample_hierarchy: dict):
    task = sample_hierarchy["task_1a"]
    response = client.get(f"/api/v1/tasks/{task.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task.id
    assert data["day_id"] == task.day_id
    assert data["title"] == "Task 1.1"
    assert data["estimated_minutes"] == 30
    assert data["order_index"] == 0
    assert data["status"] == "PENDING"
    assert data["is_completed"] is False
    assert "created_at" in data
    assert "updated_at" in data
