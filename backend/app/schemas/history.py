from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

from backend.app.models.enums import RoadmapChangeType


class RoadmapChangeResponse(BaseModel):
    """Pydantic schema representing a single auditable change entry in a roadmap's history."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    roadmap_id: int
    version_id: Optional[int] = None
    version_number: Optional[int] = None
    change_type: RoadmapChangeType
    description: str
    metadata_info: Optional[Dict[str, Any]] = None
    created_at: datetime


class RoadmapHistoryResponse(BaseModel):
    """Pydantic schema wrapping the chronological list of roadmap changes."""
    roadmap_id: int
    total_changes: int
    changes: List[RoadmapChangeResponse]
