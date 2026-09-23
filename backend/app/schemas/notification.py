from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.notification import (
    NotificationType,
    NotificationSeverity,
    NotificationAction,
)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    roadmap_id: Optional[int] = None
    day_id: Optional[int] = None
    type: NotificationType
    title: str
    message: str
    severity: NotificationSeverity
    action: Optional[NotificationAction] = None
    read: bool
    created_at: datetime


class NotificationListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notifications: List[NotificationResponse]
    unread_count: int
    total_count: int


class NotificationPreferencesResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notifications_enabled: bool
    daily_reminder_enabled: bool
    daily_reminder_time: str = Field(..., description="Daily reminder time in HH:MM format (24h)")
    timezone: str = Field(..., description="IANA timezone name, e.g. UTC, Asia/Kolkata")


class NotificationPreferencesUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notifications_enabled: Optional[bool] = None
    daily_reminder_enabled: Optional[bool] = None
    daily_reminder_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$", description="HH:MM format")
    timezone: Optional[str] = None
