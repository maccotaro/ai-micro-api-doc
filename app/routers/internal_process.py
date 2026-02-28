"""Internal API router for service-to-service document processing calls.

Authenticated via X-Internal-Secret header instead of JWT.
Mirrors the public endpoints in process.py and ocr.py.
"""
import json
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi import UploadFile, File, Form, Query, Body
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.documents import (
    DocumentProcessResponse,
    CropImageRequest,
    CropImageResponse,
    OCRMetadataResponse,
    OCRMetadataUpdateRequest,
    OCRMetadataUpdateResponse,
)

logger = logging.getLogger(__name__)


async def verify_internal_secret(
    x_internal_secret: str = Header(..., alias="X-Internal-Secret"),
) -> None:
    """Verify the shared secret for internal service-to-service calls."""
    if x_internal_secret != settings.INTERNAL_API_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API secret",
        )


router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(verify_internal_secret)],
)


# ---------------------------------------------------------------------------
# Document processing endpoints (mirrors process.py)
# ---------------------------------------------------------------------------


@router.post("/process", response_model=DocumentProcessResponse)
async def internal_process_document(
    file: UploadFile = File(...),
    wait: bool = True,
    timeout: int = 300,
    user_id: Optional[str] = Form(None),
):
    """Process a document (internal, no JWT required)."""
    try:
        from app.tasks.celery_app import celery_app

        task_id = str(uuid4())
        storage_path = Path(settings.STORAGE_BASE_PATH) / "pending" / task_id
        storage_path.mkdir(parents=True, exist_ok=True)

        file_path = storage_path / (file.filename or "document.pdf")
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        result = celery_app.send_task(
            "app.tasks.document_tasks.process_document_task",
            args=[str(file_path), file.filename, None, user_id],
        )

        if not wait:
            return DocumentProcessResponse(
                status="processing",
                message="Document processing started",
                output_directory="",
                files_created={},
                total_pages=0,
                original_filename=file.filename or "unknown",
                processing_mode="celery_async",
                task_id=result.id,
            )

        try:
            task_result = result.get(timeout=timeout)
            return DocumentProcessResponse(
                status="success",
                message="Document processed successfully",
                output_directory=task_result.get("output_directory", ""),
                files_created=task_result.get("files_created", {}),
                total_pages=task_result.get("total_pages", 0),
                original_filename=file.filename or "unknown",
                processing_mode="celery_async",
            )
        except Exception as wait_error:
            logger.warning(f"Task wait timeout or error: {wait_error}")
            return DocumentProcessResponse(
                status="processing",
                message=f"Processing in progress. task_id: {result.id}",
                output_directory="",
                files_created={},
                total_pages=0,
                original_filename=file.filename or "unknown",
                processing_mode="celery_async",
                task_id=result.id,
            )

    except Exception as e:
        logger.error(f"Error processing document (internal): {e}")
        raise HTTPException(
            status_code=500, detail=f"Document processing failed: {str(e)}"
        )


@router.post("/process/async")
async def internal_process_document_async(
    file: UploadFile = File(...),
    callback_url: Optional[str] = Form(None),
    user_id: Optional[str] = Form(None),
):
    """Process a document asynchronously (internal, no JWT required)."""
    try:
        from app.tasks.celery_app import celery_app

        task_id = str(uuid4())
        storage_path = Path(settings.STORAGE_BASE_PATH) / "pending" / task_id
        storage_path.mkdir(parents=True, exist_ok=True)

        file_path = storage_path / (file.filename or "document.pdf")
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        result = celery_app.send_task(
            "app.tasks.document_tasks.process_document_task",
            args=[str(file_path), file.filename, callback_url, user_id],
        )

        return {
            "message": "Document processing started",
            "task_id": result.id,
            "file_path": str(file_path),
        }

    except Exception as e:
        logger.error(f"Error starting async processing (internal): {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start async processing: {str(e)}"
        )


@router.get("/process/status/{task_id}")
async def internal_get_task_status(task_id: str):
    """Get the status of an async processing task (internal)."""
    try:
        from celery.result import AsyncResult
        from app.tasks.celery_app import celery_app

        result = AsyncResult(task_id, app=celery_app)

        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None,
        }

    except Exception as e:
        logger.error(f"Error getting task status (internal): {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get task status: {str(e)}"
        )


# ---------------------------------------------------------------------------
# OCR endpoints (mirrors ocr.py)
# ---------------------------------------------------------------------------


@router.get("/ocr/metadata/{document_id}", response_model=OCRMetadataResponse)
async def internal_get_ocr_metadata(
    document_id: str,
    processing_path: Optional[str] = Query(
        None, description="Actual processing output directory path"
    ),
):
    """Get OCR metadata for a processed document (internal)."""
    from app.routers.ocr import resolve_document_path

    try:
        doc_path = resolve_document_path(document_id, processing_path)
        if not doc_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Document not found: {document_id}"
            )

        metadata_file = None
        for name in [
            "metadata_hierarchy.json",
            "metadata.json",
            "ocr_metadata.json",
        ]:
            candidate = doc_path / name
            if candidate.exists():
                metadata_file = candidate
                break

        if not metadata_file:
            raise HTTPException(
                status_code=404, detail="Metadata not found for document"
            )

        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        edited_file = doc_path / "metadata_hierarchy_edited.json"
        is_edited = edited_file.exists()
        editing_status = "edited" if is_edited else "unedited"

        if is_edited:
            with open(edited_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)

        return OCRMetadataResponse(
            metadata=metadata,
            is_edited=is_edited,
            editing_status=editing_status,
            last_edited_at=None,
            edited_by=None,
            source="filesystem",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting OCR metadata (internal): {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get metadata: {str(e)}"
        )


@router.put(
    "/ocr/metadata/{document_id}",
    response_model=OCRMetadataUpdateResponse,
)
async def internal_update_ocr_metadata(
    document_id: str,
    request: OCRMetadataUpdateRequest,
    processing_path: Optional[str] = Query(
        None, description="Actual processing output directory path"
    ),
):
    """Update OCR metadata for a document (internal)."""
    from app.routers.ocr import resolve_document_path

    try:
        doc_path = resolve_document_path(document_id, processing_path)
        if not doc_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Document not found: {document_id}"
            )

        edited_file = doc_path / "metadata_hierarchy_edited.json"
        with open(edited_file, "w", encoding="utf-8") as f:
            json.dump(request.metadata, f, ensure_ascii=False, indent=2)

        return OCRMetadataUpdateResponse(
            success=True,
            message="Metadata updated successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating OCR metadata (internal): {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update metadata: {str(e)}"
        )


@router.post("/ocr/region")
async def internal_ocr_region(
    document_id: str,
    page_number: int,
    x: float,
    y: float,
    width: float,
    height: float,
    language: str = "jpn+eng",
    processing_path: Optional[str] = Query(
        None, description="Actual processing output directory path"
    ),
):
    """Perform OCR on a specific region of a page (internal)."""
    from app.routers.ocr import resolve_document_path
    from app.services.processor import RegionOCRProcessor

    try:
        doc_path = resolve_document_path(document_id, processing_path)
        page_image = None
        for pattern in [
            f"images/page_{page_number}_full.png",
            f"page_{page_number}_full.png",
            f"page_{page_number:03d}.png",
            f"page_{page_number}.png",
            f"images/page_{page_number:03d}.png",
        ]:
            candidate = doc_path / pattern
            if candidate.exists():
                page_image = candidate
                break

        if not page_image:
            raise HTTPException(
                status_code=404,
                detail=f"Page image not found for page {page_number}",
            )

        ocr_processor = RegionOCRProcessor()
        result = ocr_processor.process_region_ocr(
            image_path=str(page_image),
            x=x,
            y=y,
            width=width,
            height=height,
        )

        return {
            "status": "success",
            "text": result["text"],
            "confidence": result.get("confidence", 0.0),
            "language": language,
            "region": {"x": x, "y": y, "width": width, "height": height},
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing region OCR (internal): {e}")
        raise HTTPException(
            status_code=500, detail=f"OCR failed: {str(e)}"
        )


@router.post("/ocr/crop", response_model=CropImageResponse)
async def internal_crop_image(
    document_id: str,
    page_number: int,
    request: CropImageRequest,
    processing_path: Optional[str] = Query(
        None, description="Actual processing output directory path"
    ),
):
    """Crop a region from a document page image (internal)."""
    from app.routers.ocr import resolve_document_path
    from app.services.processor import ImageCropper

    try:
        doc_path = resolve_document_path(document_id, processing_path)
        if not doc_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Document not found: {document_id}"
            )

        page_image = None
        for pattern in [
            f"images/page_{page_number}_full.png",
            f"page_{page_number}_full.png",
            f"page_{page_number:03d}.png",
            f"page_{page_number}.png",
            f"images/page_{page_number:03d}.png",
        ]:
            candidate = doc_path / pattern
            if candidate.exists():
                page_image = candidate
                break

        if not page_image:
            raise HTTPException(
                status_code=404,
                detail=f"Page image not found for page {page_number}",
            )

        cropper = ImageCropper()
        bbox = {
            "x": request.x,
            "y": request.y,
            "width": request.width,
            "height": request.height,
        }
        result = cropper.crop_region(
            page_image_path=str(page_image),
            bbox=bbox,
            output_dir=str(doc_path),
            element_id=request.element_id,
            element_type=request.element_type,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Image cropping failed: {result.get('error', 'Unknown error')}",
            )

        if processing_path and processing_path.startswith("minio://"):
            try:
                from app.services.storage import get_minio_client, parse_minio_path

                bucket, prefix = parse_minio_path(processing_path)
                minio_client = get_minio_client()
                local_cropped_path = doc_path / result["image_path"]
                object_key = f"{prefix}/{result['image_path']}"
                minio_client.upload_file(str(local_cropped_path), bucket, object_key)
                logger.info(f"Uploaded cropped image to MinIO: {bucket}/{object_key}")
            except Exception as e:
                logger.error(f"Failed to upload cropped image to MinIO: {e}")

        from urllib.parse import urlencode

        base_url = f"/api/doc/ocr/images/{document_id}/{result['image_path']}"
        if processing_path:
            base_url = f"{base_url}?{urlencode({'processing_path': processing_path})}"

        return CropImageResponse(
            success=True,
            image_path=result["image_path"],
            full_path=result["full_path"],
            download_url=base_url,
            width=result["width"],
            height=result["height"],
            file_size=result["file_size"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cropping image (internal): {e}")
        raise HTTPException(
            status_code=500, detail=f"Image cropping failed: {str(e)}"
        )
