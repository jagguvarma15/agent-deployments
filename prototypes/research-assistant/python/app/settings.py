"""Application settings via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "research-assistant"
    app_env: str = "development"
    log_level: str = "INFO"
    anthropic_api_key: str = ""
    research_model: str = "claude-sonnet-4-6-20250514"
    max_react_steps: int = 10
    database_url: str = "postgresql+asyncpg://agent:agent@localhost:5432/agent_db"
    redis_url: str = "redis://localhost:6379"
    jwt_secret: str = "change-me-in-production"
    langfuse_public_key: str = "pk-lf-local"
    langfuse_secret_key: str = "sk-lf-local"
    langfuse_host: str = "http://localhost:3000"
    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
