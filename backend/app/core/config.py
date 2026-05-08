from __future__ import annotations

from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


MIN_PRODUCTION_SECRET_LENGTH = 32
DEFAULT_DEMO_PASSWORDS = {"ChangeMe!12345"}


def _is_localhost_origin(origin: str) -> bool:
    value = (origin or "").strip().lower()
    if not value:
        return False

    parsed = urlparse(value)
    host = parsed.hostname
    if not host and "://" not in value:
        host = value.split("/", 1)[0].split(":", 1)[0]

    return host == "localhost" or host == "127.0.0.1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"  # "development" | "production"
    app_version: str = "0.1.0"

    database_url: str = "postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinel"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev_jwt_secret_change_me_32_chars"
    sentinel_secret_key: str | None = None
    jwt_issuer: str = "sentinel"
    jwt_audience: str = "sentinel-ui"
    access_token_expires_minutes: int = 480

    cors_origins: str = "http://localhost:3000"
    sentinel_preset: str = "general"

    @property
    def cors_origins_list(self) -> list[str]:
        return [s.strip() for s in (self.cors_origins or "").split(",") if s.strip()]

    provider_default: str = "mock"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str | None = None
    ollama_enabled: bool = False
    ollama_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434/v1/"
    ollama_default_model: str = "gpt-oss:120b-cloud"

    rate_limit_tenant_per_minute: int = 600
    rate_limit_apikey_per_minute: int = 120

    seed_demo: bool = False
    demo_super_admin_email: str = "platform-admin@example.com"
    demo_super_admin_password: str = "ChangeMe!12345"
    demo_tenant_admin_email: str = "admin@demoorg.com"
    demo_tenant_admin_password: str = "ChangeMe!12345"

    store_redacted_snippets_default: bool = False
    store_raw_content_default: bool = False

    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_user: str | None = None
    smtp_password: str | None = None

    metrics_token: str | None = None

    @model_validator(mode="after")
    def _validate_production(self):
        env = (self.environment or "").strip().lower()
        if env == "production":
            jwt_secret = (self.jwt_secret or "").strip()
            if not jwt_secret:
                raise ValueError("JWT_SECRET must be set in production.")
            if jwt_secret.lower() == "dev":
                raise ValueError("JWT_SECRET is set to insecure default 'dev' in production.")
            if len(jwt_secret) < MIN_PRODUCTION_SECRET_LENGTH:
                raise ValueError(f"JWT_SECRET must be at least {MIN_PRODUCTION_SECRET_LENGTH} characters in production.")

            sentinel_secret_key = (self.sentinel_secret_key or "").strip()
            if not sentinel_secret_key:
                raise ValueError("SENTINEL_SECRET_KEY must be set in production.")
            if len(sentinel_secret_key) < MIN_PRODUCTION_SECRET_LENGTH:
                raise ValueError(f"SENTINEL_SECRET_KEY must be at least {MIN_PRODUCTION_SECRET_LENGTH} characters in production.")

            if any("*" in origin for origin in self.cors_origins_list):
                raise ValueError("CORS_ORIGINS includes '*' in production.")
            if any(_is_localhost_origin(origin) for origin in self.cors_origins_list):
                raise ValueError("CORS_ORIGINS includes localhost or 127.0.0.1 in production.")

            if self.seed_demo:
                raise ValueError("SEED_DEMO must be disabled in production.")
            if (self.demo_super_admin_password or "").strip() in DEFAULT_DEMO_PASSWORDS:
                raise ValueError("DEMO_SUPER_ADMIN_PASSWORD is set to a default value in production.")
            if (self.demo_tenant_admin_password or "").strip() in DEFAULT_DEMO_PASSWORDS:
                raise ValueError("DEMO_TENANT_ADMIN_PASSWORD is set to a default value in production.")

            if (self.provider_default or "").strip().lower() == "mock":
                raise ValueError("PROVIDER_DEFAULT=mock is not allowed in production.")

            if not (self.metrics_token or "").strip():
                raise ValueError("METRICS_TOKEN must be set in production because /metrics is exposed.")
        return self


settings = Settings()
