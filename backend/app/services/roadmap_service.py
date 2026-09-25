from datetime import datetime, date as dt_date
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.user import User
from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.models.task import Task
from backend.app.models.enums import RoadmapStatus, DayStatus, TaskStatus, RoadmapChangeType
from backend.app.models.versioning import RoadmapVersion, RoadmapChange
from backend.app.schemas.roadmap import RoadmapCreate, RoadmapUpdate
from backend.app.schemas.insertion import (
    RoadmapInsertionRequest,
    InsertionPreviewResponse,
    InsertionResultResponse,
)
from backend.app.schemas.rescheduling import (
    RoadmapRescheduleRequest,
    ReschedulePreviewResponse,
    RescheduleResultResponse,
)
from backend.app.schemas.history import (
    RoadmapChangeResponse,
    RoadmapHistoryResponse,
)
from backend.app.ai.schemas import RoadmapGenerationRequest
from backend.app.ai.service import ai_service
from backend.app.ai.validator import AIValidationError


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

    @staticmethod
    def preview_reschedule(
        db: Session,
        roadmap_id: int,
        request: RoadmapRescheduleRequest,
    ) -> ReschedulePreviewResponse:
        """Generate a preview of proposed rescheduling without database mutation."""
        from backend.app.roadmap_engine.rescheduler import rescheduling_engine
        roadmap = RoadmapService.get_roadmap_details(db, roadmap_id)
        user = db.get(User, roadmap.user_id)
        return rescheduling_engine.preview_reschedule(roadmap, user, request)

    @staticmethod
    def apply_reschedule(
        db: Session,
        roadmap_id: int,
        request: RoadmapRescheduleRequest,
    ) -> RescheduleResultResponse:
        """Apply rescheduling to future incomplete tasks deterministically."""
        from backend.app.roadmap_engine.rescheduler import rescheduling_engine
        roadmap = RoadmapService.get_roadmap_details(db, roadmap_id)
        user = db.get(User, roadmap.user_id)
        return rescheduling_engine.apply_reschedule(db, roadmap, user, request)

    @staticmethod
    def _parse_day_title_to_date(title: Optional[str], default_year: int = 2026) -> Optional[dt_date]:
        """Convert a date-like title (e.g. '24 September') into a date object if possible."""
        if not title:
            return None
        title = title.strip()
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(title, fmt).date()
            except ValueError:
                pass
        for fmt in ("%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(f"{title} {default_year}", fmt).date()
            except ValueError:
                pass
        return None

    @staticmethod
    def generate_and_create_roadmap(
        db: Session,
        request: RoadmapGenerationRequest,
    ) -> Roadmap:
        """
        Orchestrate AI-assisted roadmap generation and database persistence:
        1. Validates user existence.
        2. Resolves effective daily capacity.
        3. Calls AIService to generate and validate structured roadmap output.
        4. Transactionally creates Roadmap, Day, Task, RoadmapVersion, and RoadmapChange records.
        5. Commits atomically with defensive rollback.
        """
        user = db.get(User, request.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with id {request.user_id} not found",
            )

        effective_daily_capacity = (
            request.daily_available_minutes
            or user.daily_available_minutes
            or 120
        )

        try:
            generated = ai_service.generate_roadmap(request, effective_daily_capacity)
        except AIValidationError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": err.message, "errors": err.details},
            )
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI provider failed to generate roadmap: {str(err)}",
            )

        try:
            # Step 1: Create Roadmap
            roadmap = Roadmap(
                user_id=user.id,
                title=generated.title.strip(),
                description=generated.description,
                target_duration_days=generated.target_duration_days,
                status=RoadmapStatus.ACTIVE,
            )
            db.add(roadmap)
            db.flush()

            # Step 2: Create Days and Tasks
            snapshot_days = []
            for day_data in sorted(generated.days, key=lambda d: d.day_number):
                day_status = DayStatus.CURRENT if day_data.day_number == 1 else DayStatus.LOCKED
                day_date = RoadmapService._parse_day_title_to_date(day_data.title)
                day = Day(
                    roadmap_id=roadmap.id,
                    day_number=day_data.day_number,
                    date=day_date,
                    status=day_status,
                )
                db.add(day)
                db.flush()

                day_tasks = []
                for task_data in sorted(day_data.tasks, key=lambda t: t.order_index):
                    task = Task(
                        day_id=day.id,
                        title=task_data.title.strip(),
                        description=task_data.description,
                        estimated_minutes=task_data.estimated_minutes,
                        order_index=task_data.order_index,
                        category=task_data.category,
                        status=TaskStatus.PENDING,
                        is_completed=False,
                    )
                    db.add(task)
                    day_tasks.append({
                        "title": task.title,
                        "status": TaskStatus.PENDING.value,
                        "is_completed": False,
                        "order_index": task.order_index,
                        "estimated_minutes": task.estimated_minutes,
                        "category": task.category,
                    })

                snapshot_days.append({
                    "day_number": day.day_number,
                    "status": day_status.value,
                    "completed_at": None,
                    "tasks": day_tasks,
                })
            db.flush()

            # Step 3: Create RoadmapVersion snapshot (v1)
            version = RoadmapVersion(
                roadmap_id=roadmap.id,
                version_number=1,
                change_summary=f"Initial AI generation for goal: '{request.goal}'",
                snapshot_data={"days": snapshot_days},
            )
            db.add(version)
            db.flush()

            # Step 4: Create RoadmapChange audit log
            change = RoadmapChange(
                roadmap_id=roadmap.id,
                version_id=version.id,
                change_type=RoadmapChangeType.INITIAL_GENERATION,
                description=f"Generated initial roadmap with {len(generated.days)} days for goal: '{request.goal}'.",
                metadata_info={
                    "goal": request.goal,
                    "target_duration_days": request.target_duration_days,
                    "daily_available_minutes": effective_daily_capacity,
                    "context": request.context,
                },
            )
            db.add(change)

            # Step 5: Commit atomically
            db.commit()
        except Exception:
            db.rollback()
            raise

        # Return eager-loaded roadmap
        stmt = (
            select(Roadmap)
            .options(selectinload(Roadmap.days).selectinload(Day.tasks))
            .where(Roadmap.id == roadmap.id)
        )
        return db.scalar(stmt)

    @staticmethod
    def get_roadmap_history(db: Session, roadmap_id: int) -> RoadmapHistoryResponse:
        """Retrieve chronological change timeline and audit log for a roadmap, newest changes first."""
        roadmap = db.get(Roadmap, roadmap_id)
        if not roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roadmap with id {roadmap_id} not found",
            )

        stmt = (
            select(RoadmapChange)
            .options(selectinload(RoadmapChange.version))
            .where(RoadmapChange.roadmap_id == roadmap_id)
            .order_by(RoadmapChange.created_at.desc(), RoadmapChange.id.desc())
        )
        changes = db.scalars(stmt).all()

        change_responses = [
            RoadmapChangeResponse(
                id=c.id,
                roadmap_id=c.roadmap_id,
                version_id=c.version_id,
                version_number=c.version.version_number if c.version else None,
                change_type=c.change_type,
                description=c.description,
                metadata_info=c.metadata_info,
                created_at=c.created_at,
            )
            for c in changes
        ]

        return RoadmapHistoryResponse(
            roadmap_id=roadmap_id,
            total_changes=len(change_responses),
            changes=change_responses,
        )

    @staticmethod
    def export_roadmap(db: Session, roadmap_id: int):
        """Export roadmap, days, tasks, and history deterministically as clean JSON."""
        from datetime import datetime, timezone
        from backend.app.schemas.user import RoadmapExportResponse

        roadmap = db.get(Roadmap, roadmap_id)
        if not roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roadmap with id {roadmap_id} not found",
            )

        roadmap_data = {
            "id": roadmap.id,
            "title": roadmap.title,
            "description": roadmap.description,
            "target_duration_days": roadmap.target_duration_days,
            "status": roadmap.status.value if hasattr(roadmap.status, "value") else str(roadmap.status),
            "start_date": roadmap.start_date.isoformat() if roadmap.start_date else None,
            "target_deadline": roadmap.target_deadline.isoformat() if roadmap.target_deadline else None,
            "created_at": roadmap.created_at.isoformat() if roadmap.created_at else None,
        }

        days_data = []
        tasks_data = []
        for day in sorted(roadmap.days, key=lambda d: d.day_number):
            days_data.append({
                "id": day.id,
                "day_number": day.day_number,
                "status": day.status.value if hasattr(day.status, "value") else str(day.status),
                "date": day.date.isoformat() if day.date else None,
                "completed_at": day.completed_at.isoformat() if day.completed_at else None,
            })
            for task in sorted(day.tasks, key=lambda t: t.order_index):
                tasks_data.append({
                    "id": task.id,
                    "day_id": task.day_id,
                    "day_number": day.day_number,
                    "title": task.title,
                    "description": task.description,
                    "estimated_minutes": task.estimated_minutes,
                    "order_index": task.order_index,
                    "status": task.status.value if hasattr(task.status, "value") else str(task.status),
                    "is_completed": task.is_completed,
                    "category": task.category,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                })

        history_resp = RoadmapService.get_roadmap_history(db, roadmap_id)
        history_data = [
            {
                "id": c.id,
                "version_number": c.version_number,
                "change_type": c.change_type.value if hasattr(c.change_type, "value") else str(c.change_type),
                "description": c.description,
                "metadata_info": c.metadata_info,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in history_resp.changes
        ]

        return RoadmapExportResponse(
            roadmap=roadmap_data,
            days=days_data,
            tasks=tasks_data,
            history=history_data,
            exported_at=datetime.now(timezone.utc).isoformat(),
        )


roadmap_service = RoadmapService()
