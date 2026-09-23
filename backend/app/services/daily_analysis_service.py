from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.app.models.roadmap import Roadmap
from backend.app.models.day import Day
from backend.app.models.task import Task
from backend.app.models.enums import DayStatus, TaskStatus
from backend.app.schemas.daily_analysis import (
    DailyWorkloadStatus,
    DailyWorkloadAnalysisResponse,
)


class DailyAnalysisService:
    """Service providing deterministic daily workload analysis for smart daily planning."""

    @staticmethod
    def analyze_daily_workload(
        db: Session,
        roadmap_id: int,
        day_number: Optional[int] = None,
    ) -> DailyWorkloadAnalysisResponse:
        """
        Deterministically analyze a roadmap's current day workload against user capacity.
        Strictly read-only; never mutates the database.
        """
        stmt = (
            select(Roadmap)
            .options(
                selectinload(Roadmap.days).selectinload(Day.tasks),
                selectinload(Roadmap.user),
            )
            .where(Roadmap.id == roadmap_id)
        )
        roadmap = db.scalar(stmt)
        if not roadmap:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roadmap with id {roadmap_id} not found",
            )

        if not roadmap.days:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roadmap with id {roadmap_id} has no days",
            )

        # 1. Authoritative available daily minutes from User
        available_minutes = (
            roadmap.user.daily_available_minutes
            if (roadmap.user and roadmap.user.daily_available_minutes and roadmap.user.daily_available_minutes > 0)
            else 120
        )

        sorted_days = sorted(roadmap.days, key=lambda d: d.day_number)

        # 2. Determine target day
        if day_number is not None:
            target_day = next((d for d in sorted_days if d.day_number == day_number), None)
            if not target_day:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Day {day_number} not found in roadmap {roadmap_id}",
                )
        else:
            # First look for active / in-progress day
            active = next(
                (d for d in sorted_days if d.status in (DayStatus.CURRENT, DayStatus.IN_PROGRESS)),
                None,
            )
            if not active:
                # Look for AT_RISK day
                active = next((d for d in sorted_days if d.status == DayStatus.AT_RISK), None)
            if not active:
                # First incomplete day
                active = next((d for d in sorted_days if d.status != DayStatus.COMPLETED), None)
            if not active:
                # If all completed, target the final day
                active = sorted_days[-1]
            target_day = active

        # 3. Analyze tasks of target day
        tasks = sorted(target_day.tasks or [], key=lambda t: t.order_index)
        total_task_count = len(tasks)
        completed_tasks = [t for t in tasks if t.is_completed or t.status == TaskStatus.COMPLETED]
        incomplete_tasks = [t for t in tasks if not (t.is_completed or t.status == TaskStatus.COMPLETED)]

        completed_task_count = len(completed_tasks)
        remaining_task_count = len(incomplete_tasks)

        completed_minutes = sum(t.estimated_minutes for t in completed_tasks)
        remaining_minutes = sum(t.estimated_minutes for t in incomplete_tasks)
        total_minutes = completed_minutes + remaining_minutes

        is_all_completed = target_day.status == DayStatus.COMPLETED or (
            total_task_count > 0 and remaining_task_count == 0
        )

        # 4. Deterministic status & recommendation calculation
        if is_all_completed:
            workload_status = DailyWorkloadStatus.COMPLETE
            remaining_capacity = available_minutes
            overage = 0
            recommendation = (
                f"Day {target_day.day_number} complete. Nothing else is required today."
            )
        elif remaining_minutes > available_minutes:
            workload_status = DailyWorkloadStatus.OVER_CAPACITY
            overage = remaining_minutes - available_minutes
            remaining_capacity = 0
            recommendation = (
                f"Today's plan is {overage} min over your available time ({available_minutes} min). "
                "Consider previewing a lighter schedule."
            )
        elif remaining_minutes >= int(0.85 * available_minutes) or (available_minutes - remaining_minutes) <= 15:
            workload_status = DailyWorkloadStatus.TIGHT
            overage = 0
            remaining_capacity = available_minutes - remaining_minutes
            recommendation = (
                f"Today's plan is tight with {remaining_capacity} min to spare. "
                f"You have {remaining_minutes} min of work scheduled."
            )
        else:
            workload_status = DailyWorkloadStatus.ON_TRACK
            overage = 0
            remaining_capacity = available_minutes - remaining_minutes
            recommendation = (
                f"You have {remaining_minutes} minutes of work and {available_minutes} minutes available today. "
                "Your current plan fits comfortably within your capacity."
            )

        # 5. Future workload secondary awareness (Section 10)
        tomorrow_day = next(
            (d for d in sorted_days if d.day_number == target_day.day_number + 1),
            None,
        )
        tomorrow_minutes = (
            sum(t.estimated_minutes for t in tomorrow_day.tasks) if tomorrow_day else None
        )

        future_incomplete = [
            d
            for d in sorted_days
            if d.day_number > target_day.day_number and d.status != DayStatus.COMPLETED
        ][:3]

        if future_incomplete:
            total_future_mins = sum(
                sum(t.estimated_minutes for t in d.tasks) for d in future_incomplete
            )
            upcoming_average_minutes = round(total_future_mins / len(future_incomplete))
        else:
            upcoming_average_minutes = None

        return DailyWorkloadAnalysisResponse(
            roadmap_id=roadmap.id,
            day_number=target_day.day_number,
            day_id=target_day.id,
            date=target_day.date,
            status=workload_status,
            remaining_task_count=remaining_task_count,
            completed_task_count=completed_task_count,
            total_task_count=total_task_count,
            remaining_minutes=remaining_minutes,
            completed_minutes=completed_minutes,
            total_minutes=total_minutes,
            available_minutes=available_minutes,
            remaining_capacity_minutes=remaining_capacity,
            overage_minutes=overage,
            recommendation=recommendation,
            tomorrow_minutes=tomorrow_minutes,
            upcoming_average_minutes=upcoming_average_minutes,
        )


daily_analysis_service = DailyAnalysisService()
