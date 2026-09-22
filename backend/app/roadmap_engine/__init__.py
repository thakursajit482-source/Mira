"""Deterministic Roadmap Engine for Mira.

CORE ARCHITECTURAL BOUNDARY:
The Roadmap Engine is the primary deterministic authority responsible for enforcing
Mira's core roadmap rules (PRD Sections 11–15). It remains strictly decoupled from AI:
- Find the first incomplete day based on task/day completion states.
- Lock and protect completed days (completed history must NEVER be overwritten).
- Insert new day/task content starting from the first incomplete day (never appended).
- Shift existing future tasks forward.
- Enforce FIXED total roadmap duration (e.g., a 40-day roadmap stays 40 days).
- Detect scheduling/deadline conflicts and generate previews before destructive changes.
- Maintain auditable change records and snapshot versions.
"""

from backend.app.roadmap_engine.engine import RoadmapEngine, roadmap_engine, ShiftPlan
from backend.app.roadmap_engine.rescheduler import ReschedulingEngine, rescheduling_engine, ReschedulePlan

__all__ = [
    "RoadmapEngine",
    "roadmap_engine",
    "ShiftPlan",
    "ReschedulingEngine",
    "rescheduling_engine",
    "ReschedulePlan",
]
