"""Celery application configuration for document processing service."""
from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "doc-service",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Configure Celery
celery_app.conf.update(
    # Timezone
    timezone="Asia/Tokyo",
    enable_utc=True,
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Result expiry (24 hours)
    result_expires=86400,
    # Task time limits (for long document processing)
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    # Task discovery
    imports=["app.tasks.document_tasks"],
)

# Explicitly register tasks
celery_app.autodiscover_tasks(["app.tasks"])
