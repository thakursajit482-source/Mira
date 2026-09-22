from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import TaskStatus


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Task title")
    description: Optional[str] = Field(None, description="Detailed description of the task")
    estimated_minutes: Optional[int] = Field(None, ge=0, description="Estimated duration in minutes")
    order_index: int = Field(0, ge=0, description="Ordering index within the day")
    status: TaskStatus = Field(TaskStatus.PENDING, description="Independent task completion status")
    is_completed: bool = Field(False, description="Quick boolean indicator for completion")
    category: Optional[str] = Field(None, max_length=100, description="Category or subject of the task")


class TaskResponse(TaskBase):
    id: int
    day_id: int
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
