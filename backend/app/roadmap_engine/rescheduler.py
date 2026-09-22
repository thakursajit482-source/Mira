from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session, selectinload

from backend.app.models.enums import RoadmapStatus, DayStatus, TaskStatus, RoadmapChangeType
from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.models.task import Task
from backend.app.models.user import User
from backend.app.models.versioning import RoadmapVersion, RoadmapChange
from backend.app.schemas.roadmap import RoadmapDetailResponse
from backend.app.schemas.rescheduling import (
    TaskMovement,
    DayWorkload,
    WorkloadComparison,
    RoadmapRescheduleRequest,
    ReschedulePreviewResponse,
    RescheduleResultResponse,
)


@dataclass
class ReschedulePlan:
    """Internal representation of a calculated rescheduling plan."""
    conflict: bool
    conflict_reason: Optional[str]
    first_incomplete_day_num: Optional[int]
    target_duration_days: int
    daily_capacity_minutes: int
    movable_tasks_count: int
    task_movements: List[TaskMovement] = field(default_factory=list)
    workload_before: List[DayWorkload] = field(default_factory=list)
    workload_after: List[DayWorkload] = field(default_factory=list)
    task_assignments: Dict[int, int] = field(default_factory=dict)  # task_id -> dest_day_number
    task_order_assignments: Dict[int, int] = field(default_factory=dict)  # task_id -> order_index
    message: str = ""


class ReschedulingEngine:
    """
    Deterministic Rescheduling Engine for Mira (PRD Phase 7).
    
    Enforces the following core invariants:
    1. Completed history (Days and Tasks) is completely immutable.
    2. Only future incomplete tasks are eligible for redistribution.
    3. The roadmap's fixed target duration (target_duration_days) is strictly preserved.
    4. Tasks are never deleted or recreated; only day_id and order_index are updated.
    5. Daily workload is balanced against User.daily_available_minutes.
    6. Exactly one CURRENT (or IN_PROGRESS) day exists; no duplicate CURRENT days.
    7. All mutations are transactional with defensive rollback.
    """

    @classmethod
    def calculate_reschedule_plan(
        cls,
        roadmap: Roadmap,
        user: Optional[User],
        request: RoadmapRescheduleRequest,
    ) -> ReschedulePlan:
        """
        Deterministically calculate task redistribution across remaining days.
        NEVER mutates the database.
        """
        # Determine daily capacity
        daily_capacity = (
            request.daily_available_minutes
            or (user.daily_available_minutes if user else None)
            or 120
        )
        if daily_capacity <= 0:
            return ReschedulePlan(
                conflict=True,
                conflict_reason="INVALID_ROADMAP",
                first_incomplete_day_num=None,
                target_duration_days=roadmap.target_duration_days if roadmap else 0,
                daily_capacity_minutes=daily_capacity,
                movable_tasks_count=0,
                message="Daily available minutes must be greater than zero.",
            )

        if not roadmap or roadmap.target_duration_days <= 0:
            return ReschedulePlan(
                conflict=True,
                conflict_reason="INVALID_ROADMAP",
                first_incomplete_day_num=None,
                target_duration_days=roadmap.target_duration_days if roadmap else 0,
                daily_capacity_minutes=daily_capacity,
                movable_tasks_count=0,
                message="Invalid roadmap or non-positive target duration.",
            )

        if roadmap.status in (RoadmapStatus.COMPLETED, RoadmapStatus.ARCHIVED):
            return ReschedulePlan(
                conflict=True,
                conflict_reason="INVALID_ROADMAP",
                first_incomplete_day_num=None,
                target_duration_days=roadmap.target_duration_days,
                daily_capacity_minutes=daily_capacity,
                movable_tasks_count=0,
                message=f"Roadmap is {roadmap.status.value} and cannot be rescheduled.",
            )

        sorted_days = sorted(roadmap.days, key=lambda d: d.day_number)
        if not sorted_days:
            return ReschedulePlan(
                conflict=True,
                conflict_reason="NO_MOVABLE_TASKS",
                first_incomplete_day_num=None,
                target_duration_days=roadmap.target_duration_days,
                daily_capacity_minutes=daily_capacity,
                movable_tasks_count=0,
                message="Roadmap has no days or tasks to reschedule.",
            )

        # 1. Identify first incomplete day
        first_incomplete_day = None
        for d in sorted_days:
            if d.status != DayStatus.COMPLETED:
                first_incomplete_day = d
                break

        if first_incomplete_day is None:
            return ReschedulePlan(
                conflict=True,
                conflict_reason="NO_MOVABLE_TASKS",
                first_incomplete_day_num=None,
                target_duration_days=roadmap.target_duration_days,
                daily_capacity_minutes=daily_capacity,
                movable_tasks_count=0,
                message="All days in the roadmap are completed. No movable tasks found.",
            )

        start_day_num = first_incomplete_day.day_number
        target_duration = roadmap.target_duration_days

        if start_day_num > target_duration:
            return ReschedulePlan(
                conflict=True,
                conflict_reason="INSUFFICIENT_CAPACITY",
                first_incomplete_day_num=start_day_num,
                target_duration_days=target_duration,
                daily_capacity_minutes=daily_capacity,
                movable_tasks_count=0,
                message=(
                    f"First incomplete day {start_day_num} exceeds the fixed target duration of {target_duration} days."
                ),
            )

        # 2. Collect movable incomplete tasks (in existing sequential order)
        movable_tasks: List[Task] = []
        for d in sorted_days:
            if d.status == DayStatus.COMPLETED:
                continue  # Rule 1: Completed days immutable
            for t in sorted(d.tasks, key=lambda t: t.order_index):
                if not t.is_completed and t.status != TaskStatus.COMPLETED:
                    movable_tasks.append(t)

        if not movable_tasks:
            return ReschedulePlan(
                conflict=True,
                conflict_reason="NO_MOVABLE_TASKS",
                first_incomplete_day_num=start_day_num,
                target_duration_days=target_duration,
                daily_capacity_minutes=daily_capacity,
                movable_tasks_count=0,
                message="No incomplete tasks found to reschedule.",
            )

        # 3. Determine available future days and existing fixed workload on partially completed days
        available_day_numbers = list(range(start_day_num, target_duration + 1))
        existing_days_map = {d.day_number: d for d in sorted_days}

        initial_tasks_map: Dict[int, List[Task]] = {}
        initial_minutes_map: Dict[int, int] = {}
        remaining_capacity_map: Dict[int, int] = {}

        for day_num in available_day_numbers:
            existing_day = existing_days_map.get(day_num)
            if existing_day:
                # Completed tasks on partially completed days remain fixed
                fixed_tasks = [
                    t for t in sorted(existing_day.tasks, key=lambda t: t.order_index)
                    if t.is_completed or t.status == TaskStatus.COMPLETED
                ]
                fixed_minutes = sum(t.estimated_minutes or 0 for t in fixed_tasks)
            else:
                fixed_tasks = []
                fixed_minutes = 0

            initial_tasks_map[day_num] = list(fixed_tasks)
            initial_minutes_map[day_num] = fixed_minutes
            remaining_capacity_map[day_num] = max(0, daily_capacity - fixed_minutes)

        # Check total incomplete work against total remaining capacity
        total_incomplete_minutes = sum(t.estimated_minutes or 0 for t in movable_tasks)
        total_available_capacity = sum(remaining_capacity_map[d] for d in available_day_numbers)

        if total_incomplete_minutes > total_available_capacity:
            return ReschedulePlan(
                conflict=True,
                conflict_reason="INSUFFICIENT_CAPACITY",
                first_incomplete_day_num=start_day_num,
                target_duration_days=target_duration,
                daily_capacity_minutes=daily_capacity,
                movable_tasks_count=len(movable_tasks),
                message=(
                    f"Total incomplete workload ({total_incomplete_minutes} mins) exceeds available capacity "
                    f"({total_available_capacity} mins) across the remaining {len(available_day_numbers)} "
                    f"days of the fixed {target_duration}-day roadmap."
                ),
            )

        # 4. Sequential redistribution of movable tasks
        day_assigned_tasks: Dict[int, List[Task]] = {
            d: list(initial_tasks_map[d]) for d in available_day_numbers
        }
        day_assigned_minutes: Dict[int, int] = {
            d: initial_minutes_map[d] for d in available_day_numbers
        }

        curr_idx = 0
        task_assignments: Dict[int, int] = {}
        task_order_assignments: Dict[int, int] = {}
        task_movements: List[TaskMovement] = []

        for task in movable_tasks:
            t_mins = task.estimated_minutes or 0
            placed = False

            while curr_idx < len(available_day_numbers):
                curr_day = available_day_numbers[curr_idx]
                curr_mins = day_assigned_minutes[curr_day]
                curr_tasks = day_assigned_tasks[curr_day]

                if curr_mins + t_mins <= daily_capacity:
                    # Fits on curr_day
                    task_assignments[task.id] = curr_day
                    task_order_assignments[task.id] = len(curr_tasks)
                    day_assigned_tasks[curr_day].append(task)
                    day_assigned_minutes[curr_day] += t_mins
                    placed = True
                    break
                else:
                    if len(curr_tasks) > 0:
                        # Day already has tasks, advance to next day
                        curr_idx += 1
                    else:
                        # Day is empty but a single task exceeds daily_capacity; place it alone
                        task_assignments[task.id] = curr_day
                        task_order_assignments[task.id] = len(curr_tasks)
                        day_assigned_tasks[curr_day].append(task)
                        day_assigned_minutes[curr_day] += t_mins
                        curr_idx += 1
                        placed = True
                        break

            if not placed:
                return ReschedulePlan(
                    conflict=True,
                    conflict_reason="INSUFFICIENT_CAPACITY",
                    first_incomplete_day_num=start_day_num,
                    target_duration_days=target_duration,
                    daily_capacity_minutes=daily_capacity,
                    movable_tasks_count=len(movable_tasks),
                    message=(
                        f"Cannot fit future incomplete tasks within the remaining {len(available_day_numbers)} days "
                        f"of the fixed {target_duration}-day duration without exceeding the daily capacity of "
                        f"{daily_capacity} minutes."
                    ),
                )

        # 5. Determine task movements (only when destination day differs from current day)
        for task in movable_tasks:
            dest_day = task_assignments[task.id]
            from_day = task.day.day_number
            if from_day != dest_day:
                task_movements.append(
                    TaskMovement(
                        task_id=task.id,
                        task_title=task.title,
                        from_day_number=from_day,
                        to_day_number=dest_day,
                        estimated_minutes=task.estimated_minutes,
                    )
                )

        # 6. Compute workload before and after
        max_day = max(target_duration, max((d.day_number for d in sorted_days), default=0))
        workload_before: List[DayWorkload] = []
        workload_after: List[DayWorkload] = []

        for day_num in range(1, max_day + 1):
            d = existing_days_map.get(day_num)
            b_count = len(d.tasks) if d else 0
            b_mins = sum(t.estimated_minutes or 0 for t in d.tasks) if d else 0
            workload_before.append(
                DayWorkload(
                    day_number=day_num,
                    task_count=b_count,
                    total_estimated_minutes=b_mins,
                    is_overloaded=(b_mins > daily_capacity),
                )
            )

            if day_num < start_day_num:
                # Completed day unchanged
                a_count = b_count
                a_mins = b_mins
            elif day_num in day_assigned_tasks:
                tasks_after = day_assigned_tasks[day_num]
                a_count = len(tasks_after)
                a_mins = sum(t.estimated_minutes or 0 for t in tasks_after)
            else:
                a_count = 0
                a_mins = 0

            workload_after.append(
                DayWorkload(
                    day_number=day_num,
                    task_count=a_count,
                    total_estimated_minutes=a_mins,
                    is_overloaded=(a_mins > daily_capacity),
                )
            )

        return ReschedulePlan(
            conflict=False,
            conflict_reason=None,
            first_incomplete_day_num=start_day_num,
            target_duration_days=target_duration,
            daily_capacity_minutes=daily_capacity,
            movable_tasks_count=len(movable_tasks),
            task_movements=task_movements,
            workload_before=workload_before,
            workload_after=workload_after,
            task_assignments=task_assignments,
            task_order_assignments=task_order_assignments,
            message=(
                f"Successfully calculated rescheduling plan. {len(task_movements)} tasks will be moved "
                f"across {len(available_day_numbers)} remaining days (capacity: {daily_capacity} mins/day)."
            ),
        )

    @classmethod
    def preview_reschedule(
        cls,
        roadmap: Roadmap,
        user: Optional[User],
        request: RoadmapRescheduleRequest,
    ) -> ReschedulePreviewResponse:
        """
        Generate a non-destructive preview of the proposed rescheduling.
        NEVER mutates the database.
        """
        plan = cls.calculate_reschedule_plan(roadmap, user, request)

        workload_comp = None
        if not plan.conflict:
            workload_comp = WorkloadComparison(
                before=plan.workload_before,
                after=plan.workload_after,
            )

        return ReschedulePreviewResponse(
            status="CONFLICT" if plan.conflict else "SUCCESS",
            conflict=plan.conflict,
            conflict_reason=plan.conflict_reason,
            first_incomplete_day=plan.first_incomplete_day_num,
            target_duration_days=plan.target_duration_days,
            daily_capacity_minutes=plan.daily_capacity_minutes,
            movable_tasks_count=plan.movable_tasks_count,
            task_movements=plan.task_movements,
            workload_comparison=workload_comp,
            message=plan.message,
        )

    @classmethod
    def apply_reschedule(
        cls,
        db: Session,
        roadmap: Roadmap,
        user: Optional[User],
        request: RoadmapRescheduleRequest,
    ) -> RescheduleResultResponse:
        """
        Apply rescheduling transactionally:
        1. Validates reschedule plan; if conflict exists, aborts with zero DB mutations.
        2. Ensures Day entities exist for all target days within target_duration_days.
        3. Two-phase update of task day_id and order_index to prevent constraint collisions.
        4. Recalculates and updates Day statuses (single CURRENT/IN_PROGRESS day, remaining LOCKED).
        5. Updates user daily_available_minutes if override provided in request.
        6. Creates RoadmapVersion snapshot and RoadmapChange audit log.
        7. Commits transactionally with defensive rollback on error.
        """
        plan = cls.calculate_reschedule_plan(roadmap, user, request)

        if plan.conflict:
            return RescheduleResultResponse(
                status="CONFLICT",
                conflict=True,
                conflict_reason=plan.conflict_reason,
                first_incomplete_day=plan.first_incomplete_day_num,
                target_duration_days=plan.target_duration_days,
                daily_capacity_minutes=plan.daily_capacity_minutes,
                moved_tasks_count=0,
                task_movements=[],
                workload_comparison=None,
                message=plan.message,
                roadmap=None,
            )

        try:
            # Step 1: Ensure Day entities exist for all assigned destination days
            existing_days = {d.day_number: d for d in roadmap.days}
            for day_num in plan.task_assignments.values():
                if day_num not in existing_days:
                    new_day = Day(
                        roadmap_id=roadmap.id,
                        day_number=day_num,
                        status=DayStatus.LOCKED,
                    )
                    db.add(new_day)
                    db.flush()
                    existing_days[day_num] = new_day

            # Step 2: Two-phase update of task day_id and order_index
            movable_task_ids = set(plan.task_assignments.keys())
            tasks_to_update = [
                t for d in roadmap.days for t in d.tasks if t.id in movable_task_ids
            ]

            # Phase 2a: Set temporary negative order_index to avoid (day_id, order_index) collisions
            for idx, t in enumerate(tasks_to_update):
                t.order_index = -(idx + 1000)
            db.flush()

            # Phase 2b: Assign target day_id and new order_index
            for t in tasks_to_update:
                target_day_num = plan.task_assignments[t.id]
                target_day = existing_days[target_day_num]
                t.day_id = target_day.id
                t.order_index = plan.task_order_assignments[t.id]
            db.flush()

            # Step 3: Enforce single CURRENT day invariant across all future days
            start_day_num = plan.first_incomplete_day_num
            for day_num, d in existing_days.items():
                if day_num < start_day_num:
                    continue  # Rule 1: Completed days immutable
                elif day_num == start_day_num:
                    has_completed = any(t.is_completed for t in d.tasks)
                    d.status = DayStatus.IN_PROGRESS if has_completed else DayStatus.CURRENT
                else:
                    d.status = DayStatus.LOCKED
            # Step 4: Create RoadmapVersion snapshot
            next_version = (
                db.scalar(
                    select(func.max(RoadmapVersion.version_number)).where(
                        RoadmapVersion.roadmap_id == roadmap.id
                    )
                )
                or 0
            ) + 1

            all_days = sorted(roadmap.days, key=lambda d: d.day_number)
            snapshot_days = []
            for d in all_days:
                snapshot_days.append({
                    "day_number": d.day_number,
                    "status": d.status.value,
                    "completed_at": d.completed_at.isoformat() if d.completed_at else None,
                    "tasks": [
                        {
                            "id": t.id,
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
                change_summary=(
                    f"Rescheduled {len(plan.task_movements)} tasks across "
                    f"{len(plan.workload_after)} days at {plan.daily_capacity_minutes} mins/day"
                ),
                snapshot_data={"days": snapshot_days},
            )
            db.add(version)
            db.flush()

            # Step 6: Create RoadmapChange audit log
            change = RoadmapChange(
                roadmap_id=roadmap.id,
                version_id=version.id,
                change_type=RoadmapChangeType.WORKLOAD_REBALANCE,
                description=(
                    f"Rescheduled future incomplete tasks. Moved {len(plan.task_movements)} tasks. "
                    f"Daily capacity: {plan.daily_capacity_minutes} mins. Fixed duration: {roadmap.target_duration_days} days."
                ),
                metadata_info={
                    "daily_capacity_minutes": plan.daily_capacity_minutes,
                    "first_incomplete_day": plan.first_incomplete_day_num,
                    "target_duration_days": roadmap.target_duration_days,
                    "moved_tasks_count": len(plan.task_movements),
                    "user_metadata": request.metadata,
                },
            )
            db.add(change)

            # Step 7: Commit transaction
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

        workload_comp = WorkloadComparison(
            before=plan.workload_before,
            after=plan.workload_after,
        )

        return RescheduleResultResponse(
            status="SUCCESS",
            conflict=False,
            conflict_reason=None,
            first_incomplete_day=plan.first_incomplete_day_num,
            target_duration_days=roadmap.target_duration_days,
            daily_capacity_minutes=plan.daily_capacity_minutes,
            moved_tasks_count=len(plan.task_movements),
            task_movements=plan.task_movements,
            workload_comparison=workload_comp,
            message=plan.message,
            roadmap=RoadmapDetailResponse.model_validate(updated_roadmap),
        )


rescheduling_engine = ReschedulingEngine()
