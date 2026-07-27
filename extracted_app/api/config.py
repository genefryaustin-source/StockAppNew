"""
StockApp Platform API Configuration
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic import field_validator
from pydantic_settings import BaseSettings

from pydantic_settings import SettingsConfigDict


class Settings(BaseSettings):

    """
    Central configuration for the API.

    Environment variables automatically override
    the defaults below.

    """

    # -----------------------------------------------------
    # Platform
    # -----------------------------------------------------

    application_name: str = "StockApp Platform API"

    environment: str = "development"

    debug: bool = True

    # -----------------------------------------------------
    # API
    # -----------------------------------------------------

    host: str = "0.0.0.0"

    port: int = 8000

    api_prefix: str = "/api"

    api_version: str = "v1"

    # -----------------------------------------------------
    # Security
    # -----------------------------------------------------

    jwt_secret: str = Field(

        default="CHANGE_ME",

        alias="JWT_SECRET",

    )

    jwt_algorithm: str = "HS256"

    jwt_expiration_minutes: int = 60

    # Refresh tokens are long-lived by design (mobile clients shouldn't
    # need to re-enter credentials every hour just because the access
    # token expired) -- 30 days is a common default; each use rotates
    # to a new token (see api/auth/refresh_tokens.py), so this is the
    # maximum time a single stolen-but-unused refresh token stays valid,
    # not how often re-login is required in practice.
    refresh_token_expiration_days: int = 30

    api_key_header: str = "X-API-Key"

    # -----------------------------------------------------
    # Database
    # -----------------------------------------------------

    database_url: str = Field(

        default="",

        alias="DATABASE_URL",

    )

    # -----------------------------------------------------
    # Logging
    # -----------------------------------------------------

    log_level: str = "INFO"

    structured_logging: bool = True

    # -----------------------------------------------------
    # CORS
    # -----------------------------------------------------

    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8501",
        # Expo Web
        "http://localhost:8081",
        "http://127.0.0.1:8081",
    ]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return value


    allowed_methods: list[str] = [

        "*",

    ]

    allowed_headers: list[str] = [

        "*",

    ]

    # -----------------------------------------------------
    # Rate Limiting
    # -----------------------------------------------------

    requests_per_minute: int = 100

    requests_per_day: int = 10000

    # -----------------------------------------------------
    # OpenAPI
    # -----------------------------------------------------

    enable_docs: bool = True

    enable_redoc: bool = True

    enable_openapi: bool = True

    # -----------------------------------------------------
    # Future Runtime
    # -----------------------------------------------------

    enable_websockets: bool = True

    enable_background_tasks: bool = True

    enable_scheduler: bool = True

    enable_metrics: bool = True

    # -----------------------------------------------------

    model_config = SettingsConfigDict(

        env_file=".env",

        env_file_encoding="utf-8",

        extra="ignore",

        case_sensitive=False,

        populate_by_name=True,

    )


@lru_cache
def get_settings() -> Settings:

    """
    Singleton settings instance.
    """

    return Settings()


settings = get_settings()