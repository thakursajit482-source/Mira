from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.schemas.roadmap import (
    RoadmapCreate,
    RoadmapUpdate,
    RoadmapResponse,
    RoadmapDetailResponse,
)
from backend.app.schemas.progress import RoadmapProgressResponse
from backend.app.services.roadmap_service import roadmap_service
from backend.app.services.progress_service import progress_service

router = APIRouter(prefix="/roadmaps", tags=["roadmaps"])


@router.post(
    "",
    response_model=RoadmapResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Roadmap",
    description="Create a new roadmap associated with an existing user.",
)
def create_roadmap(
    roadmap_in: RoadmapCreate,
    db: Session = Depends(get_db),
) -> RoadmapResponse:
    """Create a new roadmap."""
    return roadmap_service.create_roadmap(db, roadmap_in)


@router.get(
    "",
    response_model=List[RoadmapResponse],
    summary="List Roadmaps",
    description="List all roadmaps with optional user_id filter and pagination.",
)
def list_roadmaps(
    user_id: Optional[int] = Query(None, description="Filter roadmaps by owner user ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
) -> List[RoadmapResponse]:
    """List roadmaps."""
    return roadmap_service.list_roadmaps(db, user_id=user_id, skip=skip, limit=limit)


@router.get(
    "/{roadmap_id}",
    response_model=RoadmapResponse,
    summary="Get Roadmap",
    description="Retrieve roadmap metadata by ID.",
)
def get_roadmap(
    roadmap_id: int,
    db: Session = Depends(get_db),
) -> RoadmapResponse:
    """Get roadmap metadata by ID."""
    return roadmap_service.get_roadmap(db, roadmap_id)


@router.get(
    "/{roadmap_id}/details",
    response_model=RoadmapDetailResponse,
    summary="Get Roadmap Details",
    description="Retrieve complete roadmap hierarchy including Days and Tasks in deterministic order.",
)
def get_roadmap_details(
    roadmap_id: int,
    db: Session = Depends(get_db),
) -> RoadmapDetailResponse:
    """Get complete roadmap hierarchy: Roadmap -> Days -> Tasks."""
    return roadmap_service.get_roadmap_details(db, roadmap_id)


@router.get(
    "/{roadmap_id}/progress",
    response_model=RoadmapProgressResponse,
    summary="Get Roadmap Progress",
    description="Retrieve calculated progress metrics for a roadmap based on completed days vs total days.",
)
def get_roadmap_progress(
    roadmap_id: int,
    db: Session = Depends(get_db),
) -> RoadmapProgressResponse:
    """Get calculated roadmap progress."""
    return progress_service.calculate_roadmap_progress(db, roadmap_id)


@router.patch(
    "/{roadmap_id}",
    response_model=RoadmapResponse,
    summary="Update Roadmap",
    description="Update roadmap metadata. Only provided fields are updated.",
)
def update_roadmap(
    roadmap_id: int,
    roadmap_in: RoadmapUpdate,
    db: Session = Depends(get_db),
) -> RoadmapResponse:
    """Update roadmap metadata."""
    return roadmap_service.update_roadmap(db, roadmap_id, roadmap_in)


@router.delete(
    "/{roadmap_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Roadmap",
    description="Delete a roadmap and all associated days, tasks, versions, and changes.",
)
def delete_roadmap(
    roadmap_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a roadmap."""
    roadmap_service.delete_roadmap(db, roadmap_id)
