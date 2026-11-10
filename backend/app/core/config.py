from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    app_name: str = "AI Marketplace API"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    database_url: str = "postgresql+psycopg://marketplace:marketplace@localhost:5433/marketplace"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev-only-secret-change-me-in-production-0123456789"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 7

    # llm_provider = mock | gemini | ollama ; embedding_provider = hash | gemini | ollama
    llm_provider: str = "mock"
    embedding_provider: str = "hash"
    embedding_dim: int = 768
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash"
    gemini_embedding_model: str = "gemini-embedding-001"
    # Overrides the embedding provider's cut-off below which a product with no keyword hit counts as unrelated.
    semantic_min_similarity: float | None = None
    gemini_disable_thinking: bool = True  # faster; set false if your chosen model rejects thinkingConfig
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    ollama_embedding_model: str = "nomic-embed-text"
    llm_timeout_seconds: float = 20.0

    upload_dir: str = "uploads"
    max_upload_mb: int = 5

    payment_webhook_secret: str = "dev-webhook-secret"
    order_reservation_minutes: int = 30

    # Run Celery tasks inline (no broker needed). Set false when a worker is running.
    celery_eager: bool = True
    ai_search_rate_limit_per_minute: int = 30
    # How long the discovered listing-spec schema is cached (0 disables; tests use 0).
    spec_catalog_ttl_seconds: int = 60

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _require_real_secrets_in_production(self):
        if self.is_production:
            if self.jwt_secret.startswith("dev-only") or len(self.jwt_secret) < 32:
                raise ValueError("JWT_SECRET must be set to a random value of at least 32 characters in production")
            if self.payment_webhook_secret == "dev-webhook-secret":
                raise ValueError("PAYMENT_WEBHOOK_SECRET must be set in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
