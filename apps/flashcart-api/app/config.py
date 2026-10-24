"""Typed, validated configuration. The app refuses to start with missing or unsafe settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLASHCART_", env_file=".env", extra="ignore")

    env: Literal["local", "test", "production"] = "local"
    app_version: str = "0.1.0"

    mongodb_uri: SecretStr
    mongodb_db: str = Field(default="flashcart", pattern=r"^[A-Za-z0-9_-]{1,38}$")
    mongodb_max_pool_size: int = Field(default=20, ge=1, le=200)
    mongodb_timeout_ms: int = Field(default=5000, ge=100, le=30000)

    jwt_secret: SecretStr
    # Previous secret still accepted for verification during rotation (JWT rotation, concept #47).
    jwt_secret_previous: SecretStr | None = None
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_days: int = Field(default=7, ge=1, le=30)

    cors_origins: list[str] = []
    cookie_secure: bool = True

    webhook_secret: SecretStr
    # Shared secret CloudFront adds as a header so the Lambda URL only serves traffic via the CDN.
    origin_verify_secret: SecretStr | None = None
    metrics_token: SecretStr | None = None

    max_body_bytes: int = Field(default=64 * 1024, ge=1024, le=1024 * 1024)
    request_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    rate_limit_per_minute: int = Field(default=300, ge=1)
    auth_rate_limit_per_minute: int = Field(default=10, ge=1)

    admin_email: str | None = None
    admin_password: SecretStr | None = None

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard_origin(cls, v: list[str]) -> list[str]:
        if "*" in v:
            raise ValueError("Wildcard CORS origin is not allowed (credentials are used)")
        return v

    @model_validator(mode="after")
    def _production_guards(self) -> "Settings":
        if len(self.jwt_secret.get_secret_value()) < 32:
            raise ValueError("FLASHCART_JWT_SECRET must be at least 32 characters")
        if len(self.webhook_secret.get_secret_value()) < 32:
            raise ValueError("FLASHCART_WEBHOOK_SECRET must be at least 32 characters")
        if self.env == "production":
            if not self.cookie_secure:
                raise ValueError("cookie_secure must be true in production")
            if self.origin_verify_secret is None:
                raise ValueError("FLASHCART_ORIGIN_VERIFY_SECRET is required in production")
            if any(o.startswith("http://") for o in self.cors_origins):
                raise ValueError("Plain-HTTP CORS origins are not allowed in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
