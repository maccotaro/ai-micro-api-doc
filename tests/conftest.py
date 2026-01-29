"""Shared fixtures for api-doc tests."""
import os
import pytest
from unittest.mock import MagicMock, patch

# Set test environment variables before importing app modules
os.environ.setdefault("JWKS_URL", "http://localhost:8002/.well-known/jwks.json")
os.environ.setdefault("JWT_ISSUER", "https://test.example.com")
os.environ.setdefault("JWT_AUDIENCE", "test-api")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:password@localhost:5432/testdb")


@pytest.fixture
def mock_settings():
    """Mock settings for tests."""
    settings = MagicMock()
    settings.JWKS_URL = "http://localhost:8002/.well-known/jwks.json"
    settings.JWT_ISSUER = "https://test.example.com"
    settings.JWT_AUDIENCE = "test-api"
    return settings


@pytest.fixture
def sample_jwt_payload():
    """Sample JWT payload for tests."""
    return {
        "sub": "test-user-123",
        "roles": ["admin", "user"],
        "tenant_id": "test-tenant-id",
        "department": "Engineering",
        "clearance_level": "internal",
        "exp": 9999999999,
        "iat": 1234567890,
    }


@pytest.fixture
def mock_jwks_response():
    """Mock JWKS response."""
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key-id",
                "use": "sig",
                "alg": "RS256",
                "n": "test-n-value",
                "e": "AQAB",
            }
        ]
    }
