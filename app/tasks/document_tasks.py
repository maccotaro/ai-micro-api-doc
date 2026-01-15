"""Lightweight Celery tasks for api-doc service.

Note: Heavy document processing tasks are handled by celery-doc worker.
This module only contains lightweight tasks that can run in api-doc.
"""
import logging
from pathlib import Path
from typing import Optional
import httpx

from app.tasks.celery_app import celery_app
from app.core.config import settings

logger = logging.getLogger(__name__)


# Note: process_document_task is now handled by celery-doc worker
# Use celery_app.send_task("app.tasks.document_tasks.process_document_task", ...)
# to queue tasks for celery-doc


@celery_app.task(bind=True, max_retries=3)
def chunk_document_task(
    self,
    document_id: str,
    text_content: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    callback_url: Optional[str] = None,
):
    """
    Chunk document text for embedding.

    This task splits text into chunks suitable for vector embedding.

    Args:
        document_id: Document identifier
        text_content: Text to chunk
        chunk_size: Size of each chunk
        chunk_overlap: Overlap between chunks
        callback_url: Optional URL to notify on completion

    Returns:
        dict: Chunking result with chunks and metadata
    """
    try:
        logger.info(f"Starting chunking for document: {document_id}")

        from langchain.text_splitter import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", ".", " ", ""],
        )

        chunks = splitter.split_text(text_content)

        logger.info(f"Chunking completed: {len(chunks)} chunks created")

        result = {
            "status": "success",
            "document_id": document_id,
            "chunk_count": len(chunks),
            "chunks": chunks,
            "settings": {
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            },
        }

        # Send callback if configured
        if callback_url:
            try:
                with httpx.Client(timeout=30.0) as client:
                    client.post(callback_url, json=result)
            except Exception as cb_error:
                logger.error(f"Callback failed: {cb_error}")

        return result

    except Exception as e:
        logger.error(f"Chunking failed: {e}")

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)

        return {
            "status": "error",
            "document_id": document_id,
            "message": str(e),
        }


@celery_app.task(bind=True, max_retries=2)
def ocr_region_task(
    self,
    document_id: str,
    page_image_path: str,
    x: float,
    y: float,
    width: float,
    height: float,
    language: str = "jpn+eng",
    callback_url: Optional[str] = None,
):
    """
    Perform OCR on a specific region asynchronously.

    Args:
        document_id: Document identifier
        page_image_path: Path to the page image
        x, y, width, height: Region coordinates
        language: OCR language
        callback_url: Optional URL to notify on completion

    Returns:
        dict: OCR result with extracted text
    """
    try:
        logger.info(f"Starting region OCR for document: {document_id}")

        from app.services.processor import RegionOCRProcessor

        ocr_processor = RegionOCRProcessor()
        result = ocr_processor.ocr_region(
            Path(page_image_path),
            x=x,
            y=y,
            width=width,
            height=height,
            language=language,
        )

        response = {
            "status": "success",
            "document_id": document_id,
            "text": result["text"],
            "confidence": result.get("confidence", 0.0),
            "language": language,
            "region": {"x": x, "y": y, "width": width, "height": height},
        }

        if callback_url:
            try:
                with httpx.Client(timeout=30.0) as client:
                    client.post(callback_url, json=response)
            except Exception as cb_error:
                logger.error(f"Callback failed: {cb_error}")

        return response

    except Exception as e:
        logger.error(f"Region OCR failed: {e}")

        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)

        return {
            "status": "error",
            "document_id": document_id,
            "message": str(e),
        }
