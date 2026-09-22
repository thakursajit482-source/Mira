from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.user import User
from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.schemas.roadmap import RoadmapCreate, RoadmapUpdate
from backend.app.schemas.insertion import (
    RoadmapInsertionRequest,
    InsertionPreviewResponse,
    InsertionResultResponse,
)


class RoadmapService:
    """Service layer managing Roadmap CRUD operations, hierarchy loading, and engine coordination."""

    @staticmethod
    def create_roadmap(db: Session, roadmap_in: RoadmapCreate) -> Roadmap:
        """Create a new roadmap for an existing user."""
        user = db.get(User, roadmap_in.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {roadmap_in.user_id} not found",
            )

        roadmap = Roadmap(
            user_id=roadmap_in.user_id,
            title=roadmap_in.title.strip(),
            description=roadmap_in.description,
            target_duration_days=roadmap_in.target_duration_days,
            status=roadmap_in.status,
            start_date=roadmap_in.start_date,
            target_deadline=roadmap_in.target_deadline,
        )
        db.add(roadmap)
        db.commit()
        db.refresh(roadmap)
        return roadmap

    @staticmethod
    def get_roadmap(db: Session, roadmap_id: int) -> Roadmap:
        """Retrieve roadmap metadata by ID."""
        roadmap = db.get(Roadmap, roadmap_id)
        if not roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roadmap with id {roadmap_id} not found",
            )
        return roadmap

    @staticmethod
    def list_roadmaps(
        db: Session,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Roadmap]:
        """List roadmaps with optional user_id filter and pagination."""
        stmt = select(Roadmap)
        if user_id is not None:
            stmt = stmt.where(Roadmap.user_id == user_id)
        stmt = stmt.order_by(Roadmap.created_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def update_roadmap(
        db: Session,
        roadmap_id: int,
        roadmap_in: RoadmapUpdate,
    ) -> Roadmap:
        """Update roadmap metadata, preserving unspecified fields."""
        roadmap = db.get(Roadmap, roadmap_id)
        if not roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roadmap with id {roadmap_id} not found",
            )

        update_data = roadmap_in.model_dump(exclude_unset=True)
        if not update_data:
            return roadmap

        # Validate effective date consistency
        effective_start = update_data.get("start_date", roadmap.start_date)
        effective_deadline = update_data.get("target_deadline", roadmap.target_deadline)
        if effective_start and effective_deadline and effective_deadline < effective_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="target_deadline cannot be before start_date",
            )

        for field, value in update_data.items():
            if field == "title" and isinstance(value, str):
                value = value.strip()
            setattr(roadmap, field, value)

        db.commit()
        db.refresh(roadmap)
        return roadmap

    @staticmethod
    def delete_roadmap(db: Session, roadmap_id: int) -> None:
        """Delete a roadmap and cascade delete associated days, tasks, versions, and changes."""
        roadmap = db.get(Roadmap, roadmap_id)
        if not roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roadmap with id {roadmap_id} not found",
            )
        db.delete(roadmap)
        db.commit()

    @staticmethod
    def get_roadmap_details(db: Session, roadmap_id: int) -> Roadmap:
        """Retrieve complete roadmap hierarchy: Roadmap -> Days -> Tasks."""
        stmt = (
            select(Roadmap)
            .options(
                selectinload(Roadmap.days).selectinload(Day.tasks)
            )
            .where(Roadmap.id == roadmap_id)
        )
        roadmap = db.scalar(stmt)
        if not roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roadmap with id {roadmap_id} not found",
            )
        return roadmap

    @staticmethod
    def preview_insertion(
        db: Session,
        roadmap_id: int,
        request: RoadmapInsertionRequest,
    ) -> InsertionPreviewResponse:
        """Generate a preview of proposed insertion without database mutation."""
        from backend.app.roadmap_engine.engine import roadmap_engine
        roadmap = RoadmapService.get_roadmap_details(db, roadmap_id)
        return roadmap_engine.preview_insertion(roadmap, request)

    @staticmethod
    def apply_insertion(
        db: Session,
        roadmap_id: int,
        request: RoadmapInsertionRequest,
    ) -> InsertionResultResponse:
        """Apply insertion to the roadmap deterministically."""
        from backend.app.roadmap_engine.engine import roadmap_engine
        roadmap = RoadmapService.get_roadmap_details(db, roadmap_id)
        return roadmap_engine.apply_insertion(db, roadmap, request)


roadmap_service = RoadmapService()
