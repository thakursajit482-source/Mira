"""
Regression tests for AI title normalization at the output validation boundary.

Covers the exact bug scenario:
    Provider failed to generate roadmap:
    1 validation error for GeneratedRoadmap
    title
    String should have at most 255 characters
    [type=string_too_long, ...]

The fix adds a deterministic `normalize_ai_title()` function applied via
a Pydantic field_validator(mode="before") on GeneratedRoadmap.title and
GeneratedTask.title, so oversized AI titles are silently normalized — never
causing a ValidationError or HTTP 422/500.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.core.database import get_db
from backend.app.models.base import Base
from backend.app.models.user import User
from backend.app.ai.schemas import (
    normalize_ai_title,
    GeneratedRoadmap,
    GeneratedDay,
    GeneratedTask,
    RoadmapGenerationRequest,
)
from backend.app.ai.providers.mock import MockAIProvider
from backend.app.ai.validator import AIValidator
from backend.app.ai.service import ai_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db():
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
    user = User(email="norm_user@example.com", username="norm_user", daily_available_minutes=120)
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


def _make_single_day_roadmap(title: str) -> GeneratedRoadmap:
    """Helper: build a minimal 1-day GeneratedRoadmap with a given raw title."""
    return GeneratedRoadmap(
        title=title,
        description="Test roadmap",
        target_duration_days=1,
        days=[
            GeneratedDay(
                day_number=1,
                title="Day 1",
                tasks=[GeneratedTask(title="Task 1", estimated_minutes=30, order_index=0)],
            )
        ],
    )


# ===========================================================================
# 1. Unit tests for normalize_ai_title()
# ===========================================================================

class TestNormalizeAiTitle:
    """Directly test the normalize_ai_title() pure function."""

    def test_short_title_unchanged(self):
        """Title <= 255 chars must be returned unchanged (apart from whitespace)."""
        t = "Learn Python"
        assert normalize_ai_title(t) == t

    def test_exact_255_unchanged(self):
        """Title of exactly 255 characters must pass through without modification."""
        t = "A" * 255
        result = normalize_ai_title(t)
        assert result == t
        assert len(result) == 255

    def test_title_256_is_truncated(self):
        """Title of 256 characters must be normalized to <= 255."""
        t = "A" * 256
        result = normalize_ai_title(t)
        assert len(result) <= 255

    def test_oversized_title_truncated(self):
        """Title >255 chars is normalized to <= 255 chars."""
        long_title = "Roadmap: " + "X" * 300
        result = normalize_ai_title(long_title)
        assert len(result) <= 255

    def test_oversized_title_preserves_start(self):
        """Truncated title must begin with the original prefix."""
        long_title = "Learn Python deeply " + "extra words " * 30
        result = normalize_ai_title(long_title)
        assert result.startswith("Learn Python")

    def test_word_boundary_truncation(self):
        """Truncation happens at a word boundary (no mid-word cut) when possible."""
        # Construct a title that is just over 255 with clear word boundaries
        words = ["word"] * 70          # 4 chars each + space = 5 per word → 350 chars total
        long_title = " ".join(words)
        result = normalize_ai_title(long_title)
        assert len(result) <= 255
        # Ellipsis appended means it did truncate
        assert result.endswith("…")
        # Must not end mid-word (last complete token before ellipsis ends cleanly)
        body = result[:-1]  # strip ellipsis
        assert not body.endswith(" ")

    def test_newlines_collapsed(self):
        """Newlines and tabs in title are collapsed to single spaces."""
        raw = "Roadmap: TARGET\n(PHASE 1\n— 26 Oct\n\nExce)"
        result = normalize_ai_title(raw)
        assert "\n" not in result
        assert "\t" not in result

    def test_extra_whitespace_collapsed(self):
        """Multiple consecutive spaces are collapsed to one."""
        raw = "Learn   Python   Basics"
        result = normalize_ai_title(raw)
        assert result == "Learn Python Basics"

    def test_empty_string_returns_placeholder(self):
        """An empty title produces a safe non-empty placeholder."""
        result = normalize_ai_title("")
        assert result == "Untitled Roadmap"
        assert len(result) > 0

    def test_whitespace_only_returns_placeholder(self):
        """A whitespace-only title produces a safe non-empty placeholder."""
        result = normalize_ai_title("   \n\t  ")
        assert result == "Untitled Roadmap"

    def test_extremely_long_single_token(self):
        """A single token of 1000 chars is hard-truncated to <= 255."""
        raw = "A" * 1000
        result = normalize_ai_title(raw)
        assert len(result) <= 255
        assert result.endswith("…")

    def test_exact_bug_scenario_title(self):
        """Reproduce the exact bug: title from the error message is normalized."""
        # Simulated title from the error: starts with "Roadmap: TARGET (PHASE 1... 33 — 26 Oct\n\nExce)"
        raw = (
            "Roadmap: TARGET (PHASE 1 — Learning from Day 1 to Day 33 — 26 Oct\n\n"
            "Excellence Program with comprehensive exercises and hands-on projects "
            "covering all fundamentals of modern software engineering and architecture)"
        )
        result = normalize_ai_title(raw)
        assert len(result) <= 255
        assert result.startswith("Roadmap: TARGET")
        assert "\n" not in result


# ===========================================================================
# 2. Schema-level normalization (GeneratedRoadmap field_validator)
# ===========================================================================

class TestGeneratedRoadmapTitleNormalization:
    """Verify the Pydantic field_validator normalizes titles at construction time."""

    def test_short_title_accepted_unchanged(self):
        rm = _make_single_day_roadmap("Python Basics")
        assert rm.title == "Python Basics"

    def test_exact_255_title_accepted(self):
        """A 255-char title must pass GeneratedRoadmap construction without error."""
        t = "B" * 255
        rm = _make_single_day_roadmap(t)
        assert rm.title == t
        assert len(rm.title) == 255

    def test_oversized_title_normalized_at_construction(self):
        """A title >255 chars is normalized by field_validator — no ValidationError raised."""
        long_title = "Roadmap: " + "Z" * 300
        rm = _make_single_day_roadmap(long_title)
        assert len(rm.title) <= 255

    def test_newline_in_title_normalized(self):
        """A title with embedded newlines is normalized to a single-line title."""
        raw = "Roadmap: TARGET (PHASE 1\n— 26 Oct\n\nExce)"
        rm = _make_single_day_roadmap(raw)
        assert "\n" not in rm.title
        assert len(rm.title) <= 255

    def test_normalized_title_passes_ai_validator(self):
        """After normalization, the GeneratedRoadmap must also pass AIValidator."""
        long_title = "Roadmap: " + "Y" * 500
        req = RoadmapGenerationRequest(user_id=1, goal="Learn Python", target_duration_days=1)
        rm = _make_single_day_roadmap(long_title)
        # AIValidator.validate must not raise
        AIValidator.validate(rm, req, daily_capacity=120)
        assert len(rm.title) <= 255

    def test_exact_bug_title_construction_succeeds(self):
        """The exact title that previously caused the bug must now construct without error."""
        raw = (
            "Roadmap: TARGET (PHASE 1 — Learning from Day 1 to Day 33 — 26 Oct\n\n"
            "Excellence Program with comprehensive exercises and hands-on projects "
            "covering all fundamentals of modern software engineering and architecture)"
        )
        rm = _make_single_day_roadmap(raw)
        assert len(rm.title) <= 255
        assert rm.title.startswith("Roadmap: TARGET")


# ===========================================================================
# 3. Mock provider — oversized goal/context no longer causes generation failure
# ===========================================================================

class TestMockProviderWithLongInputs:
    """
    Verify MockAIProvider + normalization handles inputs that previously caused
    the ValidationError: title > 255 chars.
    """

    def test_long_goal_generates_successfully(self):
        """A goal approaching max_length (500 chars) must still generate successfully."""
        long_goal = "Learn " + "Python Advanced Topics " * 20  # ~460 chars
        long_goal = long_goal[:500]
        req = RoadmapGenerationRequest(
            user_id=1,
            goal=long_goal,
            target_duration_days=3,
            daily_available_minutes=120,
        )
        provider = MockAIProvider()
        result = provider.generate_roadmap(req, effective_daily_capacity=120)
        assert isinstance(result, GeneratedRoadmap)
        assert len(result.title) <= 255

    def test_long_goal_with_long_context_generates_successfully(self):
        """A long goal + long context that would produce a >255 char title is normalized."""
        # goal: ~200 chars, context: ~200 chars → combined title ~ 410 chars before normalization
        goal = "Master FastAPI, PostgreSQL, Redis, Celery, Docker, Kubernetes and " + "cloud " * 20
        goal = goal.strip()[:499]
        context = "Senior Python Engineer with 5 years of experience in distributed systems " + "and microservices " * 8
        context = context.strip()[:499]
        req = RoadmapGenerationRequest(
            user_id=1,
            goal=goal,
            target_duration_days=5,
            daily_available_minutes=120,
            context=context,
        )
        provider = MockAIProvider()
        result = provider.generate_roadmap(req, effective_daily_capacity=120)
        assert isinstance(result, GeneratedRoadmap)
        assert len(result.title) <= 255

    def test_mock_provider_passes_ai_service_pipeline(self):
        """The full AIService.generate_roadmap pipeline succeeds with a long goal+context."""
        goal = "Become a Full Stack Engineer in Python with " + "extensive knowledge " * 15
        goal = goal.strip()[:499]
        context = "Currently a student with " + "very limited experience in " * 10
        context = context.strip()[:499]
        req = RoadmapGenerationRequest(
            user_id=1,
            goal=goal,
            target_duration_days=7,
            daily_available_minutes=90,
            context=context,
        )
        result = ai_service.generate_roadmap(req, effective_daily_capacity=90)
        assert isinstance(result, GeneratedRoadmap)
        assert len(result.title) <= 255


# ===========================================================================
# 4. API endpoint — HTTP 422/500 no longer returned for oversized AI title
# ===========================================================================

class TestApiNormalizationEndToEnd:
    """
    Verify the HTTP API does not return 422 or 500 when AI would produce a
    >255-char title, and that the normalized title appears in the response.
    """

    def test_generate_preview_with_long_goal_returns_200(
        self, client: TestClient, sample_user: User
    ):
        """POST /generate/preview with a long goal must return 200 with normalized title."""
        long_goal = "Master FastAPI and " + "PostgreSQL deeply " * 20
        long_goal = long_goal.strip()[:499]
        payload = {
            "user_id": sample_user.id,
            "goal": long_goal,
            "target_duration_days": 3,
            "daily_available_minutes": 120,
        }
        resp = client.post("/api/v1/roadmaps/generate/preview", json=payload)
        assert resp.status_code == 200, f"Unexpected {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "title" in data
        assert len(data["title"]) <= 255

    def test_generate_with_long_goal_and_context_returns_201(
        self, client: TestClient, sample_user: User
    ):
        """POST /generate with a long goal+context must return 201 with normalized title."""
        goal = "Learn Python " + "and build scalable systems " * 12
        goal = goal.strip()[:499]
        context = "Beginner developer wanting to " + "improve their skills " * 12
        context = context.strip()[:499]
        payload = {
            "user_id": sample_user.id,
            "goal": goal,
            "target_duration_days": 5,
            "daily_available_minutes": 120,
            "context": context,
        }
        resp = client.post("/api/v1/roadmaps/generate", json=payload)
        assert resp.status_code == 201, f"Unexpected {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "title" in data
        assert len(data["title"]) <= 255

    def test_generate_exact_bug_scenario_does_not_return_422_or_500(
        self, client: TestClient, sample_user: User
    ):
        """
        Reproduce the exact user-reported bug scenario and verify no 422/500 is returned.

        The original error:
            Provider failed to generate roadmap:
            1 validation error for GeneratedRoadmap
            title
            String should have at most 255 characters
            [type=string_too_long, input_value='Roadmap: TARGET (PHASE 1... 33 — 26 Oct\\n\\nExce)', ...]
        """
        # Use a goal + context that would produce a >255-char raw title
        goal = "TARGET (PHASE 1 — Learning from Day 1 to Day 33 — 26 Oct Excellence Program)"
        context = (
            "comprehensive exercises and hands-on projects covering all fundamentals "
            "of modern software engineering and architecture"
        )
        payload = {
            "user_id": sample_user.id,
            "goal": goal,
            "target_duration_days": 5,
            "daily_available_minutes": 120,
            "context": context,
        }
        resp = client.post("/api/v1/roadmaps/generate/preview", json=payload)
        assert resp.status_code not in (422, 500), (
            f"Got HTTP {resp.status_code} — bug still present: {resp.text}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["title"]) <= 255

    def test_normalized_title_in_generate_preview_response(
        self, client: TestClient, sample_user: User
    ):
        """The normalized title appears correctly in the preview response body."""
        goal = "Learn Python"
        payload = {
            "user_id": sample_user.id,
            "goal": goal,
            "target_duration_days": 2,
            "daily_available_minutes": 60,
        }
        resp = client.post("/api/v1/roadmaps/generate/preview", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "Learn Python" in data["title"]
        assert len(data["title"]) <= 255

    def test_existing_valid_generation_still_passes(
        self, client: TestClient, sample_user: User
    ):
        """Regression: normal roadmap generation (short title) still works after the fix."""
        payload = {
            "user_id": sample_user.id,
            "goal": "Master Docker and Kubernetes",
            "target_duration_days": 4,
            "daily_available_minutes": 90,
            "context": "Has Linux experience",
        }
        resp = client.post("/api/v1/roadmaps/generate", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert "Master Docker and Kubernetes" in data["title"]
        assert data["target_duration_days"] == 4
        assert len(data["days"]) == 4
