from fastapi import APIRouter
from backend.app.core.config import settings
from backend.app.schemas.health import HealthCheckResponse

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse, summary="Health Check")
async def health_check() -> HealthCheckResponse:
    """Return health status and basic application metadata."""
    return HealthCheckResponse(
        status="ok",
        app_name=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        version=settings.VERSION,
    )
