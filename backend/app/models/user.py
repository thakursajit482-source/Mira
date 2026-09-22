from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.app.models.roadmap import Roadmap


class User(Base, TimestampMixin):
    """User entity representing the roadmap owner."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    daily_available_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=120)

    # Relationships
    roadmaps: Mapped[List["Roadmap"]] = relationship(
        "Roadmap",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username='{self.username}'>"
