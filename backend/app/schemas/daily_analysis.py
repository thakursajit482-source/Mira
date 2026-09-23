from datetime import date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class DailyWorkloadStatus(str, Enum):
    """Descriptive capacity state for the current day's workload."""
    ON_TRACK = "ON_TRACK"
    TIGHT = "TIGHT"
    OVER_CAPACITY = "OVER_CAPACITY"
    COMPLETE = "COMPLETE"


class DailyWorkloadAnalysisResponse(BaseModel):
    """Deterministic workload analysis response for smart daily planning."""
    roadmap_id: int
    day_number: int
    day_id: int
    date: Optional[date] = None
    status: DailyWorkloadStatus
    remaining_task_count: int
    completed_task_count: int
    total_task_count: int
    remaining_minutes: int
    completed_minutes: int
    total_minutes: int
    available_minutes: int
    remaining_capacity_minutes: int
    overage_minutes: int
    recommendation: str
    tomorrow_minutes: Optional[int] = None
    upcoming_average_minutes: Optional[int] = None
