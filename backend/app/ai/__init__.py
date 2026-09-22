"""AI Integration Layer for Mira.

CORE ARCHITECTURAL RULE:
AI is a scheduling and organization assistant, not an autonomous authority.
- AI accepts user-supplied roadmap content, target duration, and constraints.
- AI analyzes topics, dependencies, and approximate effort.
- AI returns strictly structured JSON data (validated against Pydantic schemas).
- AI NEVER directly accesses or modifies the database.
- AI proposals are passed through validation and the deterministic Roadmap Engine.
"""

from backend.app.ai.base import AIProvider
from backend.app.ai.schemas import (
    RoadmapGenerationRequest,
    GeneratedTask,
    GeneratedDay,
    GeneratedRoadmap,
)
from backend.app.ai.validator import AIValidator, AIValidationError
from backend.app.ai.service import AIService, ai_service
from backend.app.ai.providers.mock import MockAIProvider

__all__ = [
    "AIProvider",
    "RoadmapGenerationRequest",
    "GeneratedTask",
    "GeneratedDay",
    "GeneratedRoadmap",
    "AIValidator",
    "AIValidationError",
    "AIService",
    "ai_service",
    "MockAIProvider",
]
