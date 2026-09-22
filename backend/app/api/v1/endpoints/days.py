from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.day import DayResponse
from backend.app.services.progress_service import progress_service

router = APIRouter(prefix="/days", tags=["days"])


@router.get(
    "/{day_id}",
    response_model=DayResponse,
    summary="Get Day",
    description="Retrieve a Day level and its ordered tasks.",
)
def get_day(
    day_id: int,
    db: Session = Depends(get_db),
) -> DayResponse:
    """Retrieve day by ID with ordered tasks."""
    return progress_service.get_day(db, day_id)
