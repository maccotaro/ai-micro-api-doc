"""Document processing router - OCR、レイアウト解析、階層構造変換."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pathlib import Path
from uuid import UUID, uuid4
import logging
import tempfile
import shutil
import asyncio
import json
from typing import Optional
from datetime import datetime, timezone

from app.core.security import get_current_user, require_admin
from app.schemas.documents import (
    DocumentProcessResponse,
    DocumentProcessStatus,
    ProcessingError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status", response_model=DocumentProcessStatus)
async def get_processing_status(_: dict = Depends(require_admin)):
    """Get document processing service status."""
    try:
        from app.services.processor import get_document_processor

        processor = get_document_processor(use_layout_extractor=True)

        # docling_processorの存在を確認
        if processor.docling_processor is None:
            return DocumentProcessStatus(
                status="error",
                message="Docling processor not available",
                mode="fallback_only",
                output_directory=None,
                cache_directories=None,
            )

        return DocumentProcessStatus(
            status="ready",
            message="Document processing service is ready",
            mode="docling_with_fallback",
            output_directory=str(processor.output_base_dir),
            cache_directories={
                "easyocr": str(processor.easyocr_cache_dir),
                "docling": str(processor.docling_cache_dir),
            },
        )

    except Exception as e:
        logger.error(f"Error checking processing status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to check status: {str(e)}"
        )


@router.post("/process", response_model=DocumentProcessResponse)
async def process_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(require_admin),
):
    """
    Process an uploaded document file.

    This endpoint:
    1. Saves the uploaded file to a temporary location
    2. Runs Docling-based layout extraction
    3. Generates hierarchical structure metadata
    4. Returns processing results

    For async processing, use /process/async endpoint.
    """
    try:
        from app.services.processor import get_document_processor

        # Create temp file
        suffix = Path(file.filename).suffix if file.filename else ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            # Get processor
            processor = get_document_processor(use_layout_extractor=True)

            # Process document
            result = processor.process_document(
                tmp_path, original_filename=file.filename
            )

            return DocumentProcessResponse(
                status="success",
                message="Document processed successfully",
                output_directory=result.get("output_directory", ""),
                files_created=result.get("files_created", {}),
                total_pages=result.get("total_pages", 0),
                original_filename=file.filename or "unknown",
                processing_mode=result.get("processing_mode", "docling"),
            )

        finally:
            # Cleanup temp file
            if tmp_path.exists():
                tmp_path.unlink()

    except Exception as e:
        logger.error(f"Error processing document: {e}")
        raise HTTPException(
            status_code=500, detail=f"Document processing failed: {str(e)}"
        )


@router.post("/process/async")
async def process_document_async(
    file: UploadFile = File(...),
    callback_url: Optional[str] = Form(None),
    current_user: dict = Depends(require_admin),
):
    """
    Process a document asynchronously using Celery.

    This endpoint:
    1. Saves the uploaded file to a persistent location
    2. Queues a Celery task for processing
    3. Returns a task ID for status tracking

    Use /process/status/{task_id} to check task status.
    """
    try:
        from app.core.config import settings
        from app.tasks.document_tasks import process_document_task

        # Save file to persistent storage
        task_id = str(uuid4())
        storage_path = Path(settings.STORAGE_BASE_PATH) / "pending" / task_id
        storage_path.mkdir(parents=True, exist_ok=True)

        file_path = storage_path / (file.filename or "document.pdf")
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        # Queue Celery task
        result = process_document_task.delay(
            str(file_path),
            file.filename,
            callback_url,
            current_user.get("sub"),
        )

        return {
            "message": "Document processing started",
            "task_id": result.id,
            "file_path": str(file_path),
        }

    except Exception as e:
        logger.error(f"Error starting async processing: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start async processing: {str(e)}"
        )


@router.get("/process/status/{task_id}")
async def get_task_status(
    task_id: str, current_user: dict = Depends(require_admin)
):
    """Get the status of an async processing task."""
    try:
        from celery.result import AsyncResult
        from app.tasks import celery_app

        result = AsyncResult(task_id, app=celery_app)

        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
        }

    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get task status: {str(e)}"
        )


@router.get("/process/status/{task_id}/stream")
async def stream_task_status(
    task_id: str,
    current_user: dict = Depends(require_admin),
):
    """
    Server-Sent Events (SSE) endpoint for real-time task progress streaming.

    This endpoint monitors a Celery task and streams status updates.
    The stream closes when the task reaches a terminal state.

    Args:
        task_id: Celery task ID

    Returns:
        StreamingResponse with text/event-stream content type

    Event Format:
        data: {"task_id": "...", "status": "STARTED", ...}\n\n
    """
    async def event_generator():
        """Progress event generator that yields SSE-formatted messages"""
        from celery.result import AsyncResult
        from app.tasks.celery_app import celery_app

        last_status = None
        terminal_states = ["SUCCESS", "FAILURE", "REVOKED"]
        heartbeat_interval = 2
        seconds_since_last_event = 0

        try:
            logger.info(f"SSE stream started: task_id={task_id}")

            while True:
                result = AsyncResult(task_id, app=celery_app)
                current_status = result.status

                # Determine if we should send an event
                has_changed = current_status != last_status
                is_first_event = last_status is None
                is_heartbeat_time = seconds_since_last_event >= heartbeat_interval

                if has_changed or is_first_event or is_heartbeat_time:
                    # Build progress data
                    progress_data = {
                        "task_id": task_id,
                        "status": current_status,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }

                    # Add result if task is ready
                    if result.ready():
                        try:
                            progress_data["result"] = result.result
                        except Exception:
                            progress_data["result"] = None

                    # Add task info if available
                    if hasattr(result, "info") and result.info:
                        progress_data["info"] = result.info

                    # Send SSE event
                    event_type = "heartbeat" if (is_heartbeat_time and not has_changed) else "progress"
                    logger.debug(f"SSE {event_type}: task_id={task_id}, status={current_status}")
                    yield f"data: {json.dumps(progress_data)}\n\n"

                    # Update tracking
                    last_status = current_status
                    seconds_since_last_event = 0
                else:
                    seconds_since_last_event += 1

                # Check for terminal state
                if current_status in terminal_states:
                    logger.info(f"SSE task finished: task_id={task_id}, status={current_status}")
                    break

                # Wait before next check
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"SSE stream error: task_id={task_id}, error={str(e)}")
            yield f"event: error\ndata: {{\"message\": \"Server error: {str(e)}\"}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chunk")
async def chunk_document(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    current_user: dict = Depends(require_admin),
):
    """
    Split text into chunks for embedding.

    This endpoint takes raw text and returns chunks suitable for
    vector embedding and RAG retrieval.
    """
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", "。", ".", " ", ""],
        )

        chunks = splitter.split_text(text)

        return {
            "status": "success",
            "chunk_count": len(chunks),
            "chunks": chunks,
            "settings": {
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            },
        }

    except Exception as e:
        logger.error(f"Error chunking document: {e}")
        raise HTTPException(
            status_code=500, detail=f"Chunking failed: {str(e)}"
        )
