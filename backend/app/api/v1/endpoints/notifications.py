from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)
from backend.app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get(
    "",
    response_model=NotificationListResponse,
    summary="List Notifications",
    description="Synchronize notifications deterministically based on current state and return list.",
)
def list_notifications(
    user_id: int = Query(1, description="User ID"),
    unread_only: bool = Query(False, description="Filter only unread notifications"),
    limit: int = Query(50, ge=1, le=100, description="Maximum notifications to return"),
    reference_time: Optional[str] = Query(
        None, description="Optional reference ISO timestamp for deterministic evaluation"
    ),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
    """Synchronize and return notification list with unread count."""
    ref_dt: Optional[datetime] = None
    if reference_time:
        clean_time = reference_time.replace(" ", "+").replace("Z", "+00:00")
        ref_dt = datetime.fromisoformat(clean_time)

    return notification_service.sync_and_list_notifications(
        db=db,
        user_id=user_id,
        unread_only=unread_only,
        limit=limit,
        reference_time=ref_dt,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark Notification as Read",
    description="Mark a specific notification as read.",
)
def mark_notification_as_read(
    notification_id: int,
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db),
) -> NotificationResponse:
    """Mark a notification as read."""
    return notification_service.mark_as_read(
        db=db,
        notification_id=notification_id,
        user_id=user_id,
    )


@router.patch(
    "/read-all",
    summary="Mark All Notifications as Read",
    description="Mark all notifications for the user as read.",
)
def mark_all_notifications_as_read(
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db),
) -> dict:
    """Mark all unread notifications as read."""
    return notification_service.mark_all_as_read(
        db=db,
        user_id=user_id,
    )


@router.get(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Get Notification Preferences",
    description="Get notification preferences for the user.",
)
def get_notification_preferences(
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Get notification preferences."""
    return notification_service.get_preferences(
        db=db,
        user_id=user_id,
    )


@router.patch(
    "/preferences",
    response_model=NotificationPreferencesResponse,
    summary="Update Notification Preferences",
    description="Update notification preferences for the user.",
)
def update_notification_preferences(
    preferences_in: NotificationPreferencesUpdate,
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Update notification preferences."""
    return notification_service.update_preferences(
        db=db,
        user_id=user_id,
        update_in=preferences_in,
    )
