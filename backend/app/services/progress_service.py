from datetime import datetime, timezone, date, timedelta
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.models.task import Task
from backend.app.models.enums import DayStatus, TaskStatus
from backend.app.schemas.progress import RoadmapProgressResponse
from backend.app.schemas.momentum import (
    RoadmapMomentumResponse,
    CompletionMetrics,
    TaskMetrics,
    TimeMetrics,
    StreakMetrics,
    MomentumStatus,
    MomentumMetrics,
    Milestone,
    RecentProgressActivity,
)


class ProgressService:
    """Service managing deterministic progress calculation and task/day completion states."""

    @staticmethod
    def get_task(db: Session, task_id: int) -> Task:
        """Retrieve task by ID or raise 404."""
        task = db.get(Task, task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task with id {task_id} not found",
            )
        return task

    @staticmethod
    def get_day(db: Session, day_id: int) -> Day:
        """Retrieve day by ID with ordered tasks or raise 404."""
        stmt = (
            select(Day)
            .options(selectinload(Day.tasks))
            .where(Day.id == day_id)
        )
        day = db.scalar(stmt)
        if not day:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Day with id {day_id} not found",
            )
        return day

    @classmethod
    def recalculate_day_status(cls, db: Session, day: Day) -> Day:
        """
        Recalculate Day status based on its tasks:
        - All tasks completed (and count > 0) -> COMPLETED, sets completed_at
        - Some tasks completed (count > 0) -> IN_PROGRESS, clears completed_at
        - 0 tasks completed -> CURRENT (if previously completed or in progress), clears completed_at
        - 0 total tasks -> never COMPLETED
        """
        tasks = day.tasks
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.is_completed)

        if total_tasks == 0:
            if day.status == DayStatus.COMPLETED:
                day.status = DayStatus.CURRENT
            day.completed_at = None
        elif completed_tasks == total_tasks:
            day.status = DayStatus.COMPLETED
            if not day.completed_at:
                day.completed_at = datetime.now(timezone.utc)
        elif completed_tasks > 0:
            day.status = DayStatus.IN_PROGRESS
            day.completed_at = None
        else:
            if day.status in (DayStatus.COMPLETED, DayStatus.IN_PROGRESS):
                day.status = DayStatus.CURRENT
            day.completed_at = None

        return day

    @classmethod
    def complete_task(cls, db: Session, task_id: int) -> Task:
        """
        Mark a task as completed:
        - Set status = COMPLETED, is_completed = True, completed_at = now
        - Recalculate parent Day status
        - Idempotent: repeated completion does not alter timestamp
        """
        task = cls.get_task(db, task_id)

        if not task.is_completed:
            task.status = TaskStatus.COMPLETED
            task.is_completed = True
            task.completed_at = datetime.now(timezone.utc)

            # Recalculate parent Day
            cls.recalculate_day_status(db, task.day)

            db.commit()
            db.refresh(task)

        return task

    @classmethod
    def uncomplete_task(cls, db: Session, task_id: int) -> Task:
        """
        Mark a task as incomplete:
        - Set status = PENDING, is_completed = False, completed_at = None
        - Recalculate parent Day status (previously completed Day becomes incomplete)
        - Idempotent: repeated uncompletion is safe
        """
        task = cls.get_task(db, task_id)

        if task.is_completed or task.status == TaskStatus.COMPLETED:
            task.status = TaskStatus.PENDING
            task.is_completed = False
            task.completed_at = None

            # Recalculate parent Day
            cls.recalculate_day_status(db, task.day)

            db.commit()
            db.refresh(task)

        return task

    @staticmethod
    def calculate_roadmap_progress(db: Session, roadmap_id: int) -> RoadmapProgressResponse:
        """
        Calculate deterministic roadmap progress based on completed days vs total days.
        """
        stmt = (
            select(Roadmap)
            .options(selectinload(Roadmap.days).selectinload(Day.tasks))
            .where(Roadmap.id == roadmap_id)
        )
        roadmap = db.scalar(stmt)
        if not roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roadmap with id {roadmap_id} not found",
            )

        total_days = len(roadmap.days)
        completed_days = sum(1 for d in roadmap.days if d.status == DayStatus.COMPLETED)
        progress_percentage = (
            round((completed_days / total_days) * 100.0, 2) if total_days > 0 else 0.0
        )

        total_tasks = sum(len(d.tasks) for d in roadmap.days)
        completed_tasks = sum(
            sum(1 for t in d.tasks if t.is_completed) for d in roadmap.days
        )

        return RoadmapProgressResponse(
            roadmap_id=roadmap.id,
            total_days=total_days,
            completed_days=completed_days,
            progress_percentage=progress_percentage,
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
        )

    @classmethod
    def calculate_roadmap_momentum(
        cls,
        db: Session,
        roadmap_id: int,
        reference_date: Optional[date] = None,
    ) -> RoadmapMomentumResponse:
        """
        Calculate deterministic progress, streaks, momentum classification,
        milestones, and recent activity feed for a roadmap.
        """
        stmt = (
            select(Roadmap)
            .options(selectinload(Roadmap.days).selectinload(Day.tasks))
            .where(Roadmap.id == roadmap_id)
        )
        roadmap = db.scalar(stmt)
        if not roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roadmap with id {roadmap_id} not found",
            )

        if reference_date is None:
            reference_date = datetime.now(timezone.utc).date()

        days = sorted(roadmap.days, key=lambda d: d.day_number)
        all_tasks = [t for d in days for t in d.tasks]

        # 1. Day completion metrics
        total_days = len(days)
        completed_days = sum(1 for d in days if d.status == DayStatus.COMPLETED)
        remaining_days = max(0, total_days - completed_days)
        day_percentage = round((completed_days / total_days) * 100.0, 1) if total_days > 0 else 0.0

        completion_metrics = CompletionMetrics(
            total_days=total_days,
            completed_days=completed_days,
            remaining_days=remaining_days,
            percentage=day_percentage,
        )

        # 2. Task completion metrics
        total_tasks = len(all_tasks)
        completed_tasks = sum(1 for t in all_tasks if t.is_completed)
        remaining_tasks = max(0, total_tasks - completed_tasks)
        task_percentage = round((completed_tasks / total_tasks) * 100.0, 1) if total_tasks > 0 else 0.0

        task_metrics = TaskMetrics(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            remaining_tasks=remaining_tasks,
            percentage=task_percentage,
        )

        # 3. Time progress metrics
        tasks_with_duration = [t for t in all_tasks if t.estimated_minutes is not None]
        if tasks_with_duration:
            total_planned_minutes = sum(t.estimated_minutes for t in tasks_with_duration)
            completed_minutes = sum(t.estimated_minutes for t in tasks_with_duration if t.is_completed)
            remaining_minutes = max(0, total_planned_minutes - completed_minutes)
            time_percentage = (
                round((completed_minutes / total_planned_minutes) * 100.0, 1)
                if total_planned_minutes > 0
                else 0.0
            )
            time_metrics = TimeMetrics(
                total_planned_minutes=total_planned_minutes,
                completed_minutes=completed_minutes,
                remaining_minutes=remaining_minutes,
                percentage=time_percentage,
            )
        else:
            time_metrics = TimeMetrics(
                total_planned_minutes=None,
                completed_minutes=None,
                remaining_minutes=None,
                percentage=None,
            )

        # 4. Streak system
        productive_date_set = set()
        for t in all_tasks:
            if t.is_completed:
                if t.completed_at:
                    productive_date_set.add(t.completed_at.date())
                elif t.day and t.day.completed_at:
                    productive_date_set.add(t.day.completed_at.date())
                elif t.day and t.day.date:
                    productive_date_set.add(t.day.date)

        productive_dates = sorted(productive_date_set)
        last_productive_date = productive_dates[-1] if productive_dates else None

        if not productive_dates:
            best_days = 0
            current_days = 0
        else:
            # Best streak: longest consecutive sequence of calendar days
            best_days = 1
            current_run = 1
            for i in range(1, len(productive_dates)):
                if productive_dates[i] == productive_dates[i - 1] + timedelta(days=1):
                    current_run += 1
                    best_days = max(best_days, current_run)
                else:
                    current_run = 1

            # Current streak: count backwards from reference_date or reference_date - 1
            anchor = None
            if reference_date in productive_date_set:
                anchor = reference_date
            elif (reference_date - timedelta(days=1)) in productive_date_set:
                anchor = reference_date - timedelta(days=1)

            if anchor is None:
                current_days = 0
            else:
                current_days = 0
                check_date = anchor
                while check_date in productive_date_set:
                    current_days += 1
                    check_date -= timedelta(days=1)

        streak_metrics = StreakMetrics(
            current_days=current_days,
            best_days=best_days,
            last_productive_date=last_productive_date,
        )

        # 5. Momentum classification
        is_roadmap_complete = (
            total_days > 0
            and completed_days == total_days
            and total_tasks > 0
            and completed_tasks == total_tasks
        )

        if is_roadmap_complete:
            momentum_metrics = MomentumMetrics(
                status=MomentumStatus.COMPLETE,
                label="Roadmap Complete",
                description="All planned roadmap days and tasks are finished.",
            )
        else:
            recent_start = reference_date - timedelta(days=6)
            recent_end = reference_date
            prev_start = reference_date - timedelta(days=13)
            prev_end = reference_date - timedelta(days=7)

            recent_completions = 0
            prev_completions = 0

            for t in all_tasks:
                if t.is_completed:
                    t_date = None
                    if t.completed_at:
                        t_date = t.completed_at.date()
                    elif t.day and t.day.completed_at:
                        t_date = t.day.completed_at.date()
                    elif t.day and t.day.date:
                        t_date = t.day.date

                    if t_date:
                        if recent_start <= t_date <= recent_end:
                            recent_completions += 1
                        elif prev_start <= t_date <= prev_end:
                            prev_completions += 1

            if recent_completions == 0:
                if completed_tasks > 0:
                    momentum_metrics = MomentumMetrics(
                        status=MomentumStatus.PAUSED,
                        label="Momentum Paused",
                        description="No roadmap tasks completed in the last 7 days.",
                    )
                else:
                    momentum_metrics = MomentumMetrics(
                        status=MomentumStatus.STEADY,
                        label="Steady Progress",
                        description="Ready to build roadmap momentum.",
                    )
            else:
                if prev_completions == 0 or recent_completions > prev_completions:
                    momentum_metrics = MomentumMetrics(
                        status=MomentumStatus.BUILDING,
                        label="Building Momentum",
                        description=f"Completion pace increased ({recent_completions} tasks finished this week vs {prev_completions} prior).",
                    )
                elif recent_completions < prev_completions:
                    momentum_metrics = MomentumMetrics(
                        status=MomentumStatus.SLOWING,
                        label="Pace Slowing",
                        description=f"Activity has tapered ({recent_completions} tasks finished this week vs {prev_completions} prior).",
                    )
                else:
                    momentum_metrics = MomentumMetrics(
                        status=MomentumStatus.STEADY,
                        label="Steady Progress",
                        description=f"Maintaining consistent pace ({recent_completions} tasks finished this week).",
                    )

        # 6. Milestones calculation
        completed_days_with_time = []
        for d in days:
            if d.status == DayStatus.COMPLETED:
                t_comp = d.completed_at or max((t.completed_at for t in d.tasks if t.completed_at), default=None)
                completed_days_with_time.append((d, t_comp))

        # Sort completed days by timestamp if available
        completed_days_with_time.sort(
            key=lambda item: item[1] if item[1] else datetime.min.replace(tzinfo=timezone.utc)
        )

        milestones: List[Milestone] = []

        # Milestone 1: First Task Completed
        first_task_achieved = completed_tasks >= 1
        first_task_at = min((t.completed_at for t in all_tasks if t.is_completed and t.completed_at), default=None)
        milestones.append(
            Milestone(
                id="first_task",
                title="First Task Completed",
                description="Completed your first roadmap task.",
                achieved=first_task_achieved,
                achieved_at=first_task_at,
            )
        )

        # Milestone 2: First Day Completed
        first_day_achieved = completed_days >= 1
        first_day_at = completed_days_with_time[0][1] if completed_days_with_time else None
        milestones.append(
            Milestone(
                id="first_day",
                title="First Day Completed",
                description="Finished all tasks for an entire day.",
                achieved=first_day_achieved,
                achieved_at=first_day_at,
            )
        )

        # Helper to find completion timestamp for percentage thresholds
        def find_threshold_timestamp(threshold_pct: float) -> Optional[datetime]:
            for idx, (_, t_comp) in enumerate(completed_days_with_time, start=1):
                if (idx / total_days) * 100.0 >= threshold_pct:
                    return t_comp
            return None

        # Milestone 3: 25% Roadmap Completed
        m25_achieved = day_percentage >= 25.0
        milestones.append(
            Milestone(
                id="roadmap_25",
                title="25% Roadmap Completed",
                description="Completed one-quarter of your roadmap.",
                achieved=m25_achieved,
                achieved_at=find_threshold_timestamp(25.0) if m25_achieved else None,
            )
        )

        # Milestone 4: 50% Roadmap Completed
        m50_achieved = day_percentage >= 50.0
        milestones.append(
            Milestone(
                id="roadmap_50",
                title="50% Roadmap Completed",
                description="Halfway through your learning plan.",
                achieved=m50_achieved,
                achieved_at=find_threshold_timestamp(50.0) if m50_achieved else None,
            )
        )

        # Milestone 5: 75% Roadmap Completed
        m75_achieved = day_percentage >= 75.0
        milestones.append(
            Milestone(
                id="roadmap_75",
                title="75% Roadmap Completed",
                description="Entering the final stretch of your roadmap.",
                achieved=m75_achieved,
                achieved_at=find_threshold_timestamp(75.0) if m75_achieved else None,
            )
        )

        # Milestone 6: Roadmap Completed
        m_complete_achieved = total_days > 0 and completed_days == total_days
        m_complete_at = completed_days_with_time[-1][1] if (m_complete_achieved and completed_days_with_time) else None
        milestones.append(
            Milestone(
                id="roadmap_completed",
                title="Roadmap Completed",
                description="Finished every day and task on this roadmap.",
                achieved=m_complete_achieved,
                achieved_at=m_complete_at,
            )
        )

        # 7. Recent activity feed (newest first, bounded list)
        activities: List[RecentProgressActivity] = []

        for t in all_tasks:
            if t.is_completed and t.completed_at:
                activities.append(
                    RecentProgressActivity(
                        id=f"task_{t.id}",
                        event_type="TASK_COMPLETED",
                        title=f"Completed \"{t.title}\"",
                        description=f"Day {t.day.day_number}" if t.day else None,
                        timestamp=t.completed_at,
                    )
                )

        for d in days:
            if d.status == DayStatus.COMPLETED and d.completed_at:
                activities.append(
                    RecentProgressActivity(
                        id=f"day_{d.id}",
                        event_type="DAY_COMPLETED",
                        title=f"Completed Day {d.day_number}",
                        description=f"All {len(d.tasks)} tasks finished",
                        timestamp=d.completed_at,
                    )
                )

        for m in milestones:
            if m.achieved and m.achieved_at:
                activities.append(
                    RecentProgressActivity(
                        id=f"milestone_{m.id}",
                        event_type="MILESTONE_REACHED",
                        title=f"Reached milestone: {m.title}",
                        description=m.description,
                        timestamp=m.achieved_at,
                    )
                )

        # Sort newest first
        activities.sort(key=lambda a: a.timestamp, reverse=True)
        recent_activity = activities[:10]

        return RoadmapMomentumResponse(
            roadmap_id=roadmap.id,
            completion=completion_metrics,
            tasks=task_metrics,
            time=time_metrics,
            streak=streak_metrics,
            momentum=momentum_metrics,
            milestones=milestones,
            recent_activity=recent_activity,
        )


progress_service = ProgressService()
