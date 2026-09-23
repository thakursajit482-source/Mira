from datetime import date, datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class CompletionMetrics(BaseModel):
    """Roadmap level day completion metrics."""
    total_days: int = Field(..., ge=0, description="Total days in the roadmap")
    completed_days: int = Field(..., ge=0, description="Number of fully completed days")
    remaining_days: int = Field(..., ge=0, description="Number of incomplete days")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of days completed")


class TaskMetrics(BaseModel):
    """Roadmap level task completion metrics."""
    total_tasks: int = Field(..., ge=0, description="Total tasks across all days")
    completed_tasks: int = Field(..., ge=0, description="Total completed tasks")
    remaining_tasks: int = Field(..., ge=0, description="Total incomplete tasks")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of tasks completed")


class TimeMetrics(BaseModel):
    """Roadmap level estimated minute metrics."""
    total_planned_minutes: Optional[int] = Field(None, ge=0, description="Total planned minutes across all tasks")
    completed_minutes: Optional[int] = Field(None, ge=0, description="Completed minutes across completed tasks")
    remaining_minutes: Optional[int] = Field(None, ge=0, description="Remaining minutes across incomplete tasks")
    percentage: Optional[float] = Field(None, ge=0.0, le=100.0, description="Percentage of planned time completed")


class StreakMetrics(BaseModel):
    """Consecutive calendar day execution metrics."""
    current_days: int = Field(..., ge=0, description="Current consecutive productive calendar days")
    best_days: int = Field(..., ge=0, description="All-time best consecutive productive calendar days")
    last_productive_date: Optional[date] = Field(None, description="Most recent calendar date with completed work")


class MomentumStatus(str, Enum):
    """Categorical pace descriptor based on recent activity."""
    BUILDING = "BUILDING"
    STEADY = "STEADY"
    SLOWING = "SLOWING"
    PAUSED = "PAUSED"
    COMPLETE = "COMPLETE"


class MomentumMetrics(BaseModel):
    """Momentum status and human-friendly explanation."""
    status: MomentumStatus
    label: str
    description: str


class Milestone(BaseModel):
    """Deterministic progression milestone."""
    id: str
    title: str
    description: str
    achieved: bool
    achieved_at: Optional[datetime] = None


class RecentProgressActivity(BaseModel):
    """Recent meaningful progress event derived from existing records."""
    id: str
    event_type: str
    title: str
    description: Optional[str] = None
    timestamp: datetime


class RoadmapMomentumResponse(BaseModel):
    """Deterministic progress and momentum response for a roadmap."""
    roadmap_id: int
    completion: CompletionMetrics
    tasks: TaskMetrics
    time: TimeMetrics
    streak: StreakMetrics
    momentum: MomentumMetrics
    milestones: List[Milestone]
    recent_activity: List[RecentProgressActivity]

    model_config = ConfigDict(from_attributes=True)
