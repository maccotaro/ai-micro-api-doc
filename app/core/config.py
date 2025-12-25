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

    # Database (docdb)
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/docdb"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_POOL_RECYCLE: int = 3600

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

    # Docling settings
    DOCLING_DEVICE: str = "cuda"  # cuda, cpu, mps
    DOCLING_BATCH_SIZE: int = 4

    # OCR settings
    OCR_DEFAULT_ENGINE: str = "easyocr"  # easyocr, tesseract
    OCR_DEFAULT_LANGUAGE: str = "jpn+eng"
    OCR_GPU_ENABLED: bool = True

    # Embedding settings
    EMBEDDING_MODEL: str = "bge-m3:567m"
    EMBEDDING_DIMENSION: int = 768
    OLLAMA_BASE_URL: str = "http://localhost:11434"

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
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def ollama_base_url(self) -> str:
        return self.OLLAMA_BASE_URL

    @property
    def embedding_model(self) -> str:
        return self.EMBEDDING_MODEL

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
