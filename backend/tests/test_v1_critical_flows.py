import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import get_db
from backend.app.models.base import Base
from backend.app.models.user import User
from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.models.task import Task
from backend.app.models.versioning import RoadmapVersion
from backend.app.models.notification import Notification


@pytest.fixture
def qa_db():
    """Create an isolated in-memory SQLite database for critical user journey QA."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    Base.metadata.create_all(engine)
    QA_Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = QA_Session()

    # Seed test user
    user = User(
        id=1,
        username="qa_user",
        email="qa@mira.local",
        daily_available_minutes=120,
        theme="system",
        timezone="UTC",
    )
    session.add(user)
    session.commit()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client(qa_db: Session):
    def override_get_db():
        try:
            yield qa_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_critical_flows_a_through_i(client: TestClient, qa_db: Session):
    """
    Comprehensive End-to-End QA Test validating Phase 12 Critical User Journeys:
    Flow A: Home / Daily Focus
    Flow B: Roadmap View & Progress Interaction
    Flow C: AI Roadmap Generation & Validation
    Flow D: Deterministic Roadmap Insertion (History Preservation & Shift)
    Flow E: Rescheduling & Capacity Invariants
    Flow F: Momentum & Milestone Verification
    Flow G: Notifications & Reminders
    Flow H: Settings & Preferences
    Flow I: Data Export & Safe Deletion
    """

    # =========================================================================
    # FLOW C — AI ROADMAP GENERATION (Create active roadmap)
    # =========================================================================
    gen_payload = {
        "user_id": 1,
        "goal": "Master Full-Stack Engineering with FastAPI and React",
        "target_duration_days": 6,
        "daily_available_minutes": 120,
        "context": "Professional Developer",
    }

    # 1. Preview AI roadmap (must not mutate DB)
    preview_resp = client.post("/api/v1/roadmaps/generate/preview", json=gen_payload)
    assert preview_resp.status_code == 200, preview_resp.text
    preview_data = preview_resp.json()
    assert "Full-Stack" in preview_data["title"]
    assert len(preview_data["days"]) == 6
    # Verify no roadmap written yet
    assert qa_db.query(Roadmap).count() == 0

    # 2. Persist generated roadmap via deterministic service
    create_resp = client.post("/api/v1/roadmaps/generate", json=gen_payload)
    assert create_resp.status_code == 201, create_resp.text
    roadmap_data = create_resp.json()
    roadmap_id = roadmap_data["id"]
    assert "Full-Stack" in roadmap_data["title"]
    assert len(roadmap_data["days"]) == 6

    # =========================================================================
    # FLOW A — HOME / DAILY FOCUS
    # =========================================================================
    # User loads roadmap details
    detail_resp = client.get(f"/api/v1/roadmaps/{roadmap_id}/details")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["status"].lower() == "active"
    days = detail["days"]
    assert len(days) == 6
    day_1 = days[0]
    assert day_1["day_number"] == 1
    assert len(day_1["tasks"]) > 0

    # Daily workload analysis for current day
    analysis_resp = client.get(f"/api/v1/roadmaps/{roadmap_id}/daily-analysis")
    assert analysis_resp.status_code == 200
    analysis_data = analysis_resp.json()
    assert analysis_data["status"] in ("ON_TRACK", "TIGHT", "OVER_CAPACITY", "COMPLETE")
    assert analysis_data["total_minutes"] >= 0
    assert analysis_data["remaining_task_count"] >= 0

    # =========================================================================
    # FLOW B — ROADMAP PROGRESS INTERACTIONS
    # =========================================================================
    # Complete all tasks in Day 1, Day 2, and Day 3
    for d_idx in range(3):
        d = days[d_idx]
        for t in d["tasks"]:
            comp_resp = client.patch(f"/api/v1/tasks/{t['id']}/complete")
            assert comp_resp.status_code == 200
            assert comp_resp.json()["status"].lower() == "completed"

    # Refresh detail: Days 1, 2, 3 should be COMPLETED, Day 4 should be CURRENT
    detail = client.get(f"/api/v1/roadmaps/{roadmap_id}/details").json()
    assert detail["days"][0]["status"].lower() == "completed"
    assert detail["days"][1]["status"].lower() == "completed"
    assert detail["days"][2]["status"].lower() == "completed"
    assert detail["days"][3]["status"].lower() in ("locked", "current", "not_started")
    assert detail["days"][3]["day_number"] == 4

    # Test task uncompletion & reversion
    test_task = detail["days"][0]["tasks"][0]
    uncomp_resp = client.patch(f"/api/v1/tasks/{test_task['id']}/uncomplete")
    assert uncomp_resp.status_code == 200
    assert uncomp_resp.json()["status"].lower() in ("not_started", "pending")
    # Re-complete to restore invariant
    client.patch(f"/api/v1/tasks/{test_task['id']}/complete")

    # =========================================================================
    # FLOW D — DETERMINISTIC ROADMAP INSERTION
    # =========================================================================
    # Expand target duration to 10 days to accommodate insertion of 2 new days
    patch_resp = client.patch(f"/api/v1/roadmaps/{roadmap_id}", json={"target_duration_days": 10})
    assert patch_resp.status_code == 200

    # Invariant:
    # Days 1..3 are completed. Days 4..6 are incomplete.
    # Inserting 2 days must insert at Day 4, shifting old 4..6 to 6..8.
    # Completed Days 1..3 must remain untouched.
    insert_payload = {
        "new_days": [
            {
                "tasks": [
                    {"title": "New Inserted Day A Task", "order_index": 0, "estimated_minutes": 45}
                ]
            },
            {
                "tasks": [
                    {"title": "New Inserted Day B Task", "order_index": 0, "estimated_minutes": 50}
                ]
            },
        ],
        "metadata": {"source": "Advanced Electives"},
    }

    # Insertion preview (read-only)
    preview_ins = client.post(f"/api/v1/roadmaps/{roadmap_id}/insert/preview", json=insert_payload)
    assert preview_ins.status_code == 200
    preview_ins_data = preview_ins.json()
    assert preview_ins_data["inserted_days_count"] == 2
    assert preview_ins_data["shifted_days_count"] == 3

    # Execute insertion
    apply_ins = client.post(f"/api/v1/roadmaps/{roadmap_id}/insert", json=insert_payload)
    assert apply_ins.status_code == 200
    inserted_result = apply_ins.json()
    assert inserted_result["status"] == "SUCCESS"
    assert inserted_result["conflict"] is False
    assert inserted_result["inserted_days_count"] == 2
    assert inserted_result["first_incomplete_day"] == 4

    # Fetch updated details
    updated_details = client.get(f"/api/v1/roadmaps/{roadmap_id}/details").json()
    assert len(updated_details["days"]) == 8

    # Verify history invariant: Days 1..3 remain COMPLETED
    assert updated_details["days"][0]["day_number"] == 1
    assert updated_details["days"][0]["status"].lower() == "completed"
    assert updated_details["days"][1]["day_number"] == 2
    assert updated_details["days"][1]["status"].lower() == "completed"
    assert updated_details["days"][2]["day_number"] == 3
    assert updated_details["days"][2]["status"].lower() == "completed"

    # Verify Days 4 & 5 are the newly inserted days
    assert updated_details["days"][3]["day_number"] == 4
    assert updated_details["days"][3]["tasks"][0]["title"] == "New Inserted Day A Task"
    assert updated_details["days"][4]["day_number"] == 5
    assert updated_details["days"][4]["tasks"][0]["title"] == "New Inserted Day B Task"

    # =========================================================================
    # FLOW E — RESCHEDULING & CAPACITY ANALYSIS
    # =========================================================================
    resched_payload = {
        "daily_available_minutes": 120,
    }

    # Reschedule preview
    resched_prev = client.post(f"/api/v1/roadmaps/{roadmap_id}/reschedule/preview", json=resched_payload)
    assert resched_prev.status_code == 200
    resched_prev_data = resched_prev.json()
    assert resched_prev_data["status"] == "SUCCESS"
    assert "workload_comparison" in resched_prev_data

    # Apply reschedule
    resched_apply = client.post(f"/api/v1/roadmaps/{roadmap_id}/reschedule", json=resched_payload)
    assert resched_apply.status_code == 200
    resched_data = resched_apply.json()
    assert resched_data["status"] == "SUCCESS"
    assert resched_data["conflict"] is False

    # Check that roadmap history / versions were recorded
    hist_resp = client.get(f"/api/v1/roadmaps/{roadmap_id}/history")
    assert hist_resp.status_code == 200
    history_data = hist_resp.json()
    assert len(history_data["changes"]) >= 2  # initial AI generation + insertion + rescheduling

    # =========================================================================
    # FLOW F — MOMENTUM & METRICS
    # =========================================================================
    # Progress endpoint
    prog_resp = client.get(f"/api/v1/roadmaps/{roadmap_id}/progress")
    assert prog_resp.status_code == 200
    prog = prog_resp.json()
    assert prog["completed_days"] == 3
    assert prog["total_days"] == 8
    assert prog["progress_percentage"] > 0

    # Momentum endpoint
    mom_resp = client.get(f"/api/v1/roadmaps/{roadmap_id}/momentum")
    assert mom_resp.status_code == 200
    momentum_data = mom_resp.json()
    assert "momentum" in momentum_data
    assert "streak" in momentum_data
    assert "milestones" in momentum_data
    assert momentum_data["completion"]["completed_days"] == 3

    # =========================================================================
    # FLOW G — NOTIFICATIONS & REMINDERS
    # =========================================================================
    # Check notification list & unread count
    notif_list_resp = client.get("/api/v1/notifications?user_id=1")
    assert notif_list_resp.status_code == 200
    notif_data = notif_list_resp.json()
    assert "unread_count" in notif_data
    assert "notifications" in notif_data

    if notif_data["notifications"]:
        target_notif_id = notif_data["notifications"][0]["id"]
        # Mark as read
        read_resp = client.patch(f"/api/v1/notifications/{target_notif_id}/read")
        assert read_resp.status_code == 200
        assert read_resp.json()["read"] is True

    # Mark all read
    all_read_resp = client.patch("/api/v1/notifications/read-all?user_id=1")
    assert all_read_resp.status_code == 200

    # Notification preferences
    pref_patch = {
        "notifications_enabled": True,
        "daily_reminder_enabled": True,
        "daily_reminder_time": "20:00",
        "timezone": "America/New_York",
    }
    notif_pref_resp = client.patch("/api/v1/notifications/preferences?user_id=1", json=pref_patch)
    assert notif_pref_resp.status_code == 200
    assert notif_pref_resp.json()["daily_reminder_time"] == "20:00"

    # =========================================================================
    # FLOW H — SETTINGS & PREFERENCES
    # =========================================================================
    user_prefs_resp = client.get("/api/v1/users/preferences?user_id=1")
    assert user_prefs_resp.status_code == 200
    prefs_data = user_prefs_resp.json()
    assert prefs_data["username"] == "qa_user"

    # Update capacity to 90 min, theme to dark, ask_before_reschedule to False
    update_user_prefs = {
        "daily_available_minutes": 90,
        "theme": "dark",
        "ask_before_reschedule": False,
    }
    update_resp = client.patch("/api/v1/users/preferences?user_id=1", json=update_user_prefs)
    assert update_resp.status_code == 200
    updated_prefs = update_resp.json()
    assert updated_prefs["daily_available_minutes"] == 90
    assert updated_prefs["theme"] == "dark"
    assert updated_prefs["ask_before_reschedule"] is False

    # =========================================================================
    # FLOW I — DATA EXPORT & SAFE DELETION
    # =========================================================================
    # Export roadmap data
    export_resp = client.get(f"/api/v1/roadmaps/{roadmap_id}/export")
    assert export_resp.status_code == 200
    export_data = export_resp.json()
    assert export_data["roadmap"]["id"] == roadmap_id
    assert "Full-Stack" in export_data["roadmap"]["title"]
    assert len(export_data["days"]) == 8
    assert len(export_data["history"]) >= 2

    # Safe delete roadmap
    del_resp = client.delete(f"/api/v1/roadmaps/{roadmap_id}")
    assert del_resp.status_code == 204

    # Verify roadmap no longer exists
    assert client.get(f"/api/v1/roadmaps/{roadmap_id}").status_code == 404
    assert qa_db.query(Roadmap).filter_by(id=roadmap_id).first() is None
    assert qa_db.query(Day).filter_by(roadmap_id=roadmap_id).count() == 0
    assert qa_db.query(RoadmapVersion).filter_by(roadmap_id=roadmap_id).count() == 0
