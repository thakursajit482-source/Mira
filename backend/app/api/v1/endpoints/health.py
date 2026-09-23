from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.logging import get_logger
from backend.app.schemas.health import HealthCheckResponse

router = APIRouter()
logger = get_logger("health")


@router.get("/health", response_model=HealthCheckResponse, summary="Health Check (Liveness)")
async def health_check() -> HealthCheckResponse:
    """Liveness check returning basic application metadata without external dependencies."""
    return HealthCheckResponse(
        status="ok",
        app_name=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT,
        version=settings.VERSION,
    )


@router.get("/ready", summary="Readiness Check")
def readiness_check(db: Session = Depends(get_db)):
    """Readiness check verifying database connectivity."""
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "connected",
            "environment": settings.ENVIRONMENT,
        }
    except Exception as exc:
        logger.error(f"Readiness database probe failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
