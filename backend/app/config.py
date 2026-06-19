from pathlib import Path

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).parent.parent.parent / ".env"


class Settings(BaseSettings):
    environment: str = "development"
    database_url: str
    anthropic_api_key: str
    igdb_client_id: str
    igdb_client_secret: str
    rawg_api_key: str
    steam_api_key: str = ""
    psn_npsso: SecretStr = SecretStr("")
    openxbl_api_key: SecretStr = SecretStr("")
    opencritic_api_key: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    openrouter_api_key: str = ""
    glm_api_key: str = ""
    litellm_api_base: str = ""
    secret_key: str = "change-me-in-production"
    jwt_lifetime_seconds: int = 60 * 60 * 24 * 7
    embedding_model: str = "BAAI/bge-m3"
    litellm_model: str = "anthropic/claude-sonnet-4-5"
    chat_history_window: int = 20
    rag_top_k: int = 8
    rag_candidate_pool: int = 40
    rag_notoriety_alpha: float = 0.35
    backend_cors_origins: str = "http://localhost:5173"
    allow_anonymous_chat: bool = True
    chat_rate_limit_enabled: bool = True
    chat_auth_rate_limit_per_hour: int = 60
    chat_anonymous_rate_limit_per_hour: int = 20
    langfuse_enabled: bool = False
    langfuse_capture_content: bool = True
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_base_url: str = "https://cloud.langfuse.com"
    sentry_enabled: bool = False
    sentry_dsn: str = ""
    sentry_environment: str = "development"
    sentry_release: str = ""
    sentry_traces_sample_rate: float = 0.0
    git_sha: str = "unknown"

    class Config:
        env_file = str(_ENV_FILE)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.environment != "production":
            return self

        if self.secret_key == "change-me-in-production" or len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be changed and contain at least 32 characters in production")

        return self


settings = Settings()
