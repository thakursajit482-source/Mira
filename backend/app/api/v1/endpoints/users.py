from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.user import UserPreferencesResponse, UserPreferencesUpdate
from backend.app.services.user_service import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/preferences",
    response_model=UserPreferencesResponse,
    summary="Get User Preferences & Profile",
    description="Retrieve personal preferences, available capacity, appearance, and notification settings.",
)
def get_user_preferences(
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db),
) -> UserPreferencesResponse:
    """Retrieve unified user preferences and profile information."""
    return user_service.get_preferences(db=db, user_id=user_id)


@router.patch(
    "/preferences",
    response_model=UserPreferencesResponse,
    summary="Update User Preferences",
    description="Update personal settings including daily study minutes, theme, and roadmap behaviors.",
)
def update_user_preferences(
    update_in: UserPreferencesUpdate,
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db),
) -> UserPreferencesResponse:
    """Update user preferences and profile information."""
    return user_service.update_preferences(db=db, user_id=user_id, update_in=update_in)
