"""Pydantic schemas for data validation and API serialization."""

from backend.app.schemas.health import HealthCheckResponse
from backend.app.schemas.task import TaskBase, TaskResponse
from backend.app.schemas.day import DayBase, DayResponse
from backend.app.schemas.roadmap import (
    RoadmapBase,
    RoadmapCreate,
    RoadmapUpdate,
    RoadmapResponse,
    RoadmapDetailResponse,
)
from backend.app.schemas.progress import RoadmapProgressResponse
from backend.app.schemas.insertion import (
    NewTaskDefinition,
    NewDayDefinition,
    RoadmapInsertionRequest,
    DayShiftMapping,
    InsertionPreviewResponse,
    InsertionResultResponse,
)
from backend.app.schemas.rescheduling import (
    TaskMovement,
    DayWorkload,
    WorkloadComparison,
    RoadmapRescheduleRequest,
    ReschedulePreviewResponse,
    RescheduleResultResponse,
)

from backend.app.schemas.history import (
    RoadmapChangeResponse,
    RoadmapHistoryResponse,
)
from backend.app.schemas.daily_analysis import (
    DailyWorkloadStatus,
    DailyWorkloadAnalysisResponse,
)
from backend.app.schemas.momentum import (
    CompletionMetrics,
    TaskMetrics,
    TimeMetrics,
    StreakMetrics,
    MomentumStatus,
    MomentumMetrics,
    Milestone,
    RecentProgressActivity,
    RoadmapMomentumResponse,
)
from backend.app.schemas.notification import (
    NotificationType,
    NotificationSeverity,
    NotificationAction,
    NotificationResponse,
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)

__all__ = [
    "HealthCheckResponse",
    "TaskBase",
    "TaskResponse",
    "DayBase",
    "DayResponse",
    "RoadmapBase",
    "RoadmapCreate",
    "RoadmapUpdate",
    "RoadmapResponse",
    "RoadmapDetailResponse",
    "RoadmapProgressResponse",
    "NewTaskDefinition",
    "NewDayDefinition",
    "RoadmapInsertionRequest",
    "DayShiftMapping",
    "InsertionPreviewResponse",
    "InsertionResultResponse",
    "TaskMovement",
    "DayWorkload",
    "WorkloadComparison",
    "RoadmapRescheduleRequest",
    "ReschedulePreviewResponse",
    "RescheduleResultResponse",
    "RoadmapChangeResponse",
    "RoadmapHistoryResponse",
    "DailyWorkloadStatus",
    "DailyWorkloadAnalysisResponse",
    "CompletionMetrics",
    "TaskMetrics",
    "TimeMetrics",
    "StreakMetrics",
    "MomentumStatus",
    "MomentumMetrics",
    "Milestone",
    "RecentProgressActivity",
    "RoadmapMomentumResponse",
    "NotificationType",
    "NotificationSeverity",
    "NotificationAction",
    "NotificationResponse",
    "NotificationListResponse",
    "NotificationPreferencesResponse",
    "NotificationPreferencesUpdate",
]

