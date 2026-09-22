from typing import Dict, Type
from backend.app.core.config import settings
from backend.app.ai.base import AIProvider
from backend.app.ai.providers.mock import MockAIProvider
from backend.app.ai.schemas import RoadmapGenerationRequest, GeneratedRoadmap
from backend.app.ai.validator import AIValidator


class AIService:
    """
    AI Service coordinating provider execution and output validation.
    
    CORE ARCHITECTURAL INVARIANT:
    This service is strictly decoupled from database access and persistence.
    It takes requests, calls the configured AIProvider, validates the output,
    and returns verified domain structures.
    """

    def __init__(self):
        self._providers: Dict[str, Type[AIProvider]] = {
            "mock": MockAIProvider,
        }

    def get_provider(self, provider_name: str = None) -> AIProvider:
        """Instantiate the configured AI provider."""
        name = (provider_name or settings.AI_PROVIDER).lower().strip()
        provider_cls = self._providers.get(name)
        if not provider_cls:
            raise ValueError(f"Unknown or unsupported AI provider: '{name}'")
        return provider_cls()

    def generate_roadmap(
        self,
        request: RoadmapGenerationRequest,
        effective_daily_capacity: int,
        provider_name: str = None,
    ) -> GeneratedRoadmap:
        """
        Generate and validate a structured roadmap proposal.
        Throws AIValidationError if output is malformed or exceeds capacity.
        """
        provider = self.get_provider(provider_name)
        generated = provider.generate_roadmap(request, effective_daily_capacity)

        # Validate untrusted AI output
        AIValidator.validate(generated, request, effective_daily_capacity)

        return generated


ai_service = AIService()
