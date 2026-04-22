"""Application settings via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "customer-support-triage"
    app_env: str = "development"
    log_level: str = "INFO"

    # LLM
    anthropic_api_key: str = ""
    classifier_model: str = "claude-haiku-4-5-20251001"
    specialist_model: str = "claude-sonnet-4-6-20250514"

    # Routing
    escalation_threshold: float = 0.7

    # Database
    database_url: str = "postgresql+asyncpg://agent:agent@localhost:5432/agent_db"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "support_kb"

    # Auth
    jwt_secret: str = "change-me-in-production"

    # Langfuse
    langfuse_public_key: str = "pk-lf-local"
    langfuse_secret_key: str = "sk-lf-local"
    langfuse_host: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
