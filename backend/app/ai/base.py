from abc import ABC, abstractmethod
from backend.app.ai.schemas import RoadmapGenerationRequest, GeneratedRoadmap


class AIProvider(ABC):
    """
    Abstract base class for AI roadmap generation providers.
    Decouples roadmap generation logic from specific LLM vendors (Mock, OpenAI, Anthropic, etc.).
    """

    @abstractmethod
    def generate_roadmap(self, request: RoadmapGenerationRequest, effective_daily_capacity: int) -> GeneratedRoadmap:
        """
        Generate a structured roadmap proposal from user requirements.
        Must return a structured GeneratedRoadmap instance.
        Must NOT interact with or mutate the database.
        """
        pass
