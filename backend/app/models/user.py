from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.roadmap import Roadmap
    from backend.app.models.notification import Notification


class User(Base, TimestampMixin):
    """User entity representing the roadmap owner."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    daily_available_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=120)

    # Notification Preferences (Phase 10.8)
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )
    daily_reminder_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )
    daily_reminder_time: Mapped[str] = mapped_column(
        String(5),
        default="19:00",
        server_default="19:00",
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(
        String(50),
        default="UTC",
        server_default="UTC",
        nullable=False,
    )

    # Relationships
    roadmaps: Mapped[List["Roadmap"]] = relationship(
        "Roadmap",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username='{self.username}'>"
