from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.app.schemas.roadmap import RoadmapDetailResponse


class NewTaskDefinition(BaseModel):
    """Structured definition of a new task for roadmap insertion."""
    title: str = Field(..., min_length=1, max_length=255, description="Task title")
    description: Optional[str] = Field(None, description="Detailed task description")
    estimated_minutes: Optional[int] = Field(None, ge=0, description="Estimated duration in minutes")
    order_index: int = Field(0, ge=0, description="Order within the day")
    category: Optional[str] = Field(None, max_length=100, description="Task category or subject")


class NewDayDefinition(BaseModel):
    """Structured definition of a new day containing tasks for roadmap insertion."""
    tasks: List[NewTaskDefinition] = Field(
        ...,
        min_length=1,
        description="List of tasks for this day. Must contain at least one task.",
    )

    @field_validator("tasks")
    @classmethod
    def validate_unique_task_order(cls, tasks: List[NewTaskDefinition]) -> List[NewTaskDefinition]:
        orders = [t.order_index for t in tasks]
        if len(orders) != len(set(orders)):
            raise ValueError("Duplicate order_index found within day tasks")
        return tasks


class RoadmapInsertionRequest(BaseModel):
    """Request payload for inserting new roadmap content."""
    new_days: List[NewDayDefinition] = Field(
        ...,
        min_length=1,
        description="Structured list of new days to insert. Must contain at least one day.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional metadata or source information for audit tracking",
    )


class DayShiftMapping(BaseModel):
    """Mapping describing how an existing day is shifted."""
    day_id: int
    old_day_number: int
    new_day_number: int


class InsertionPreviewResponse(BaseModel):
    """Preview of a proposed insertion without database mutation."""
    status: str = Field(..., description="'SUCCESS' or 'CONFLICT'")
    conflict: bool = Field(..., description="True if a scheduling/capacity conflict was detected")
    conflict_reason: Optional[str] = Field(None, description="Reason code if conflict detected")
    first_incomplete_day: Optional[int] = Field(None, description="Day number of the first incomplete day")
    insertion_start_day: Optional[int] = Field(None, description="Day number where insertion will begin")
    inserted_days_count: int = Field(..., ge=0, description="Number of new days to be inserted")
    shifted_days_count: int = Field(..., ge=0, description="Number of existing days to be shifted forward")
    available_days: int = Field(..., ge=0, description="Remaining day capacity before reaching fixed target duration")
    required_total_days: int = Field(..., ge=0, description="Total days required if insertion were performed")
    target_duration_days: int = Field(..., ge=0, description="Fixed total duration of the roadmap")
    shifted_days: List[DayShiftMapping] = Field(default_factory=list, description="List of day number shift mappings")
    message: str = Field(..., description="Human-readable summary of preview result")

    model_config = ConfigDict(from_attributes=True)


class InsertionResultResponse(BaseModel):
    """Result of an applied roadmap insertion."""
    status: str = Field(..., description="'SUCCESS' or 'CONFLICT'")
    conflict: bool = Field(..., description="True if conflict prevented insertion")
    conflict_reason: Optional[str] = Field(None, description="Reason code if conflict occurred")
    first_incomplete_day: Optional[int] = Field(None, description="Day number of the first incomplete day")
    insertion_start_day: Optional[int] = Field(None, description="Day number where insertion began")
    inserted_days_count: int = Field(0, ge=0, description="Number of new days inserted")
    shifted_days_count: int = Field(0, ge=0, description="Number of existing days shifted")
    available_days: int = Field(0, ge=0, description="Available day slots before insertion")
    required_total_days: int = Field(0, ge=0, description="Total days required")
    target_duration_days: int = Field(0, ge=0, description="Fixed total duration of the roadmap")
    message: str = Field(..., description="Human-readable result summary")
    roadmap: Optional[RoadmapDetailResponse] = Field(None, description="Updated roadmap hierarchy if successful")

    model_config = ConfigDict(from_attributes=True)
