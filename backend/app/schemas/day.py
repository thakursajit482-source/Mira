from datetime import date as dt_date, datetime as dt_datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, computed_field

from backend.app.models.enums import DayStatus
from backend.app.schemas.task import TaskResponse


class DayBase(BaseModel):
    day_number: int = Field(..., gt=0, description="Sequential day number in the roadmap")
    date: Optional[dt_date] = Field(None, description="Optional calendar date for the day")
    status: DayStatus = Field(DayStatus.LOCKED, description="Progress state of the day container")


class DayResponse(DayBase):
    id: int
    roadmap_id: int
    completed_at: Optional[dt_datetime] = None
    created_at: dt_datetime
    updated_at: dt_datetime
    tasks: List[TaskResponse] = Field(default_factory=list, description="Ordered list of tasks for this day")

    @computed_field
    def title(self) -> Optional[str]:
        """Human-readable date label (e.g. '24 September') when date is set."""
        if self.date:
            return self.date.strftime("%d %B").lstrip("0")
        return None

    model_config = ConfigDict(from_attributes=True)
