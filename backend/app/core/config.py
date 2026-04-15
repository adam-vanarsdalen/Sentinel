from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"  # "development" | "production"
    app_version: str = "0.1.0"

    database_url: str = "postgresql+psycopg://sentinel:sentinel@localhost:5432/sentinel"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev"
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
            if self.jwt_secret == "dev":
                raise ValueError("JWT_SECRET is set to insecure default 'dev' in production.")
            if not (self.sentinel_secret_key or "").strip():
                raise ValueError("SENTINEL_SECRET_KEY must be set in production.")
            if "*" in self.cors_origins_list:
                raise ValueError("CORS_ORIGINS includes '*' in production.")
        return self


settings = Settings()
