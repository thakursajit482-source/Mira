"""SQLAlchemy ORM models package for Mira.

Core entities supporting the PRD:
- User: Profile and preferences
- Roadmap: Learning plan with fixed total duration
- Day: Day container representing levels (preserves completed history)
- Task: Individual unit of work with independent completion status
- RoadmapVersion: Snapshot data for auditing and reversal
- RoadmapChange: Auditable log of insertions, shifts, and rebalances
"""

from backend.app.models.base import Base, TimestampMixin
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

__all__ = [
    "Base",
    "TimestampMixin",
    "RoadmapStatus",
    "DayStatus",
    "TaskStatus",
    "RoadmapChangeType",
    "User",
    "Roadmap",
    "Day",
    "Task",
    "RoadmapVersion",
    "RoadmapChange",
]
