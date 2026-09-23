from datetime import datetime, timezone
import zoneinfo
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.models.enums import RoadmapStatus, DayStatus, TaskStatus
from backend.app.models.notification import (
    Notification,
    NotificationType,
    NotificationSeverity,
    NotificationAction,
)
from backend.app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)


class NotificationService:
    """Service handling deterministic notification eligibility, generation, and preferences."""

    def _get_user_zoneinfo(self, tz_name: Optional[str]) -> zoneinfo.ZoneInfo:
        """Safely parse timezone name or fallback to UTC."""
        if not tz_name:
            return zoneinfo.ZoneInfo("UTC")
        try:
            return zoneinfo.ZoneInfo(tz_name)
        except Exception:
            return zoneinfo.ZoneInfo("UTC")

    def sync_and_list_notifications(
        self,
        db: Session,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        reference_time: Optional[datetime] = None,
    ) -> NotificationListResponse:
        """Deterministically evaluates roadmap state and lists notifications for user."""
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found",
            )

        # If user has disabled notifications, do not generate new alerts
        if user.notifications_enabled:
            # Timezone-aware date & time evaluation
            now_utc = reference_time or datetime.now(timezone.utc)
            user_tz = self._get_user_zoneinfo(user.timezone)
            user_local_now = now_utc.astimezone(user_tz)
            calendar_date_str = user_local_now.date().isoformat()
            current_time_str = user_local_now.strftime("%H:%M")
            reminder_time_str = user.daily_reminder_time or "19:00"

            # Query primary/active roadmap for this user
            roadmap = (
                db.query(Roadmap)
                .filter(Roadmap.user_id == user_id, Roadmap.status == RoadmapStatus.ACTIVE)
                .order_by(Roadmap.created_at.desc())
                .first()
            )
            if not roadmap:
                # Fallback to any latest roadmap if no explicitly ACTIVE one
                roadmap = (
                    db.query(Roadmap)
                    .filter(Roadmap.user_id == user_id)
                    .order_by(Roadmap.created_at.desc())
                    .first()
                )

            if roadmap:
                # Check 1: Roadmap Complete
                is_completed = (roadmap.status == RoadmapStatus.COMPLETED) or (
                    len(roadmap.days) > 0
                    and all(d.status == DayStatus.COMPLETED for d in roadmap.days)
                )

                if is_completed:
                    dedup_key = f"user_{user.id}:roadmap_{roadmap.id}:ROADMAP_COMPLETE"
                    existing = db.query(Notification).filter(Notification.dedup_key == dedup_key).first()
                    if not existing:
                        db.add(
                            Notification(
                                user_id=user.id,
                                roadmap_id=roadmap.id,
                                type=NotificationType.ROADMAP_COMPLETE,
                                title="Roadmap complete",
                                message="You finished every planned day in this roadmap.",
                                severity=NotificationSeverity.SUCCESS,
                                action=NotificationAction.VIEW_ROADMAP,
                                dedup_key=dedup_key,
                                read=False,
                            )
                        )
                        db.commit()
                else:
                    # Incomplete roadmap: inspect active day
                    sorted_days = sorted(roadmap.days, key=lambda d: d.day_number)
                    active_day = None
                    for d in sorted_days:
                        if d.status in (DayStatus.CURRENT, DayStatus.IN_PROGRESS, DayStatus.AT_RISK):
                            active_day = d
                            break
                    if not active_day:
                        for d in sorted_days:
                            if d.status != DayStatus.COMPLETED:
                                active_day = d
                                break

                    if active_day:
                        incomplete_tasks = [t for t in active_day.tasks if t.status != TaskStatus.COMPLETED]
                        remaining_minutes = sum(t.estimated_minutes for t in incomplete_tasks)
                        daily_capacity = user.daily_available_minutes or 120

                        # Check 2: Over-Capacity Notification
                        if len(incomplete_tasks) > 0 and remaining_minutes > daily_capacity:
                            overage = remaining_minutes - daily_capacity
                            dedup_key = f"user_{user.id}:roadmap_{roadmap.id}:day_{active_day.id}:OVER_CAPACITY:{calendar_date_str}"
                            existing = db.query(Notification).filter(Notification.dedup_key == dedup_key).first()
                            if not existing:
                                db.add(
                                    Notification(
                                        user_id=user.id,
                                        roadmap_id=roadmap.id,
                                        day_id=active_day.id,
                                        type=NotificationType.OVER_CAPACITY,
                                        title="Plan is over capacity",
                                        message=f"Today’s plan is {overage} minutes over your available time.",
                                        severity=NotificationSeverity.ATTENTION,
                                        action=NotificationAction.VIEW_TODAY,
                                        dedup_key=dedup_key,
                                        read=False,
                                    )
                                )
                                db.commit()

                        # Check 3: Daily Incomplete Reminder or Daily Focus
                        if user.daily_reminder_enabled:
                            if current_time_str >= reminder_time_str:
                                # After reminder time: send DAY_INCOMPLETE reminder if tasks remain
                                if len(incomplete_tasks) > 0:
                                    dedup_key = f"user_{user.id}:roadmap_{roadmap.id}:day_{active_day.id}:DAY_INCOMPLETE:{calendar_date_str}"
                                    existing = db.query(Notification).filter(Notification.dedup_key == dedup_key).first()
                                    if not existing:
                                        db.add(
                                            Notification(
                                                user_id=user.id,
                                                roadmap_id=roadmap.id,
                                                day_id=active_day.id,
                                                type=NotificationType.DAY_INCOMPLETE,
                                                title=f"Day {active_day.day_number} plan is incomplete",
                                                message=f"You have {len(incomplete_tasks)} tasks remaining for today.",
                                                severity=NotificationSeverity.ATTENTION,
                                                action=NotificationAction.VIEW_TODAY,
                                                dedup_key=dedup_key,
                                                read=False,
                                            )
                                        )
                                        db.commit()
                            else:
                                # Before reminder time: send DAILY_FOCUS if day has incomplete tasks
                                if len(incomplete_tasks) > 0:
                                    dedup_key = f"user_{user.id}:roadmap_{roadmap.id}:day_{active_day.id}:DAILY_FOCUS:{calendar_date_str}"
                                    existing = db.query(Notification).filter(Notification.dedup_key == dedup_key).first()
                                    if not existing:
                                        db.add(
                                            Notification(
                                                user_id=user.id,
                                                roadmap_id=roadmap.id,
                                                day_id=active_day.id,
                                                type=NotificationType.DAILY_FOCUS,
                                                title=f"Today's Focus: Day {active_day.day_number}",
                                                message=f"You have {len(incomplete_tasks)} tasks planned for today ({remaining_minutes} min).",
                                                severity=NotificationSeverity.INFO,
                                                action=NotificationAction.VIEW_TODAY,
                                                dedup_key=dedup_key,
                                                read=False,
                                            )
                                        )
                                        db.commit()

        # Query all notifications for user
        base_query = db.query(Notification).filter(Notification.user_id == user_id)
        unread_count = (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.read == False)
            .count()
        )
        total_count = base_query.count()

        if unread_only:
            query = base_query.filter(Notification.read == False)
        else:
            query = base_query

        notifications = query.order_by(Notification.created_at.desc()).limit(limit).all()

        return NotificationListResponse(
            notifications=[NotificationResponse.model_validate(n) for n in notifications],
            unread_count=unread_count,
            total_count=total_count,
        )

    def mark_as_read(self, db: Session, notification_id: int, user_id: int) -> NotificationResponse:
        """Mark a single notification as read."""
        notification = (
            db.query(Notification)
            .filter(Notification.id == notification_id, Notification.user_id == user_id)
            .first()
        )
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Notification with id {notification_id} not found",
            )

        notification.read = True
        db.commit()
        db.refresh(notification)
        return NotificationResponse.model_validate(notification)

    def mark_all_as_read(self, db: Session, user_id: int) -> dict:
        """Mark all notifications for user as read."""
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found",
            )

        updated_count = (
            db.query(Notification)
            .filter(Notification.user_id == user_id, Notification.read == False)
            .update({"read": True})
        )
        db.commit()
        return {"updated_count": updated_count}

    def get_preferences(self, db: Session, user_id: int) -> NotificationPreferencesResponse:
        """Retrieve user notification preferences."""
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found",
            )

        return NotificationPreferencesResponse(
            notifications_enabled=user.notifications_enabled,
            daily_reminder_enabled=user.daily_reminder_enabled,
            daily_reminder_time=user.daily_reminder_time,
            timezone=user.timezone,
        )

    def update_preferences(
        self, db: Session, user_id: int, update_in: NotificationPreferencesUpdate
    ) -> NotificationPreferencesResponse:
        """Update user notification preferences."""
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found",
            )

        if update_in.notifications_enabled is not None:
            user.notifications_enabled = update_in.notifications_enabled
        if update_in.daily_reminder_enabled is not None:
            user.daily_reminder_enabled = update_in.daily_reminder_enabled
        if update_in.daily_reminder_time is not None:
            user.daily_reminder_time = update_in.daily_reminder_time
        if update_in.timezone is not None:
            # Validate timezone string
            try:
                zoneinfo.ZoneInfo(update_in.timezone)
                user.timezone = update_in.timezone
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid IANA timezone '{update_in.timezone}'",
                )

        db.commit()
        db.refresh(user)
        return NotificationPreferencesResponse(
            notifications_enabled=user.notifications_enabled,
            daily_reminder_enabled=user.daily_reminder_enabled,
            daily_reminder_time=user.daily_reminder_time,
            timezone=user.timezone,
        )


notification_service = NotificationService()
