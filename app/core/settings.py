from functools import lru_cache

from pydantic import field_validator, model_validator, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Ops Copilot"
    app_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"
    log_json: bool = False
    docs_enabled: bool = True
    data_dir: str = "data"
    vector_db_dir: str = "vector_db"
    database_url: str = "sqlite:///ai_ops_copilot.db"
    storage_provider: str = "local"
    azure_blob_connection_string: str = ""
    azure_blob_container: str = "ai-ops-datasets"

    jwt_secret_key: str = "change-this-secret-before-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    refresh_token_expire_minutes: int = 60 * 24 * 7

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-4o-mini"
    llm_timeout_seconds: float = 5.0
    llm_max_retries: int = 0

    max_upload_size_bytes: int = 5 * 1024 * 1024
    max_question_length: int = 500
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60
    rag_enabled: bool = True
    rag_top_k: int = 2
    rag_collection_name: str = "docs"
    health_require_llm: bool = False
    frontend_app_url: str = "http://127.0.0.1:5173"
    cors_allowed_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        enable_decoding=False,
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value):
        if value is None:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, str):
            value = value.strip()

            if not value:
                return []


            # Try JSON first
            if value.startswith("["):
                import json
                try:
                    return json.loads(value)
                except Exception:
                    raise ValueError("Invalid JSON format for cors_allowed_origins")

            # Fallback: comma-separated
            return [origin.strip() for origin in value.split(",") if origin.strip()]

        raise ValueError("Invalid type for cors_allowed_origins")

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"development", "staging", "production"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"environment must be one of {sorted(allowed)}")
        return normalized

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalized = value.upper().strip()
        if normalized not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return normalized

    @model_validator(mode="after")
    def validate_security_settings(self):
        if self.environment == "production" and self.jwt_secret_key == "change-this-secret-before-production":
            raise ValueError("JWT secret key must be changed before running in production.")

        if self.jwt_expire_minutes <= 0:
            raise ValueError("jwt_expire_minutes must be greater than zero.")

        if self.max_upload_size_bytes <= 0:
            raise ValueError("max_upload_size_bytes must be greater than zero.")

        if self.refresh_token_expire_minutes <= 0:
            raise ValueError("refresh_token_expire_minutes must be greater than zero.")

        if self.rate_limit_requests <= 0 or self.rate_limit_window_seconds <= 0:
            raise ValueError("Rate limit settings must be greater than zero.")

        if self.llm_timeout_seconds <= 0:
            raise ValueError("llm_timeout_seconds must be greater than zero.")

        if self.rag_top_k <= 0:
            raise ValueError("rag_top_k must be greater than zero.")

        if self.storage_provider not in {"local", "azure_blob"}:
            raise ValueError("storage_provider must be 'local' or 'azure_blob'.")

        return self

    @property
    def sqlite_db_path(self) -> str:
        if self.database_url.startswith("sqlite:///"):
            return self.database_url.replace("sqlite:///", "", 1)
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
