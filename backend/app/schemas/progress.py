from pydantic import BaseModel, ConfigDict, Field


class RoadmapProgressResponse(BaseModel):
    """Schema representing calculated progress for a Roadmap."""
    roadmap_id: int = Field(..., description="ID of the roadmap")
    total_days: int = Field(..., ge=0, description="Total days in the roadmap")
    completed_days: int = Field(..., ge=0, description="Number of fully completed days")
    progress_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of days completed")
    total_tasks: int = Field(..., ge=0, description="Total tasks across all days in the roadmap")
    completed_tasks: int = Field(..., ge=0, description="Total completed tasks across all days")

    model_config = ConfigDict(from_attributes=True)
