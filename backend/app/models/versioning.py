from datetime import datetime
from typing import Optional, List, Any, Dict, TYPE_CHECKING
from sqlalchemy import String, Text, Integer, DateTime, Enum, ForeignKey, JSON, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base
from backend.app.models.enums import RoadmapChangeType

if TYPE_CHECKING:
    from backend.app.models.roadmap import Roadmap


class RoadmapVersion(Base):
    """Snapshot/version of a roadmap state for auditing, history, and reversal."""
    __tablename__ = "roadmap_versions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    roadmap_id: Mapped[int] = mapped_column(
        ForeignKey("roadmaps.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    change_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    snapshot_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    roadmap: Mapped["Roadmap"] = relationship("Roadmap", back_populates="versions")
    changes: Mapped[List["RoadmapChange"]] = relationship(
        "RoadmapChange",
        back_populates="version",
    )

    __table_args__ = (
        UniqueConstraint("roadmap_id", "version_number", name="uq_roadmap_version_number"),
    )

    def __repr__(self) -> str:
        return f"<RoadmapVersion id={self.id} roadmap_id={self.roadmap_id} version={self.version_number}>"


class RoadmapChange(Base):
    """Auditable log entry recording mutations (insertions, shifting, rebalancing)."""
    __tablename__ = "roadmap_changes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    roadmap_id: Mapped[int] = mapped_column(
        ForeignKey("roadmaps.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("roadmap_versions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    change_type: Mapped[RoadmapChangeType] = mapped_column(
        Enum(RoadmapChangeType, native_enum=False, length=30),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    roadmap: Mapped["Roadmap"] = relationship("Roadmap", back_populates="changes")
    version: Mapped[Optional["RoadmapVersion"]] = relationship("RoadmapVersion", back_populates="changes")

    def __repr__(self) -> str:
        return f"<RoadmapChange id={self.id} type='{self.change_type}' roadmap_id={self.roadmap_id}>"
