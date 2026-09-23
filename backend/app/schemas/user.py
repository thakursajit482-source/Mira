from typing import Optional, List, Literal, Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class UserPreferencesResponse(BaseModel):
    """Unified user preferences and profile response."""
    user_id: int
    username: str
    email: str
    daily_available_minutes: int = 120
    theme: str = "system"
    timezone: str = "UTC"
    notifications_enabled: bool = True
    daily_reminder_enabled: bool = True
    daily_reminder_time: str = "19:00"
    ask_before_reschedule: bool = True

    model_config = ConfigDict(from_attributes=True)


class UserPreferencesUpdate(BaseModel):
    """Update payload for user preferences."""
    username: Optional[str] = Field(None, min_length=1, max_length=100, description="Display username")
    daily_available_minutes: Optional[int] = Field(
        None,
        ge=15,
        le=1440,
        description="Daily available study or execution minutes (15 to 1440)",
    )
    theme: Optional[Literal["system", "light", "dark"]] = Field(
        None, description="UI theme preference: system, light, or dark"
    )
    timezone: Optional[str] = Field(None, description="IANA timezone identifier")
    notifications_enabled: Optional[bool] = Field(None, description="Global toggle for notifications")
    daily_reminder_enabled: Optional[bool] = Field(None, description="Daily evening reminder toggle")
    daily_reminder_time: Optional[str] = Field(
        None, pattern=r"^\d{2}:\d{2}$", description="Reminder time in HH:MM format"
    )
    ask_before_reschedule: Optional[bool] = Field(
        None, description="Whether to require confirmation before applying schedule adjustments"
    )


class RoadmapExportResponse(BaseModel):
    """Structured, safe export of a complete roadmap."""
    roadmap: Dict[str, Any]
    days: List[Dict[str, Any]]
    tasks: List[Dict[str, Any]]
    history: List[Dict[str, Any]]
    exported_at: str
