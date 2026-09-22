from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, Boolean, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import TaskStatus

if TYPE_CHECKING:
    from backend.app.models.day import Day


class Task(Base, TimestampMixin):
    """Task entity representing the smallest unit of execution within a Day."""
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    day_id: Mapped[int] = mapped_column(
        ForeignKey("days.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=20),
        default=TaskStatus.PENDING,
        nullable=False,
        index=True,
    )
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    day: Mapped["Day"] = relationship("Day", back_populates="tasks")

    __table_args__ = (
        UniqueConstraint("day_id", "order_index", name="uq_day_task_order"),
    )

    def __repr__(self) -> str:
        return f"<Task id={self.id} day_id={self.day_id} title='{self.title}' is_completed={self.is_completed}>"
