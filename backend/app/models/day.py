from datetime import date, datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import Integer, Date, DateTime, Enum, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import DayStatus

if TYPE_CHECKING:
    from backend.app.models.roadmap import Roadmap
    from backend.app.models.task import Task


class Day(Base, TimestampMixin):
    """Day container entity representing a level in the roadmap (PRD Section 9)."""
    __tablename__ = "days"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    roadmap_id: Mapped[int] = mapped_column(
        ForeignKey("roadmaps.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    day_number: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    status: Mapped[DayStatus] = mapped_column(
        Enum(DayStatus, native_enum=False, length=20),
        default=DayStatus.LOCKED,
        nullable=False,
        index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    roadmap: Mapped["Roadmap"] = relationship("Roadmap", back_populates="days")
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="day",
        cascade="all, delete-orphan",
        order_by="Task.order_index",
    )

    __table_args__ = (
        UniqueConstraint("roadmap_id", "day_number", name="uq_roadmap_day_number"),
        Index("ix_days_roadmap_status", "roadmap_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Day id={self.id} roadmap_id={self.roadmap_id} day_number={self.day_number} status='{self.status}'>"
