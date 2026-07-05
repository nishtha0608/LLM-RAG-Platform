"""Application settings loaded from environment variables (12-factor config)."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "rag-platform"
    environment: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/rag_platform"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # Auth
    jwt_secret_key: SecretStr = Field(default=SecretStr("change-me-in-production"))
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Vector store
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: SecretStr | None = None
    qdrant_collection: str = "documents"
    vector_dimension: int = 384  # bge-small-en-v1.5

    # Embeddings
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_batch_size: int = 32

    # LLM
    llm_provider: Literal["ollama", "anthropic"] = "ollama"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.2

    anthropic_api_key: SecretStr | None = None
    llm_model: str = "claude-sonnet-4-5"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    ollama_num_ctx: int = 16384
    ollama_num_predict: int = 1024

    # Ingestion
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_upload_size_mb: int = 25

    # Retrieval
    retrieval_top_k: int = 5
    retrieval_score_threshold: float = 0.5
    summary_max_chunks: int = 40

    # Rate limiting
    rate_limit_per_minute: int = 60

    # Observability
    otel_exporter_endpoint: str | None = None
    log_level: str = "INFO"
    log_json: bool = True

    # CORS
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
