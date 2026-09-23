import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import get_db
from backend.app.models.base import Base
from backend.app.models.enums import RoadmapStatus, DayStatus, TaskStatus
from backend.app.models.user import User
from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.models.task import Task


from sqlalchemy.pool import StaticPool

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
    """Helper fixture to insert a test user."""
    user = User(email="testuser@example.com", username="testuser", daily_available_minutes=120)
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


# 1. Create roadmap successfully
def test_create_roadmap_success(client: TestClient, sample_user: User):
    payload = {
        "user_id": sample_user.id,
        "title": "Learn FastAPI & SQLAlchemy",
        "description": "Master modern Python web development",
        "target_duration_days": 30,
        "start_date": "2026-10-01",
        "target_deadline": "2026-10-30",
        "status": "ACTIVE",
    }
    response = client.post("/api/v1/roadmaps", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["user_id"] == sample_user.id
    assert data["title"] == "Learn FastAPI & SQLAlchemy"
    assert data["target_duration_days"] == 30
    assert data["status"] == "ACTIVE"
    assert data["start_date"] == "2026-10-01"
    assert data["target_deadline"] == "2026-10-30"


# 2. Create roadmap with nonexistent user fails
def test_create_roadmap_nonexistent_user_fails(client: TestClient):
    payload = {
        "user_id": 99999,
        "title": "Orphan Roadmap",
        "target_duration_days": 10,
    }
    response = client.post("/api/v1/roadmaps", json=payload)
    assert response.status_code == 404
    assert "User with id 99999 not found" in response.json()["detail"]


# 3. Get roadmap successfully
def test_get_roadmap_success(client: TestClient, sample_user: User):
    create_payload = {
        "user_id": sample_user.id,
        "title": "Deep Learning Specialization",
        "target_duration_days": 60,
    }
    create_resp = client.post("/api/v1/roadmaps", json=create_payload)
    roadmap_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/roadmaps/{roadmap_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == roadmap_id
    assert data["title"] == "Deep Learning Specialization"
    assert data["target_duration_days"] == 60


# 4. Get nonexistent roadmap returns 404
def test_get_nonexistent_roadmap_returns_404(client: TestClient):
    response = client.get("/api/v1/roadmaps/99999")
    assert response.status_code == 404
    assert "Roadmap with id 99999 not found" in response.json()["detail"]


# 5. List roadmaps (including filtering by user_id)
def test_list_roadmaps(client: TestClient, sample_user: User, test_db: Session):
    # Create a second user
    user2 = User(email="second@example.com", username="seconduser")
    test_db.add(user2)
    test_db.commit()
    test_db.refresh(user2)

    client.post("/api/v1/roadmaps", json={"user_id": sample_user.id, "title": "User1 Plan 1", "target_duration_days": 10})
    client.post("/api/v1/roadmaps", json={"user_id": sample_user.id, "title": "User1 Plan 2", "target_duration_days": 20})
    client.post("/api/v1/roadmaps", json={"user_id": user2.id, "title": "User2 Plan", "target_duration_days": 15})

    # List all roadmaps
    resp_all = client.get("/api/v1/roadmaps")
    assert resp_all.status_code == 200
    assert len(resp_all.json()) == 3

    # Filter by sample_user
    resp_user1 = client.get(f"/api/v1/roadmaps?user_id={sample_user.id}")
    assert resp_user1.status_code == 200
    assert len(resp_user1.json()) == 2
    assert all(r["user_id"] == sample_user.id for r in resp_user1.json())

    # Filter by user2
    resp_user2 = client.get(f"/api/v1/roadmaps?user_id={user2.id}")
    assert resp_user2.status_code == 200
    assert len(resp_user2.json()) == 1
    assert resp_user2.json()[0]["title"] == "User2 Plan"


# 6. Update roadmap
def test_update_roadmap(client: TestClient, sample_user: User):
    create_resp = client.post("/api/v1/roadmaps", json={"user_id": sample_user.id, "title": "Initial Title", "target_duration_days": 10})
    roadmap_id = create_resp.json()["id"]

    patch_payload = {
        "title": "Updated Title",
        "description": "Added description",
        "status": "COMPLETED",
    }
    response = client.patch(f"/api/v1/roadmaps/{roadmap_id}", json=patch_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["description"] == "Added description"
    assert data["status"] == "COMPLETED"
    assert data["target_duration_days"] == 10  # Unchanged


# 7. Partial update does not overwrite unspecified fields
def test_partial_update_preserves_unspecified_fields(client: TestClient, sample_user: User):
    create_resp = client.post(
        "/api/v1/roadmaps",
        json={
            "user_id": sample_user.id,
            "title": "Full Plan",
            "description": "Original Description",
            "target_duration_days": 40,
            "start_date": "2026-10-01",
            "target_deadline": "2026-11-10",
        },
    )
    roadmap_id = create_resp.json()["id"]

    # Only update description
    patch_resp = client.patch(f"/api/v1/roadmaps/{roadmap_id}", json={"description": "New Description"})
    assert patch_resp.status_code == 200
    data = patch_resp.json()
    assert data["title"] == "Full Plan"
    assert data["description"] == "New Description"
    assert data["target_duration_days"] == 40
    assert data["start_date"] == "2026-10-01"
    assert data["target_deadline"] == "2026-11-10"


# 8. Delete roadmap
def test_delete_roadmap(client: TestClient, sample_user: User):
    create_resp = client.post("/api/v1/roadmaps", json={"user_id": sample_user.id, "title": "To Delete", "target_duration_days": 5})
    roadmap_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/roadmaps/{roadmap_id}")
    assert del_resp.status_code == 204


# 9. Deleted roadmap cannot be fetched
def test_deleted_roadmap_returns_404(client: TestClient, sample_user: User):
    create_resp = client.post("/api/v1/roadmaps", json={"user_id": sample_user.id, "title": "To Delete", "target_duration_days": 5})
    roadmap_id = create_resp.json()["id"]

    client.delete(f"/api/v1/roadmaps/{roadmap_id}")
    get_resp = client.get(f"/api/v1/roadmaps/{roadmap_id}")
    assert get_resp.status_code == 404


# 10. Get roadmap details
# 11. Details correctly return Days
# 12. Details correctly return Tasks
# 13. Days are ordered by day_number
# 14. Tasks are ordered correctly
def test_get_roadmap_details_hierarchy_and_ordering(client: TestClient, sample_user: User, test_db: Session):
    # Create roadmap via DB to attach days and tasks
    roadmap = Roadmap(
        user_id=sample_user.id,
        title="Ordered Roadmap",
        target_duration_days=3,
        status=RoadmapStatus.ACTIVE,
    )
    test_db.add(roadmap)
    test_db.commit()

    # Insert days out of order to verify sorting by day_number
    day_3 = Day(roadmap_id=roadmap.id, day_number=3, status=DayStatus.LOCKED)
    day_1 = Day(roadmap_id=roadmap.id, day_number=1, status=DayStatus.COMPLETED)
    day_2 = Day(roadmap_id=roadmap.id, day_number=2, status=DayStatus.CURRENT)
    test_db.add_all([day_3, day_1, day_2])
    test_db.commit()

    # Insert tasks out of order in Day 1 to verify sorting by order_index
    task_1b = Task(day_id=day_1.id, title="Task 1.2", order_index=1, status=TaskStatus.COMPLETED, is_completed=True)
    task_1a = Task(day_id=day_1.id, title="Task 1.1", order_index=0, status=TaskStatus.COMPLETED, is_completed=True)
    test_db.add_all([task_1b, task_1a])

    # Insert tasks in Day 2
    task_2a = Task(day_id=day_2.id, title="Task 2.1", order_index=0, status=TaskStatus.IN_PROGRESS, is_completed=False)
    test_db.add(task_2a)
    test_db.commit()

    # Fetch details via API
    response = client.get(f"/api/v1/roadmaps/{roadmap.id}/details")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == roadmap.id
    assert data["title"] == "Ordered Roadmap"

    # Verify Days exist and are strictly ordered by day_number
    days = data["days"]
    assert len(days) == 3
    assert [d["day_number"] for d in days] == [1, 2, 3]
    assert days[0]["status"] == "COMPLETED"
    assert days[1]["status"] == "CURRENT"
    assert days[2]["status"] == "LOCKED"

    # Verify Tasks in Day 1 are ordered by order_index
    day1_tasks = days[0]["tasks"]
    assert len(day1_tasks) == 2
    assert day1_tasks[0]["title"] == "Task 1.1"
    assert day1_tasks[0]["order_index"] == 0
    assert day1_tasks[1]["title"] == "Task 1.2"
    assert day1_tasks[1]["order_index"] == 1

    # Verify Tasks in Day 2
    day2_tasks = days[1]["tasks"]
    assert len(day2_tasks) == 1
    assert day2_tasks[0]["title"] == "Task 2.1"

    # Verify Day 3 has empty tasks
    assert days[2]["tasks"] == []


# 15. Invalid target_duration_days rejected (422)
def test_invalid_target_duration_rejected(client: TestClient, sample_user: User):
    payload = {
        "user_id": sample_user.id,
        "title": "Invalid Duration",
        "target_duration_days": 0,  # Must be > 0
    }
    response = client.post("/api/v1/roadmaps", json=payload)
    assert response.status_code == 422


# 16. Invalid date relationship rejected (422 or 400)
def test_invalid_date_relationship_rejected(client: TestClient, sample_user: User):
    # Deadline before start_date on create -> 422 (Pydantic validator)
    payload = {
        "user_id": sample_user.id,
        "title": "Invalid Dates",
        "target_duration_days": 10,
        "start_date": "2026-10-15",
        "target_deadline": "2026-10-10",
    }
    response = client.post("/api/v1/roadmaps", json=payload)
    assert response.status_code == 422

    # Deadline before start_date on update -> 400 or 422
    valid_create = client.post(
        "/api/v1/roadmaps",
        json={
            "user_id": sample_user.id,
            "title": "Valid Initially",
            "target_duration_days": 10,
            "start_date": "2026-10-10",
            "target_deadline": "2026-10-20",
        },
    )
    roadmap_id = valid_create.json()["id"]

    # Try updating deadline to before start_date
    patch_resp = client.patch(f"/api/v1/roadmaps/{roadmap_id}", json={"target_deadline": "2026-10-05"})
    assert patch_resp.status_code == 400
    assert "target_deadline cannot be before start_date" in patch_resp.json()["detail"]


# 17. Invalid roadmap status rejected (422)
def test_invalid_roadmap_status_rejected(client: TestClient, sample_user: User):
    payload = {
        "user_id": sample_user.id,
        "title": "Invalid Status",
        "target_duration_days": 10,
        "status": "NONEXISTENT_STATUS",
    }
    response = client.post("/api/v1/roadmaps", json=payload)
    assert response.status_code == 422


# 18. Nonexistent roadmap details returns 404
def test_get_nonexistent_roadmap_details_returns_404(client: TestClient):
    resp = client.get("/api/v1/roadmaps/99999/details")
    assert resp.status_code == 404
    assert "Roadmap with id 99999 not found" in resp.json()["detail"]


# 19. Update nonexistent roadmap returns 404
def test_update_nonexistent_roadmap_returns_404(client: TestClient):
    resp = client.patch("/api/v1/roadmaps/99999", json={"title": "Nonexistent"})
    assert resp.status_code == 404
    assert "Roadmap with id 99999 not found" in resp.json()["detail"]


# 20. Delete nonexistent roadmap returns 404
def test_delete_nonexistent_roadmap_returns_404(client: TestClient):
    resp = client.delete("/api/v1/roadmaps/99999")
    assert resp.status_code == 404
    assert "Roadmap with id 99999 not found" in resp.json()["detail"]
