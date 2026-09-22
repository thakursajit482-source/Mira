from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.task import TaskResponse
from backend.app.services.progress_service import progress_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get Task",
    description="Retrieve a task and its current completion state.",
)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Retrieve a task by ID."""
    return progress_service.get_task(db, task_id)


@router.patch(
    "/{task_id}/complete",
    response_model=TaskResponse,
    summary="Complete Task",
    description="Mark a task as completed and update parent Day status. Idempotent.",
)
def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Mark a task as completed."""
    return progress_service.complete_task(db, task_id)


@router.patch(
    "/{task_id}/uncomplete",
    response_model=TaskResponse,
    summary="Uncomplete Task",
    description="Mark a task as incomplete and update parent Day status. Idempotent.",
)
def uncomplete_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> TaskResponse:
    """Mark a task as incomplete."""
    return progress_service.uncomplete_task(db, task_id)
