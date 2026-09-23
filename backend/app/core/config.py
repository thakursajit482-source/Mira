from typing import List, Union, Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Mira"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: Optional[bool] = None
    LOG_LEVEL: str = "INFO"
    ENABLE_DOCS: Optional[bool] = None
    API_V1_STR: str = "/api/v1"

    # CORS origins: accepts either a list of strings or a comma-separated string
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # Database Configuration
    # Uses SQLite fallback for local development if DATABASE_URL is not set in .env
    DATABASE_URL: str = "sqlite:///./mira_dev.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_RECYCLE: int = 3600

    # AI Configuration
    AI_PROVIDER: str = "mock"

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @model_validator(mode="after")
    def resolve_environment_defaults(self) -> "Settings":
        is_prod = self.ENVIRONMENT.lower() == "production"

        if self.DEBUG is None:
            self.DEBUG = not is_prod

        if self.ENABLE_DOCS is None:
            self.ENABLE_DOCS = not is_prod

        if not self.LOG_LEVEL:
            self.LOG_LEVEL = "INFO" if is_prod else "DEBUG"

        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
