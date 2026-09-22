from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.models.task import Task
from backend.app.models.enums import DayStatus, TaskStatus
from backend.app.schemas.progress import RoadmapProgressResponse


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


progress_service = ProgressService()
