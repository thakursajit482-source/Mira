from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.models.enums import RoadmapStatus
from backend.app.schemas.day import DayResponse


class RoadmapBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Roadmap title")
    description: Optional[str] = Field(None, description="Detailed description of the roadmap")
    target_duration_days: int = Field(..., gt=0, description="Fixed total duration in days")
    start_date: Optional[date] = Field(None, description="Planned start date")
    target_deadline: Optional[date] = Field(None, description="Planned completion deadline")
    status: RoadmapStatus = Field(RoadmapStatus.ACTIVE, description="Roadmap lifecycle status")

    @model_validator(mode="after")
    def validate_dates(self) -> "RoadmapBase":
        if self.start_date and self.target_deadline:
            if self.target_deadline < self.start_date:
                raise ValueError("target_deadline cannot be before start_date")
        return self


class RoadmapCreate(RoadmapBase):
    user_id: int = Field(
        ...,
        gt=0,
        description="Owner user ID (explicit until authentication is implemented)",
    )


class RoadmapUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255, description="Roadmap title")
    description: Optional[str] = Field(None, description="Detailed description of the roadmap")
    target_duration_days: Optional[int] = Field(None, gt=0, description="Fixed total duration in days")
    start_date: Optional[date] = Field(None, description="Planned start date")
    target_deadline: Optional[date] = Field(None, description="Planned completion deadline")
    status: Optional[RoadmapStatus] = Field(None, description="Roadmap lifecycle status")

    @model_validator(mode="after")
    def validate_dates(self) -> "RoadmapUpdate":
        if self.start_date and self.target_deadline:
            if self.target_deadline < self.start_date:
                raise ValueError("target_deadline cannot be before start_date")
        return self


class RoadmapResponse(RoadmapBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoadmapDetailResponse(RoadmapResponse):
    days: List[DayResponse] = Field(
        default_factory=list,
        description="Ordered list of days and their respective tasks",
    )

    model_config = ConfigDict(from_attributes=True)
