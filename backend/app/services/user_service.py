import zoneinfo
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.models.user import User
from backend.app.schemas.user import UserPreferencesResponse, UserPreferencesUpdate


class UserService:
    """Service layer managing user preferences and profile settings."""

    @staticmethod
    def get_preferences(db: Session, user_id: int) -> UserPreferencesResponse:
        """Retrieve unified preferences and profile info for a user."""
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found",
            )

        return UserPreferencesResponse(
            user_id=user.id,
            username=user.username,
            email=user.email,
            daily_available_minutes=user.daily_available_minutes or 120,
            theme=getattr(user, "theme", "system") or "system",
            timezone=user.timezone or "UTC",
            notifications_enabled=user.notifications_enabled,
            daily_reminder_enabled=user.daily_reminder_enabled,
            daily_reminder_time=user.daily_reminder_time or "19:00",
            ask_before_reschedule=getattr(user, "ask_before_reschedule", True),
        )

    @staticmethod
    def update_preferences(
        db: Session, user_id: int, update_in: UserPreferencesUpdate
    ) -> UserPreferencesResponse:
        """Update user preferences and profile with validation."""
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {user_id} not found",
            )

        if update_in.username is not None:
            clean_username = update_in.username.strip()
            if not clean_username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username cannot be empty",
                )
            user.username = clean_username

        if update_in.daily_available_minutes is not None:
            if update_in.daily_available_minutes < 15 or update_in.daily_available_minutes > 1440:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Daily available time must be between 15 and 1440 minutes",
                )
            user.daily_available_minutes = update_in.daily_available_minutes

        if update_in.theme is not None:
            if update_in.theme not in ("system", "light", "dark"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Theme must be one of: system, light, dark",
                )
            user.theme = update_in.theme

        if update_in.timezone is not None:
            try:
                zoneinfo.ZoneInfo(update_in.timezone)
                user.timezone = update_in.timezone
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid IANA timezone '{update_in.timezone}'",
                )

        if update_in.notifications_enabled is not None:
            user.notifications_enabled = update_in.notifications_enabled

        if update_in.daily_reminder_enabled is not None:
            user.daily_reminder_enabled = update_in.daily_reminder_enabled

        if update_in.daily_reminder_time is not None:
            user.daily_reminder_time = update_in.daily_reminder_time

        if update_in.ask_before_reschedule is not None:
            user.ask_before_reschedule = update_in.ask_before_reschedule

        db.commit()
        db.refresh(user)

        return UserPreferencesResponse(
            user_id=user.id,
            username=user.username,
            email=user.email,
            daily_available_minutes=user.daily_available_minutes or 120,
            theme=user.theme,
            timezone=user.timezone,
            notifications_enabled=user.notifications_enabled,
            daily_reminder_enabled=user.daily_reminder_enabled,
            daily_reminder_time=user.daily_reminder_time,
            ask_before_reschedule=user.ask_before_reschedule,
        )


user_service = UserService()
