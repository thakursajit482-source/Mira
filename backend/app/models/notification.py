import enum
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, ForeignKey, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.user import User
    from backend.app.models.roadmap import Roadmap
    from backend.app.models.day import Day


class NotificationType(str, enum.Enum):
    DAILY_FOCUS = "DAILY_FOCUS"
    DAY_INCOMPLETE = "DAY_INCOMPLETE"
    OVER_CAPACITY = "OVER_CAPACITY"
    ROADMAP_COMPLETE = "ROADMAP_COMPLETE"
    REMINDER = "REMINDER"


class NotificationSeverity(str, enum.Enum):
    INFO = "INFO"
    ATTENTION = "ATTENTION"
    SUCCESS = "SUCCESS"


class NotificationAction(str, enum.Enum):
    VIEW_TODAY = "VIEW_TODAY"
    VIEW_ROADMAP = "VIEW_ROADMAP"
    VIEW_SETTINGS = "VIEW_SETTINGS"


class Notification(Base, TimestampMixin):
    """Notification entity storing user reminders and roadmap alerts."""
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    roadmap_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("roadmaps.id", ondelete="SET NULL"),
        nullable=True,
    )
    day_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("days.id", ondelete="SET NULL"),
        nullable=True,
    )

    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, native_enum=False, length=30),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[NotificationSeverity] = mapped_column(
        Enum(NotificationSeverity, native_enum=False, length=20),
        default=NotificationSeverity.INFO,
        nullable=False,
    )
    action: Mapped[Optional[NotificationAction]] = mapped_column(
        Enum(NotificationAction, native_enum=False, length=30),
        nullable=True,
    )

    dedup_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification id={self.id} user_id={self.user_id} type='{self.type}' read={self.read}>"
