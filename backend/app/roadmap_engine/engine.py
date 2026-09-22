from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.models.task import Task
from backend.app.models.versioning import RoadmapVersion, RoadmapChange
from backend.app.models.enums import DayStatus, TaskStatus, RoadmapChangeType
from backend.app.schemas.insertion import (
    RoadmapInsertionRequest,
    DayShiftMapping,
    InsertionPreviewResponse,
    InsertionResultResponse,
)
from backend.app.schemas.roadmap import RoadmapDetailResponse


class ShiftPlan:
    """Internal calculation representation for a proposed insertion."""
    def __init__(
        self,
        conflict: bool,
        conflict_reason: Optional[str],
        first_incomplete_day_num: Optional[int],
        insertion_start_day: Optional[int],
        inserted_days_count: int,
        shifted_days_count: int,
        available_days: int,
        required_total_days: int,
        target_duration_days: int,
        shifted_mappings: List[DayShiftMapping],
        future_days: List[Day],
        message: str,
    ):
        self.conflict = conflict
        self.conflict_reason = conflict_reason
        self.first_incomplete_day_num = first_incomplete_day_num
        self.insertion_start_day = insertion_start_day
        self.inserted_days_count = inserted_days_count
        self.shifted_days_count = shifted_days_count
        self.available_days = available_days
        self.required_total_days = required_total_days
        self.target_duration_days = target_duration_days
        self.shifted_mappings = shifted_mappings
        self.future_days = future_days
        self.message = message


class RoadmapEngine:
    """
    Deterministic Roadmap Engine.
    Enforces core Mira product rules:
    - Protect completed history (never overwrite, modify, or shift completed days).
    - Insert new content starting at the first incomplete day.
    - Shift future incomplete days forward.
    - Enforce fixed total roadmap duration (never silently extend).
    - Detect capacity conflicts and provide non-destructive previews.
    """

    @staticmethod
    def find_first_incomplete_day(days: List[Day]) -> Optional[Day]:
        """
        Deterministically find the earliest Day whose status is not COMPLETED.
        Days must be checked in ascending day_number order.
        """
        sorted_days = sorted(days, key=lambda d: d.day_number)
        for d in sorted_days:
            if d.status != DayStatus.COMPLETED:
                return d
        return None

    @classmethod
    def calculate_shift_plan(
        cls,
        roadmap: Roadmap,
        new_days_count: int,
    ) -> ShiftPlan:
        """
        Pure deterministic calculation for an insertion.
        Calculates shift mapping, capacity, and detects conflicts without database mutation.
        """
        target_duration = roadmap.target_duration_days
        sorted_days = sorted(roadmap.days, key=lambda d: d.day_number)

        # Case 1: Zero-day roadmap
        if len(sorted_days) == 0:
            if new_days_count > target_duration:
                return ShiftPlan(
                    conflict=True,
                    conflict_reason="INSUFFICIENT_CAPACITY",
                    first_incomplete_day_num=1,
                    insertion_start_day=1,
                    inserted_days_count=new_days_count,
                    shifted_days_count=0,
                    available_days=target_duration,
                    required_total_days=new_days_count,
                    target_duration_days=target_duration,
                    shifted_mappings=[],
                    future_days=[],
                    message=f"New content of {new_days_count} days exceeds fixed roadmap duration of {target_duration} days.",
                )
            return ShiftPlan(
                conflict=False,
                conflict_reason=None,
                first_incomplete_day_num=1,
                insertion_start_day=1,
                inserted_days_count=new_days_count,
                shifted_days_count=0,
                available_days=target_duration,
                required_total_days=new_days_count,
                target_duration_days=target_duration,
                shifted_mappings=[],
                future_days=[],
                message=f"New content of {new_days_count} days will be inserted starting at Day 1.",
            )

        # Find the first incomplete day
        first_incomplete = cls.find_first_incomplete_day(sorted_days)

        # Case 2: All existing days are completed
        if first_incomplete is None:
            return ShiftPlan(
                conflict=True,
                conflict_reason="NO_INCOMPLETE_DAY",
                first_incomplete_day_num=None,
                insertion_start_day=None,
                inserted_days_count=new_days_count,
                shifted_days_count=0,
                available_days=0,
                required_total_days=len(sorted_days) + new_days_count,
                target_duration_days=target_duration,
                shifted_mappings=[],
                future_days=[],
                message="All days in the roadmap are already completed. No incomplete day exists for insertion.",
            )

        # Case 3: Incomplete day exists
        start_day_num = first_incomplete.day_number
        completed_days = [d for d in sorted_days if d.day_number < start_day_num]
        future_days = [d for d in sorted_days if d.day_number >= start_day_num]

        total_required = len(completed_days) + new_days_count + len(future_days)
        available_days = max(0, target_duration - (len(completed_days) + len(future_days)))

        # Fixed duration check
        if total_required > target_duration:
            return ShiftPlan(
                conflict=True,
                conflict_reason="INSUFFICIENT_CAPACITY",
                first_incomplete_day_num=start_day_num,
                insertion_start_day=start_day_num,
                inserted_days_count=new_days_count,
                shifted_days_count=len(future_days),
                available_days=available_days,
                required_total_days=total_required,
                target_duration_days=target_duration,
                shifted_mappings=[],
                future_days=future_days,
                message=(
                    f"Cannot insert {new_days_count} days at Day {start_day_num}. "
                    f"Shifting {len(future_days)} existing incomplete days would require {total_required} "
                    f"total days, exceeding the fixed duration of {target_duration} days."
                ),
            )

        # Valid insertion - compute shift mapping
        mappings: List[DayShiftMapping] = []
        for d in future_days:
            mappings.append(
                DayShiftMapping(
                    day_id=d.id,
                    old_day_number=d.day_number,
                    new_day_number=d.day_number + new_days_count,
                )
            )

        return ShiftPlan(
            conflict=False,
            conflict_reason=None,
            first_incomplete_day_num=start_day_num,
            insertion_start_day=start_day_num,
            inserted_days_count=new_days_count,
            shifted_days_count=len(future_days),
            available_days=available_days,
            required_total_days=total_required,
            target_duration_days=target_duration,
            shifted_mappings=mappings,
            future_days=future_days,
            message=(
                f"Successfully planned insertion of {new_days_count} days starting at Day {start_day_num}. "
                f"{len(future_days)} existing incomplete days will be shifted forward."
            ),
        )

    @classmethod
    def preview_insertion(
        cls,
        roadmap: Roadmap,
        request: RoadmapInsertionRequest,
    ) -> InsertionPreviewResponse:
        """
        Generate a non-destructive preview of a proposed insertion.
        NEVER mutates the database.
        """
        new_days_count = len(request.new_days)
        plan = cls.calculate_shift_plan(roadmap, new_days_count)

        return InsertionPreviewResponse(
            status="CONFLICT" if plan.conflict else "SUCCESS",
            conflict=plan.conflict,
            conflict_reason=plan.conflict_reason,
            first_incomplete_day=plan.first_incomplete_day_num,
            insertion_start_day=plan.insertion_start_day,
            inserted_days_count=plan.inserted_days_count,
            shifted_days_count=plan.shifted_days_count,
            available_days=plan.available_days,
            required_total_days=plan.required_total_days,
            target_duration_days=plan.target_duration_days,
            shifted_days=plan.shifted_mappings,
            message=plan.message,
        )

    @classmethod
    def apply_insertion(
        cls,
        db: Session,
        roadmap: Roadmap,
        request: RoadmapInsertionRequest,
    ) -> InsertionResultResponse:
        """
        Apply a roadmap insertion transactionally:
        1. Validates shift plan; if conflict exists, aborts with zero DB mutations.
        2. Safely reassigns existing future day numbers (two-phase shift to prevent unique constraint collisions).
        3. Inserts new Day and Task entities.
        4. Creates a RoadmapVersion snapshot.
        5. Creates a RoadmapChange audit record.
        6. Commits transactionally.
        """
        new_days_count = len(request.new_days)
        plan = cls.calculate_shift_plan(roadmap, new_days_count)

        if plan.conflict:
            return InsertionResultResponse(
                status="CONFLICT",
                conflict=True,
                conflict_reason=plan.conflict_reason,
                first_incomplete_day=plan.first_incomplete_day_num,
                insertion_start_day=plan.insertion_start_day,
                inserted_days_count=0,
                shifted_days_count=0,
                available_days=plan.available_days,
                required_total_days=plan.required_total_days,
                target_duration_days=plan.target_duration_days,
                message=plan.message,
                roadmap=None,
            )

        start_day_num = plan.insertion_start_day
        future_days = plan.future_days

        try:
            # Step 1: Two-phase shift of existing future days
            # Phase 1a: Set temporary negative day numbers to avoid unique constraint collision.
            # If the shifted day was CURRENT, change it to LOCKED since the new first day becomes CURRENT.
            for d in future_days:
                if d.status == DayStatus.CURRENT:
                    d.status = DayStatus.LOCKED
                d.day_number = -d.day_number
            db.flush()

            # Phase 1b: Set target shifted day numbers
            for d in future_days:
                d.day_number = (-d.day_number) + new_days_count
            db.flush()

            # Step 2: Insert new Day and Task entities
            for idx, new_day_def in enumerate(request.new_days):
                day_num = start_day_num + idx
                day_status = DayStatus.CURRENT if idx == 0 else DayStatus.LOCKED
                new_day = Day(
                    roadmap_id=roadmap.id,
                    day_number=day_num,
                    status=day_status,
                )
                db.add(new_day)
                db.flush()

                for task_def in new_day_def.tasks:
                    new_task = Task(
                        day_id=new_day.id,
                        title=task_def.title.strip(),
                        description=task_def.description,
                        estimated_minutes=task_def.estimated_minutes,
                        order_index=task_def.order_index,
                        category=task_def.category,
                        status=TaskStatus.PENDING,
                        is_completed=False,
                    )
                    db.add(new_task)
            db.flush()

            # Step 3: Create RoadmapVersion snapshot
            next_version = (
                db.scalar(
                    select(func.max(RoadmapVersion.version_number)).where(
                        RoadmapVersion.roadmap_id == roadmap.id
                    )
                )
                or 0
            ) + 1

            # Re-fetch days to serialize full snapshot
            all_days = sorted(roadmap.days, key=lambda d: d.day_number)
            snapshot_days = []
            for d in all_days:
                snapshot_days.append({
                    "day_number": d.day_number,
                    "status": d.status.value,
                    "completed_at": d.completed_at.isoformat() if d.completed_at else None,
                    "tasks": [
                        {
                            "title": t.title,
                            "status": t.status.value,
                            "is_completed": t.is_completed,
                            "order_index": t.order_index,
                            "estimated_minutes": t.estimated_minutes,
                            "category": t.category,
                        }
                        for t in sorted(d.tasks, key=lambda t: t.order_index)
                    ],
                })

            version = RoadmapVersion(
                roadmap_id=roadmap.id,
                version_number=next_version,
                change_summary=f"Inserted {new_days_count} days starting at Day {start_day_num}",
                snapshot_data={"days": snapshot_days},
            )
            db.add(version)
            db.flush()

            # Step 4: Create RoadmapChange audit log
            change = RoadmapChange(
                roadmap_id=roadmap.id,
                version_id=version.id,
                change_type=RoadmapChangeType.CONTENT_INSERTION,
                description=(
                    f"Inserted {new_days_count} new days starting at Day {start_day_num}. "
                    f"Shifted {len(future_days)} future days forward."
                ),
                metadata_info={
                    "insertion_start_day": start_day_num,
                    "inserted_days_count": new_days_count,
                    "shifted_days_count": len(future_days),
                    "target_duration_days": roadmap.target_duration_days,
                    "user_metadata": request.metadata,
                },
            )
            db.add(change)

            # Step 5: Commit atomically
            db.commit()
        except Exception:
            db.rollback()
            raise

        # Refresh roadmap with eager loading of days and tasks
        stmt = (
            select(Roadmap)
            .options(selectinload(Roadmap.days).selectinload(Day.tasks))
            .where(Roadmap.id == roadmap.id)
        )
        updated_roadmap = db.scalar(stmt)

        return InsertionResultResponse(
            status="SUCCESS",
            conflict=False,
            conflict_reason=None,
            first_incomplete_day=plan.first_incomplete_day_num,
            insertion_start_day=plan.insertion_start_day,
            inserted_days_count=new_days_count,
            shifted_days_count=len(future_days),
            available_days=plan.available_days,
            required_total_days=plan.required_total_days,
            target_duration_days=roadmap.target_duration_days,
            message=plan.message,
            roadmap=RoadmapDetailResponse.model_validate(updated_roadmap),
        )


roadmap_engine = RoadmapEngine()
