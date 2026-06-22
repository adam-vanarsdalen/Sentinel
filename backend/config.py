from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel"
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    openai_api_key: str = ""

    secret_key: str = "change-me-in-production"
    environment: str = "development"
    log_level: str = "INFO"

    grounding_block_threshold: float = 0.5
    grounding_warn_threshold: float = 0.8

    anomaly_baseline_days: int = 7
    anomaly_log_sigma: float = 2.5
    anomaly_throttle_sigma: float = 3.5
    anomaly_pause_sigma: float = 5.0
    anomaly_terminate_sigma: float = 7.0


settings = Settings()
