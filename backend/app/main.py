from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.core.database import SessionLocal
from backend.app.core.logging import setup_logging, get_logger
from backend.app.models.user import User
from backend.app.schemas.health import HealthCheckResponse

setup_logging()
logger = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for application startup and shutdown."""
    logger.info(f"Starting {settings.PROJECT_NAME} (environment={settings.ENVIRONMENT})")

    # Seed development user ONLY in development mode
    if settings.ENVIRONMENT.lower() == "development":
        db = SessionLocal()
        try:
            dev_user = db.query(User).filter(User.id == 1).first()
            if not dev_user:
                dev_user = User(
                    id=1,
                    email="dev@mira.local",
                    username="dev_user",
                    daily_available_minutes=120,
                    theme="system",
                    timezone="UTC",
                )
                db.add(dev_user)
                db.commit()
                logger.info("Seeded default development user (id=1)")
        except Exception as exc:
            db.rollback()
            logger.warning(f"Development user seed skipped or failed: {exc}")
        finally:
            db.close()
    else:
        logger.info(f"Skipping development seeding for environment: {settings.ENVIRONMENT}")

    yield

    logger.info(f"Shutting down {settings.PROJECT_NAME}")


def create_application() -> FastAPI:
    """Application factory creating the hardened FastAPI app instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Personal AI Roadmap and Progress Management System",
        docs_url="/docs" if settings.ENABLE_DOCS else None,
        redoc_url="/redoc" if settings.ENABLE_DOCS else None,
        lifespan=lifespan,
    )

    # Security Headers Middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response

    # Global Exception Handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"Unhandled exception processing {request.method} {request.url.path}: {exc}",
            exc_info=True,
        )
        if settings.ENVIRONMENT.lower() == "production":
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "An internal server error occurred. Please try again later."},
            )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Internal Server Error: {str(exc)}"},
        )

    # Configure CORS middleware
    has_wildcard = "*" in settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else settings.CORS_ORIGINS == "*"
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=not has_wildcard,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API v1 router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Root health check (Liveness)
    @app.get("/health", response_model=HealthCheckResponse, tags=["health"])
    async def root_health() -> HealthCheckResponse:
        """Root liveness probe."""
        return HealthCheckResponse(
            status="ok",
            app_name=settings.PROJECT_NAME,
            environment=settings.ENVIRONMENT,
            version=settings.VERSION,
        )

    # Root readiness check (Database Probe)
    @app.get("/ready", tags=["health"])
    async def root_ready():
        """Root readiness probe validating database connectivity."""
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
            return {
                "status": "ok",
                "database": "connected",
                "environment": settings.ENVIRONMENT,
            }
        except Exception as exc:
            logger.error(f"Root readiness probe failed: {exc}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "unavailable",
                    "database": "disconnected",
                    "environment": settings.ENVIRONMENT,
                },
            )

    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint returning basic application metadata."""
        return {
            "app": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/docs" if settings.ENABLE_DOCS else None,
            "health": "/health",
            "ready": "/ready",
        }

    return app


app = create_application()
