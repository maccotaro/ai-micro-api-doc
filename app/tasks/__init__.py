"""Celery tasks for document processing service."""
from app.tasks.celery_app import celery_app
from app.tasks.document_tasks import (
    process_document_task,
    chunk_document_task,
    ocr_region_task,
)

__all__ = [
    "celery_app",
    "process_document_task",
    "chunk_document_task",
    "ocr_region_task",
]
