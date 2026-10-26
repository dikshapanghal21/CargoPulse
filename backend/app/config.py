from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CargoPulse API"
    environment: str = "development"
    debug: bool = False

    database_url: str = "postgresql+psycopg://cargopulse:cargopulse@localhost:5432/cargopulse"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # Overdue detection
    overdue_scan_interval_seconds: int = 300
    overdue_grace_minutes: int = 0
    overdue_lock_timeout_seconds: int = 120

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        if isinstance(value, str):
            if value.strip().startswith("["):
                import json

                return json.loads(value)
            return [v.strip() for v in value.split(",") if v.strip()]
        return value

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
