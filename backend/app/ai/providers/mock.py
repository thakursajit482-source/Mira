"""
Deterministic mock AI provider for development, CI, and offline testing.

Context parsing strategy
------------------------
When `request.context` contains day boundary markers (e.g. "Day 1 — 24 Sept",
"Day 2:", "Day 3") the provider extracts the item lines within each day section
and builds one GeneratedTask per item.  The day title is set to the date suffix
when present (e.g. "24 September").

Fallback
--------
When no day boundaries are detected in the context, the original phase-based
generic generation is used.  This preserves all existing generic-roadmap
behaviour and all existing test assertions that rely on it.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from backend.app.ai.base import AIProvider
from backend.app.ai.schemas import (
    GeneratedDay,
    GeneratedRoadmap,
    GeneratedTask,
    RoadmapGenerationRequest,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Matches "Day N", "Day N:", "Day N —", "Day N -", "day n", etc.
_DAY_BOUNDARY_RE = re.compile(
    r"^[Dd]ay\s+(\d+)\s*(?:[:\-—–]?\s*(.*))?$"
)

# Matches an explicit date suffix like "24 Sept", "3 October", "14 Sep 2025"
_DATE_SUFFIX_RE = re.compile(
    r"^(\d{1,2})\s+([A-Za-z]{3,}(?:\s+\d{4})?)\s*$"
)

# Lines that should be skipped when extracting tasks (blank or day headers)
_SKIP_RE = re.compile(r"^\s*$")


# ---------------------------------------------------------------------------
# Helper – full month name normalisation
# ---------------------------------------------------------------------------

_MONTH_ABBR_MAP = {
    "jan": "January", "feb": "February", "mar": "March",
    "apr": "April", "may": "May", "jun": "June",
    "jul": "July", "aug": "August", "sep": "September",
    "sept": "September", "oct": "October", "nov": "November",
    "dec": "December",
}


def _normalise_date_suffix(raw: str) -> Optional[str]:
    """Convert '24 Sept' → '24 September', '3 October' → '3 October'.

    Returns None when the suffix does not look like a date.
    """
    m = _DATE_SUFFIX_RE.match(raw.strip())
    if not m:
        return None
    day_part, month_part = m.group(1), m.group(2)
    # Normalise month abbreviation
    key = month_part.lower().rstrip(".")
    # try exact key first
    full_month = _MONTH_ABBR_MAP.get(key)
    if not full_month:
        # try first-three-char prefix
        full_month = _MONTH_ABBR_MAP.get(key[:3], month_part.capitalize())
    return f"{day_part} {full_month}"


# ---------------------------------------------------------------------------
# Context parser
# ---------------------------------------------------------------------------

def _parse_context_to_days(
    context: str,
    capacity: int,
    target_duration: int,
) -> Optional[List[GeneratedDay]]:
    """Parse a structured context string into a list of GeneratedDay objects.

    Returns None when the context does not contain recognisable day boundaries,
    signalling the caller to fall back to generic phase-based generation.

    Parsing rules
    ~~~~~~~~~~~~~
    * A day section begins with a line matching _DAY_BOUNDARY_RE.
    * Any non-blank line within a day section (that is NOT itself a day
      boundary) becomes a separate GeneratedTask.
    * Task titles are the line content verbatim (after stripping).
    * A task title that contains another day boundary marker is treated
      as a parse error for that item and is discarded (guarding against
      run-on context).
    * If fewer days are found in the context than target_duration, the
      parsed days govern the generated roadmap (the caller adjusts
      target_duration accordingly).
    * Per-task time is distributed evenly to fill the daily capacity.
    """
    lines = context.splitlines()

    # First pass: detect whether any day boundaries exist
    has_boundaries = any(_DAY_BOUNDARY_RE.match(l.strip()) for l in lines)
    if not has_boundaries:
        return None

    # Second pass: split into sections
    sections: List[Tuple[int, Optional[str], List[str]]] = []
    current_day_num: Optional[int] = None
    current_date_title: Optional[str] = None
    current_items: List[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        m = _DAY_BOUNDARY_RE.match(line)
        if m:
            # Flush previous section
            if current_day_num is not None:
                sections.append((current_day_num, current_date_title, current_items))
            current_day_num = int(m.group(1))
            suffix_raw = (m.group(2) or "").strip()
            current_date_title = _normalise_date_suffix(suffix_raw) if suffix_raw else None
            current_items = []
        elif current_day_num is not None:
            if not _SKIP_RE.match(line):
                # Guard: skip a line that itself looks like a future day boundary
                if _DAY_BOUNDARY_RE.match(line):
                    continue
                current_items.append(line)

    # Flush last section
    if current_day_num is not None:
        sections.append((current_day_num, current_date_title, current_items))

    if not sections:
        return None

    # Third pass: build GeneratedDay objects
    generated_days: List[GeneratedDay] = []
    for (day_num, date_title, item_lines) in sections:
        # Filter items that accidentally embed another day header mid-line
        clean_items = [
            it for it in item_lines
            if not _DAY_BOUNDARY_RE.match(it)
        ]
        if not clean_items:
            # Day section exists but has no tasks — insert a placeholder so
            # the day is represented without inventing content
            clean_items = ["Review and prepare for this day's work"]

        n_tasks = len(clean_items)
        # Distribute capacity evenly across tasks (minimum 15 mins per task)
        base_mins = max(15, capacity // n_tasks)
        remainder = capacity - base_mins * n_tasks

        tasks: List[GeneratedTask] = []
        for idx, item in enumerate(clean_items):
            # Assign the remainder to the first task
            extra = remainder if idx == 0 else 0
            tasks.append(
                GeneratedTask(
                    title=item,
                    description=None,
                    estimated_minutes=base_mins + extra,
                    category=None,
                    order_index=idx,
                )
            )

        generated_days.append(
            GeneratedDay(
                day_number=day_num,
                title=date_title,
                tasks=tasks,
            )
        )

    # Re-number days sequentially in case the user wrote non-contiguous numbers
    # (e.g. Day 1, Day 3 with Day 2 missing).  Order is preserved; only the
    # day_number field is corrected so the roadmap engine sees 1…N.
    for new_idx, gd in enumerate(generated_days, start=1):
        object.__setattr__(gd, "day_number", new_idx)  # Pydantic v2 safe

    return generated_days if generated_days else None


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

class MockAIProvider(AIProvider):
    """
    Deterministic mock AI provider for development, CI, and offline testing.
    Generates structured, realistic learning roadmaps tailored to the requested
    goal, duration, and daily available capacity without external API calls or
    keys.

    When the user's context contains structured day sections (e.g. from a
    pasted schedule), those sections are parsed and used verbatim for task
    titles.  Generic phase-based generation is used only when no day
    boundaries are detected.
    """

    def generate_roadmap(
        self,
        request: RoadmapGenerationRequest,
        effective_daily_capacity: int,
    ) -> GeneratedRoadmap:
        """
        Generate a deterministic, structured roadmap based on the request.
        Produces exactly request.target_duration_days days (or the number of
        days found in the context when context-parsing is used).
        """
        goal = request.goal.strip()
        duration = request.target_duration_days
        capacity = max(30, effective_daily_capacity)

        # ------------------------------------------------------------------
        # Attempt context-driven generation first
        # ------------------------------------------------------------------
        parsed_days: Optional[List[GeneratedDay]] = None
        if request.context and request.context.strip():
            parsed_days = _parse_context_to_days(
                request.context, capacity, duration
            )

        if parsed_days is not None:
            # Use the parsed structure; adapt the duration to match
            actual_duration = len(parsed_days)
            return GeneratedRoadmap(
                title=goal,
                description=(
                    f"A {actual_duration}-day roadmap for '{goal}' "
                    f"organised from your supplied schedule."
                ),
                target_duration_days=actual_duration,
                days=parsed_days,
            )

        # ------------------------------------------------------------------
        # Fallback: generic phase-based generation (original behaviour)
        # ------------------------------------------------------------------
        days: List[GeneratedDay] = []

        if capacity >= 60:
            task1_mins = capacity // 2
            task2_mins = capacity - task1_mins
            has_two_tasks = True
        else:
            task1_mins = capacity
            task2_mins = 0
            has_two_tasks = False

        for day_num in range(1, duration + 1):
            phase_name, phase_cat = self._get_phase_info(day_num, duration, goal)
            day_title = f"{phase_name} - Part {day_num}"

            tasks: List[GeneratedTask] = []
            tasks.append(
                GeneratedTask(
                    title=f"Study: {goal} - {phase_name} (Day {day_num})",
                    description=f"Core concepts, syntax, and principles for {phase_name.lower()}.",
                    estimated_minutes=task1_mins,
                    category=phase_cat,
                    order_index=0,
                )
            )

            if has_two_tasks:
                tasks.append(
                    GeneratedTask(
                        title=f"Practice: {phase_name} Exercises (Day {day_num})",
                        description=f"Practical hands-on exercises and coding challenges for {goal}.",
                        estimated_minutes=task2_mins,
                        category=f"{phase_cat} Practice",
                        order_index=1,
                    )
                )

            days.append(
                GeneratedDay(
                    day_number=day_num,
                    title=day_title,
                    tasks=tasks,
                )
            )

        return GeneratedRoadmap(
            title=goal,
            description=(
                f"A structured {duration}-day roadmap for '{goal}' "
                f"designed for {capacity} minutes of daily study."
            ),
            target_duration_days=duration,
            days=days,
        )

    @staticmethod
    def _get_phase_info(day_num: int, total_days: int, goal: str) -> tuple[str, str]:
        """Determine logical phase name and category based on progress through the total duration."""
        if total_days <= 2:
            return ("Foundations & Essentials", "Basics")

        progress = day_num / total_days
        if progress <= 0.25:
            return ("Foundations & Setup", "Fundamentals")
        elif progress <= 0.60:
            return ("Core Concepts & Implementation", "Core")
        elif progress <= 0.85:
            return ("Advanced Topics & Architecture", "Advanced")
        else:
            return ("Capstone Project & Review", "Project")
