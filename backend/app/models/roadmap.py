from datetime import date
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, Date, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin
from backend.app.models.enums import RoadmapStatus

if TYPE_CHECKING:
    from backend.app.models.user import User
    from backend.app.models.day import Day
    from backend.app.models.versioning import RoadmapVersion, RoadmapChange


class Roadmap(Base, TimestampMixin):
    """Roadmap entity representing an active or archived learning plan."""
    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Core constraint: target total duration (e.g., 40 days) remains fixed
    target_duration_days: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[RoadmapStatus] = mapped_column(
        Enum(RoadmapStatus, native_enum=False, length=20),
        default=RoadmapStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    target_deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="roadmaps")
    days: Mapped[List["Day"]] = relationship(
        "Day",
        back_populates="roadmap",
        cascade="all, delete-orphan",
        order_by="Day.day_number",
    )
    versions: Mapped[List["RoadmapVersion"]] = relationship(
        "RoadmapVersion",
        back_populates="roadmap",
        cascade="all, delete-orphan",
        order_by="desc(RoadmapVersion.version_number)",
    )
    changes: Mapped[List["RoadmapChange"]] = relationship(
        "RoadmapChange",
        back_populates="roadmap",
        cascade="all, delete-orphan",
        order_by="desc(RoadmapChange.created_at)",
    )

    def __repr__(self) -> str:
        return f"<Roadmap id={self.id} title='{self.title}' duration={self.target_duration_days} status='{self.status}'>"
