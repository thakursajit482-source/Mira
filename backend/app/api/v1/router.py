from fastapi import APIRouter
from backend.app.api.v1.endpoints import health, roadmaps

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(roadmaps.router)
