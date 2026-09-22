from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    status: str = Field(..., description="Application health status", examples=["ok"])
    app_name: str = Field(..., description="Application name", examples=["Mira"])
    environment: str = Field(..., description="Current running environment", examples=["development"])
    version: str = Field(..., description="Application version", examples=["0.1.0"])
