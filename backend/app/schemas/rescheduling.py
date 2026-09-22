from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from backend.app.schemas.roadmap import RoadmapDetailResponse


class TaskMovement(BaseModel):
    """Details of a task scheduled or moved during rescheduling."""
    task_id: int
    task_title: str
    from_day_number: int
    to_day_number: int
    estimated_minutes: Optional[int] = None


class DayWorkload(BaseModel):
    """Workload metrics for a specific day."""
    day_number: int
    task_count: int
    total_estimated_minutes: int
    is_overloaded: bool = False


class WorkloadComparison(BaseModel):
    """Day-by-day workload comparison before and after rescheduling."""
    before: List[DayWorkload]
    after: List[DayWorkload]


class RoadmapRescheduleRequest(BaseModel):
    """Request payload for rescheduling future incomplete roadmap tasks."""
    daily_available_minutes: Optional[int] = Field(
        None,
        ge=1,
        description="Optional daily available minutes override. If omitted, User.daily_available_minutes is used.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional audit metadata or context for the rescheduling operation",
    )


class ReschedulePreviewResponse(BaseModel):
    """Non-destructive preview of proposed rescheduling."""
    status: str = Field(..., description="'SUCCESS' or 'CONFLICT'")
    conflict: bool = Field(..., description="True if a capacity or schedule conflict was detected")
    conflict_reason: Optional[str] = Field(None, description="Reason code if conflict detected")
    first_incomplete_day: Optional[int] = Field(None, description="Day number of the first incomplete day")
    target_duration_days: int = Field(..., description="Fixed total duration of the roadmap")
    daily_capacity_minutes: int = Field(..., description="Daily available capacity in minutes used for rebalancing")
    movable_tasks_count: int = Field(0, description="Total number of incomplete tasks eligible for redistribution")
    task_movements: List[TaskMovement] = Field(default_factory=list, description="List of tasks that will be moved")
    workload_comparison: Optional[WorkloadComparison] = Field(None, description="Day workload before and after")
    message: str = Field(..., description="Human-readable explanation of the preview result")


class RescheduleResultResponse(BaseModel):
    """Result of applying a rescheduling operation."""
    status: str = Field(..., description="'SUCCESS' or 'CONFLICT'")
    conflict: bool = Field(..., description="True if a capacity or schedule conflict was detected")
    conflict_reason: Optional[str] = Field(None, description="Reason code if conflict detected")
    first_incomplete_day: Optional[int] = Field(None, description="Day number of the first incomplete day")
    target_duration_days: int = Field(..., description="Fixed total duration of the roadmap")
    daily_capacity_minutes: int = Field(..., description="Daily available capacity in minutes used for rebalancing")
    moved_tasks_count: int = Field(0, description="Number of tasks moved to a different day")
    task_movements: List[TaskMovement] = Field(default_factory=list, description="List of tasks that were moved")
    workload_comparison: Optional[WorkloadComparison] = Field(None, description="Day workload before and after")
    message: str = Field(..., description="Human-readable explanation of the result")
    roadmap: Optional[RoadmapDetailResponse] = Field(None, description="Updated roadmap hierarchy if successful")
