from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1.router import api_router
from backend.app.core.config import settings
from backend.app.schemas.health import HealthCheckResponse


def create_application() -> FastAPI:
    """Application factory creating the FastAPI app instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Personal AI Roadmap and Progress Management System",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API v1 router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    # Root health check endpoint for quick ping
    @app.get("/health", response_model=HealthCheckResponse, tags=["health"])
    async def root_health() -> HealthCheckResponse:
        """Root health check endpoint."""
        return HealthCheckResponse(
            status="ok",
            app_name=settings.PROJECT_NAME,
            environment=settings.ENVIRONMENT,
            version=settings.VERSION,
        )

    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint returning basic application info."""
        return {
            "app": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_application()
