"""
Tests for the MockAIProvider context-parsing behaviour.

These tests verify that:
 1. Day boundary markers are correctly detected in user context.
 2. Content belonging to Day N never appears in a task for another day.
 3. Task titles represent single actionable items (not multi-day blobs).
 4. Task titles do not contain future day markers.
 5. The exact assignment-style roadmap input works end-to-end.
 6. Multiple tasks inside one day are all preserved.
 7. Context with no day boundaries falls back to generic generation.
 8. The 129-day generic fallback still works.
 9. Existing title normalization continues to pass.
10. Day 1 tasks do not include Day 2 tasks.
"""

import pytest
from backend.app.ai.providers.mock import MockAIProvider, _parse_context_to_days
from backend.app.ai.schemas import RoadmapGenerationRequest, GeneratedRoadmap

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

PROVIDER = MockAIProvider()

ASSIGNMENT_CONTEXT = """\
Day 1 — 24 Sept
AOA — Assignment 1
AOA — Assignment 2
COA — Assignment 1

Day 2 — 25 Sept
AOA — Assignment 3
AOA — Assignment 4
ESE — Assignment 1

Day 3 — 26 Sept
AOA — Assignment 5
AOA — Assignment 6
COA — Assignment 2
"""

ASSIGNMENT_GOAL = "ASSIGNMENTS"


def _make_request(
    goal: str = ASSIGNMENT_GOAL,
    duration: int = 3,
    context: str | None = ASSIGNMENT_CONTEXT,
    capacity: int = 120,
) -> RoadmapGenerationRequest:
    return RoadmapGenerationRequest(
        user_id=1,
        goal=goal,
        target_duration_days=duration,
        daily_available_minutes=capacity,
        context=context,
    )


# ---------------------------------------------------------------------------
# Unit tests: _parse_context_to_days
# ---------------------------------------------------------------------------

class TestParseContextToDays:
    """Unit tests for the low-level context parser."""

    def test_returns_none_for_no_boundaries(self):
        """Context without day markers should return None (fallback to generic)."""
        ctx = "Learn Python basics\nRead chapter 1\nDo exercises"
        result = _parse_context_to_days(ctx, capacity=120, target_duration=3)
        assert result is None

    def test_detects_day_boundary_simple(self):
        ctx = "Day 1\nLearn A\nLearn B\nDay 2\nLearn C"
        days = _parse_context_to_days(ctx, capacity=60, target_duration=2)
        assert days is not None
        assert len(days) == 2

    def test_detects_day_boundary_with_dash_date(self):
        """Day 1 — 24 Sept style boundary."""
        days = _parse_context_to_days(ASSIGNMENT_CONTEXT, capacity=120, target_duration=3)
        assert days is not None
        assert len(days) == 3

    def test_day1_tasks_are_correct(self):
        days = _parse_context_to_days(ASSIGNMENT_CONTEXT, capacity=120, target_duration=3)
        day1 = next(d for d in days if d.day_number == 1)
        titles = [t.title for t in day1.tasks]
        assert "AOA — Assignment 1" in titles
        assert "AOA — Assignment 2" in titles
        assert "COA — Assignment 1" in titles

    def test_day2_tasks_are_correct(self):
        days = _parse_context_to_days(ASSIGNMENT_CONTEXT, capacity=120, target_duration=3)
        day2 = next(d for d in days if d.day_number == 2)
        titles = [t.title for t in day2.tasks]
        assert "AOA — Assignment 3" in titles
        assert "AOA — Assignment 4" in titles
        assert "ESE — Assignment 1" in titles

    def test_day3_tasks_are_correct(self):
        days = _parse_context_to_days(ASSIGNMENT_CONTEXT, capacity=120, target_duration=3)
        day3 = next(d for d in days if d.day_number == 3)
        titles = [t.title for t in day3.tasks]
        assert "AOA — Assignment 5" in titles
        assert "AOA — Assignment 6" in titles
        assert "COA — Assignment 2" in titles

    def test_day1_does_not_contain_day2_tasks(self):
        """Boundary test: no Day 2 content leaks into Day 1."""
        days = _parse_context_to_days(ASSIGNMENT_CONTEXT, capacity=120, target_duration=3)
        day1 = next(d for d in days if d.day_number == 1)
        day2_titles = {"AOA — Assignment 3", "AOA — Assignment 4", "ESE — Assignment 1"}
        day1_titles = {t.title for t in day1.tasks}
        assert day1_titles.isdisjoint(day2_titles), (
            f"Day 1 contains Day 2 tasks: {day1_titles & day2_titles}"
        )

    def test_no_task_title_contains_day_marker(self):
        """Task titles must not embed day boundary strings."""
        days = _parse_context_to_days(ASSIGNMENT_CONTEXT, capacity=120, target_duration=3)
        import re
        day_marker_re = re.compile(r"\bDay\s+\d+", re.IGNORECASE)
        for day in days:
            for task in day.tasks:
                assert not day_marker_re.search(task.title), (
                    f"Task title contains day marker: {task.title!r}"
                )

    def test_task_count_matches_items(self):
        """Each day should have exactly as many tasks as items in its section."""
        days = _parse_context_to_days(ASSIGNMENT_CONTEXT, capacity=120, target_duration=3)
        day1 = next(d for d in days if d.day_number == 1)
        day2 = next(d for d in days if d.day_number == 2)
        day3 = next(d for d in days if d.day_number == 3)
        assert len(day1.tasks) == 3
        assert len(day2.tasks) == 3
        assert len(day3.tasks) == 3

    def test_date_title_extracted(self):
        """Day title should be the extracted date string."""
        days = _parse_context_to_days(ASSIGNMENT_CONTEXT, capacity=120, target_duration=3)
        day1 = next(d for d in days if d.day_number == 1)
        assert day1.title == "24 September"

    def test_capacity_distributed_per_task(self):
        """Total estimated_minutes across all tasks in a day should equal capacity."""
        capacity = 120
        days = _parse_context_to_days(ASSIGNMENT_CONTEXT, capacity=capacity, target_duration=3)
        for day in days:
            total = sum(t.estimated_minutes for t in day.tasks)
            assert total == capacity, (
                f"Day {day.day_number}: expected {capacity} mins total, got {total}"
            )

    def test_day_without_date_suffix_has_none_title(self):
        ctx = "Day 1\nLearn A\nDay 2\nLearn B"
        days = _parse_context_to_days(ctx, capacity=60, target_duration=2)
        assert days is not None
        assert days[0].title is None
        assert days[1].title is None

    def test_colon_boundary_parsed(self):
        """Day N: syntax."""
        ctx = "Day 1:\nTask Alpha\nDay 2:\nTask Beta"
        days = _parse_context_to_days(ctx, capacity=60, target_duration=2)
        assert days is not None
        assert len(days) == 2
        assert days[0].tasks[0].title == "Task Alpha"
        assert days[1].tasks[0].title == "Task Beta"

    def test_returns_none_for_empty_string(self):
        result = _parse_context_to_days("", capacity=120, target_duration=3)
        assert result is None

    def test_returns_none_for_whitespace_only(self):
        result = _parse_context_to_days("   \n  \n  ", capacity=120, target_duration=3)
        assert result is None


# ---------------------------------------------------------------------------
# Integration tests: MockAIProvider.generate_roadmap
# ---------------------------------------------------------------------------

class TestMockAIProviderContextParsing:
    """Integration tests for the full provider pipeline."""

    def test_assignment_roadmap_uses_context_tasks(self):
        """End-to-end: the exact assignment-style input produces correct tasks."""
        req = _make_request()
        result = PROVIDER.generate_roadmap(req, effective_daily_capacity=120)
        assert isinstance(result, GeneratedRoadmap)

        day1 = next(d for d in result.days if d.day_number == 1)
        titles = {t.title for t in day1.tasks}
        assert "AOA — Assignment 1" in titles
        assert "AOA — Assignment 2" in titles
        assert "COA — Assignment 1" in titles

    def test_roadmap_title_is_goal_not_context_blob(self):
        """Title must be the goal string, NOT a raw context blob."""
        req = _make_request()
        result = PROVIDER.generate_roadmap(req, effective_daily_capacity=120)
        assert "Day 1" not in result.title
        assert "AOA" not in result.title
        assert ASSIGNMENT_GOAL in result.title

    def test_roadmap_duration_matches_parsed_days(self):
        """target_duration_days on the result must equal the number of parsed days."""
        req = _make_request(duration=10)  # context only has 3 days
        result = PROVIDER.generate_roadmap(req, effective_daily_capacity=120)
        assert result.target_duration_days == len(result.days) == 3

    def test_fallback_to_generic_when_no_boundaries(self):
        """No day boundaries → generic phase-based generation."""
        req = _make_request(
            context="Learn Python basics and build a project",
            duration=5,
        )
        result = PROVIDER.generate_roadmap(req, effective_daily_capacity=120)
        assert len(result.days) == 5
        # Generic generation uses "Study:" / "Practice:" prefixes
        day1_titles = [t.title for t in result.days[0].tasks]
        assert any("Study:" in t for t in day1_titles)

    def test_no_context_falls_back_to_generic(self):
        """None context → generic generation."""
        req = _make_request(context=None, duration=3)
        result = PROVIDER.generate_roadmap(req, effective_daily_capacity=120)
        assert len(result.days) == 3
        day1_titles = [t.title for t in result.days[0].tasks]
        assert any("Study:" in t for t in day1_titles)

    def test_no_task_title_embeds_day_marker_in_parsed_roadmap(self):
        """Generated task titles from context must not contain 'Day N' substrings."""
        import re
        req = _make_request()
        result = PROVIDER.generate_roadmap(req, effective_daily_capacity=120)
        day_marker_re = re.compile(r"\bDay\s+\d+", re.IGNORECASE)
        for day in result.days:
            for task in day.tasks:
                assert not day_marker_re.search(task.title), (
                    f"Task title contains day marker: {task.title!r}"
                )

    def test_all_tasks_have_valid_estimated_minutes(self):
        req = _make_request()
        result = PROVIDER.generate_roadmap(req, effective_daily_capacity=120)
        for day in result.days:
            for task in day.tasks:
                assert task.estimated_minutes >= 1

    def test_generated_roadmap_schema_valid(self):
        """Result must satisfy GeneratedRoadmap schema constraints."""
        req = _make_request()
        result = PROVIDER.generate_roadmap(req, effective_daily_capacity=120)
        # title ≤ 255 chars
        assert len(result.title) <= 255
        # each task title ≤ 255 chars
        for day in result.days:
            assert len(day.tasks) >= 1
            for task in day.tasks:
                assert 1 <= len(task.title) <= 255
                assert task.estimated_minutes >= 1

    def test_129_day_generic_roadmap_still_works(self):
        """Large generic roadmap (129 days) must still generate correctly."""
        req = _make_request(
            goal="Master Computer Science",
            duration=129,
            context=None,
        )
        result = PROVIDER.generate_roadmap(req, effective_daily_capacity=120)
        assert result.target_duration_days == 129
        assert len(result.days) == 129
        for day in result.days:
            assert len(day.tasks) >= 1

    def test_single_day_context(self):
        """A context with only one day section must produce a 1-day roadmap."""
        ctx = "Day 1 — 1 Oct\nRead chapter\nSolve exercises"
        req = _make_request(context=ctx, duration=5)
        result = PROVIDER.generate_roadmap(req, effective_daily_capacity=60)
        assert result.target_duration_days == 1
        assert len(result.days) == 1
        titles = {t.title for t in result.days[0].tasks}
        assert "Read chapter" in titles
        assert "Solve exercises" in titles

    def test_day1_tasks_do_not_include_day2_content_in_result(self):
        """Regression: Day 1 must only contain tasks for Day 1."""
        req = _make_request()
        result = PROVIDER.generate_roadmap(req, effective_daily_capacity=120)
        day1 = next(d for d in result.days if d.day_number == 1)
        day2_titles = {"AOA — Assignment 3", "AOA — Assignment 4", "ESE — Assignment 1"}
        day1_titles = {t.title for t in day1.tasks}
        assert day1_titles.isdisjoint(day2_titles), (
            f"Day 1 contains Day 2 tasks: {day1_titles & day2_titles}"
        )
