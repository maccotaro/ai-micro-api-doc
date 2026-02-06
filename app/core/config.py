"""Document Processing Service configuration settings."""
from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""

    # Service info
    SERVICE_NAME: str = "doc-service"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Redis (task queue)
    REDIS_URL: str = "redis://:password@localhost:6379/1"

    # Celery
    CELERY_BROKER_URL: str = "redis://:password@localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://:password@localhost:6379/2"
    CELERY_WORKER_CONCURRENCY: int = 4

    # Storage
    STORAGE_TYPE: str = "local"  # local, s3, minio
    STORAGE_BASE_PATH: str = "/data/documents"
    S3_ENDPOINT: str = "http://minio:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "documents"

    # OCR settings
    OCR_DEFAULT_ENGINE: str = "easyocr"  # easyocr, tesseract
    OCR_DEFAULT_LANGUAGE: str = "jpn+eng"
    OCR_GPU_ENABLED: bool = True

    # Embedding settings (model names are managed via DB system_settings, fetched via internal API)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    ADMIN_INTERNAL_URL: str = "http://localhost:8003"
    INTERNAL_API_SECRET: str = "change-me-in-production"

    # Chunking settings
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # Authentication
    JWKS_URL: str = "http://localhost:8002/.well-known/jwks.json"
    JWT_AUDIENCE: str = "fastapi-api"
    JWT_ISSUER: str = "https://auth.example.com"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # Logging
    LOG_LEVEL: str = "INFO"

    # api-admin connection (for callbacks)
    ADMIN_SERVICE_URL: str = "http://localhost:8003"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    # Property accessors for lowercase compatibility
    @property
    def ollama_base_url(self) -> str:
        return self.OLLAMA_BASE_URL

    @property
    def chunk_size(self) -> int:
        return self.CHUNK_SIZE

    @property
    def chunk_overlap(self) -> int:
        return self.CHUNK_OVERLAP


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
