"""Application settings via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "prototype-name"
    app_env: str = "development"
    log_level: str = "INFO"

    # LLM
    anthropic_api_key: str = ""

    # Database
    database_url: str = "postgresql://agent:agent@localhost:5432/agent_db"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Auth
    jwt_secret: str = "change-me-in-production"

    # Langfuse
    langfuse_public_key: str = "pk-lf-local"
    langfuse_secret_key: str = "sk-lf-local"
    langfuse_host: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
