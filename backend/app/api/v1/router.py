from fastapi import APIRouter
from backend.app.api.v1.endpoints import health, roadmaps, days, tasks

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(roadmaps.router)
api_router.include_router(days.router)
api_router.include_router(tasks.router)
