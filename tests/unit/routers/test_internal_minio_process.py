# ai-micro-api-doc/tests/unit/routers/test_internal_minio_process.py
"""
Unit tests for internal MinIO URL-based document processing endpoint.

Tests:
- POST /internal/process/minio: auth, parameter validation, MinIO download + celery dispatch
- GET /internal/process/status/{task_id}: status polling
"""
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.internal_process import router

VALID_SECRET = "change-me-in-production"


def _create_app():
    """Create a test FastAPI app with internal router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.unit
class TestInternalMinioAuth:
    """Auth tests for MinIO process endpoint."""

    def test_missing_secret_returns_422(self):
        app = _create_app()
        client = TestClient(app)
        resp = client.post(
            "/internal/process/minio",
            json={"minio_url": "minio://bucket/file.pdf"},
        )
        assert resp.status_code == 422

    def test_invalid_secret_returns_401(self):
        app = _create_app()
        client = TestClient(app)
        resp = client.post(
            "/internal/process/minio",
            json={"minio_url": "minio://bucket/file.pdf"},
            headers={"X-Internal-Secret": "wrong"},
        )
        assert resp.status_code == 401


@pytest.mark.unit
class TestProcessFromMinio:
    """Tests for POST /internal/process/minio."""

    def test_invalid_minio_url_format(self):
        """parse_minio_path rejects non-minio:// URLs."""
        from app.services.storage import parse_minio_path
        with pytest.raises(ValueError, match="Invalid MinIO path"):
            parse_minio_path("https://not-minio/file.pdf")

    def test_missing_minio_url_returns_422(self):
        app = _create_app()
        client = TestClient(app)
        resp = client.post(
            "/internal/process/minio",
            json={},
            headers={"X-Internal-Secret": VALID_SECRET},
        )
        assert resp.status_code == 422

    def test_parse_valid_minio_url(self):
        """parse_minio_path correctly parses minio:// URLs."""
        from app.services.storage import parse_minio_path
        bucket, key = parse_minio_path("minio://mybucket/docs/file.pdf")
        assert bucket == "mybucket"
        assert key == "docs/file.pdf"

    def test_minio_endpoint_requires_minio_url(self):
        """POST /internal/process/minio requires minio_url body parameter."""
        app = _create_app()
        client = TestClient(app)
        resp = client.post(
            "/internal/process/minio",
            json={"document_id": "some-id"},
            headers={"X-Internal-Secret": VALID_SECRET},
        )
        assert resp.status_code == 422


@pytest.mark.unit
class TestGetTaskStatus:
    """Tests for GET /internal/process/status/{task_id}."""

    def test_status_pending(self):
        app = _create_app()

        mock_result = MagicMock()
        mock_result.status = "PENDING"
        mock_result.ready.return_value = False
        mock_result.result = None

        import sys
        mock_celery_result = MagicMock()
        mock_celery_result.AsyncResult = MagicMock(return_value=mock_result)
        sys.modules["celery.result"] = mock_celery_result
        mock_celery_app_mod = MagicMock()
        sys.modules["app.tasks.celery_app"] = mock_celery_app_mod

        try:
            client = TestClient(app)
            resp = client.get(
                "/internal/process/status/task-123",
                headers={"X-Internal-Secret": VALID_SECRET},
            )
        finally:
            sys.modules.pop("celery.result", None)
            sys.modules.pop("app.tasks.celery_app", None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["result"] is None

    def test_status_success(self):
        app = _create_app()

        mock_result = MagicMock()
        mock_result.status = "SUCCESS"
        mock_result.ready.return_value = True
        mock_result.result = {"output_directory": "/data/docs/123", "total_pages": 5}

        import sys
        mock_celery_result = MagicMock()
        mock_celery_result.AsyncResult = MagicMock(return_value=mock_result)
        sys.modules["celery.result"] = mock_celery_result
        mock_celery_app_mod = MagicMock()
        sys.modules["app.tasks.celery_app"] = mock_celery_app_mod

        try:
            client = TestClient(app)
            resp = client.get(
                "/internal/process/status/task-123",
                headers={"X-Internal-Secret": VALID_SECRET},
            )
        finally:
            sys.modules.pop("celery.result", None)
            sys.modules.pop("app.tasks.celery_app", None)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert data["result"]["total_pages"] == 5
