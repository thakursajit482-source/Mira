from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.schemas.roadmap import (
    RoadmapCreate,
    RoadmapUpdate,
    RoadmapResponse,
    RoadmapDetailResponse,
)
from backend.app.schemas.progress import RoadmapProgressResponse
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
from backend.app.schemas.history import RoadmapHistoryResponse
from backend.app.schemas.daily_analysis import DailyWorkloadAnalysisResponse
from backend.app.schemas.momentum import RoadmapMomentumResponse
from backend.app.ai.schemas import RoadmapGenerationRequest, GeneratedRoadmap
from backend.app.ai.service import ai_service
from backend.app.ai.validator import AIValidationError
from backend.app.services.roadmap_service import roadmap_service
from backend.app.services.progress_service import progress_service
from backend.app.services.daily_analysis_service import daily_analysis_service

router = APIRouter(prefix="/roadmaps", tags=["roadmaps"])


@router.post(
    "/generate/preview",
    response_model=GeneratedRoadmap,
    status_code=status.HTTP_200_OK,
    summary="Preview AI-Generated Roadmap",
    description="Generate and validate a structured roadmap proposal without persisting to the database.",
)
def preview_generate_roadmap(
    request: RoadmapGenerationRequest,
    db: Session = Depends(get_db),
) -> GeneratedRoadmap:
    """Generate and validate a structured roadmap proposal without mutating the database."""
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
        return ai_service.generate_roadmap(request, effective_daily_capacity)
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


@router.post(
    "/generate",
    response_model=RoadmapDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Roadmap with AI",
    description="Generate and persist a structured, day-wise roadmap from a goal using AI assistance.",
)
def generate_roadmap(
    request: RoadmapGenerationRequest,
    db: Session = Depends(get_db),
) -> RoadmapDetailResponse:
    """Generate and persist a new roadmap from user goal and constraints."""
    roadmap = roadmap_service.generate_and_create_roadmap(db, request)
    return RoadmapDetailResponse.model_validate(roadmap)


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


@router.get(
    "/{roadmap_id}/history",
    response_model=RoadmapHistoryResponse,
    summary="Get Roadmap History",
    description="Retrieve chronological change timeline and audit log for a roadmap, newest changes first.",
)
def get_roadmap_history(
    roadmap_id: int,
    db: Session = Depends(get_db),
) -> RoadmapHistoryResponse:
    """Get roadmap change history."""
    return roadmap_service.get_roadmap_history(db, roadmap_id)


@router.get(
    "/{roadmap_id}/daily-analysis",
    response_model=DailyWorkloadAnalysisResponse,
    summary="Get Daily Workload Analysis",
    description="Deterministically analyze current day workload against available capacity, returning status, task counts, and smart recommendations.",
)
def get_daily_workload_analysis(
    roadmap_id: int,
    day_number: Optional[int] = Query(None, description="Optional specific day number to analyze"),
    db: Session = Depends(get_db),
) -> DailyWorkloadAnalysisResponse:
    """Get deterministic daily workload analysis."""
    return daily_analysis_service.analyze_daily_workload(db, roadmap_id, day_number)


@router.get(
    "/{roadmap_id}/momentum",
    response_model=RoadmapMomentumResponse,
    summary="Get Roadmap Momentum & Progress",
    description="Retrieve deterministic progress metrics, streak tracking, momentum classification, milestones, and recent activity.",
)
def get_roadmap_momentum(
    roadmap_id: int,
    db: Session = Depends(get_db),
) -> RoadmapMomentumResponse:
    """Get calculated roadmap progress and momentum metrics."""
    return progress_service.calculate_roadmap_momentum(db, roadmap_id)


@router.post(
    "/{roadmap_id}/insert/preview",
    response_model=InsertionPreviewResponse,
    summary="Preview Roadmap Insertion",
    description="Simulate inserting new content starting from the first incomplete day without mutating the database.",
)
def preview_roadmap_insertion(
    roadmap_id: int,
    request: RoadmapInsertionRequest,
    db: Session = Depends(get_db),
) -> InsertionPreviewResponse:
    """Preview insertion without database mutation."""
    return roadmap_service.preview_insertion(db, roadmap_id, request)


@router.post(
    "/{roadmap_id}/insert",
    response_model=InsertionResultResponse,
    summary="Insert Roadmap Content",
    description="Insert new roadmap content starting from the first incomplete day and shift future incomplete work.",
    responses={
        200: {"model": InsertionResultResponse, "description": "Insertion applied successfully"},
        409: {"model": InsertionResultResponse, "description": "Scheduling or capacity conflict detected"},
    },
)
def insert_roadmap_content(
    roadmap_id: int,
    request: RoadmapInsertionRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> InsertionResultResponse:
    """Apply roadmap insertion deterministically."""
    result = roadmap_service.apply_insertion(db, roadmap_id, request)
    if result.conflict:
        response.status_code = status.HTTP_409_CONFLICT
    return result


@router.post(
    "/{roadmap_id}/reschedule/preview",
    response_model=ReschedulePreviewResponse,
    summary="Preview Roadmap Rescheduling",
    description="Simulate rescheduling future incomplete tasks within user daily capacity without mutating the database.",
)
def preview_roadmap_reschedule(
    roadmap_id: int,
    request: RoadmapRescheduleRequest,
    db: Session = Depends(get_db),
) -> ReschedulePreviewResponse:
    """Preview rescheduling without database mutation."""
    return roadmap_service.preview_reschedule(db, roadmap_id, request)


@router.post(
    "/{roadmap_id}/reschedule",
    response_model=RescheduleResultResponse,
    summary="Reschedule Roadmap",
    description="Deterministically rebalance future incomplete tasks within user daily capacity while preserving completed history.",
    responses={
        200: {"model": RescheduleResultResponse, "description": "Rescheduling applied successfully"},
        409: {"model": RescheduleResultResponse, "description": "Capacity or scheduling conflict detected"},
    },
)
def reschedule_roadmap(
    roadmap_id: int,
    request: RoadmapRescheduleRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> RescheduleResultResponse:
    """Apply roadmap rescheduling deterministically."""
    result = roadmap_service.apply_reschedule(db, roadmap_id, request)
    if result.conflict:
        response.status_code = status.HTTP_409_CONFLICT
    return result


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
