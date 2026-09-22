import enum


class RoadmapStatus(str, enum.Enum):
    """Lifecycle status of a Roadmap."""
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class DayStatus(str, enum.Enum):
    """Progress status of a Day container (PRD Section 17)."""
    LOCKED = "LOCKED"           # Future day that is not yet available
    CURRENT = "CURRENT"         # First day requiring action
    IN_PROGRESS = "IN_PROGRESS" # One or more tasks completed, but not all
    COMPLETED = "COMPLETED"     # All required tasks are complete
    AT_RISK = "AT_RISK"         # Optional state for deadline tracking
    SKIPPED = "SKIPPED"         # Optional future state requiring explicit user action


class TaskStatus(str, enum.Enum):
    """Independent completion status of a Task."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class RoadmapChangeType(str, enum.Enum):
    """Auditable change categories for roadmap modifications."""
    INITIAL_GENERATION = "INITIAL_GENERATION"
    CONTENT_INSERTION = "CONTENT_INSERTION"
    WORKLOAD_REBALANCE = "WORKLOAD_REBALANCE"
    TASK_UPDATE = "TASK_UPDATE"
    SCHEDULE_SHIFT = "SCHEDULE_SHIFT"
