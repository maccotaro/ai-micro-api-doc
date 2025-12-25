"""OCR router - OCRメタデータ、画像クロッピング操作."""
from fastapi import APIRouter, HTTPException, Depends, Body, Query
from fastapi.responses import FileResponse
from pathlib import Path
from uuid import UUID
import logging
from typing import Dict, Any, Optional

from app.core.security import get_current_user, require_admin
from app.core.config import settings
from app.schemas.documents import (
    CropImageRequest,
    CropImageResponse,
    OCRMetadataResponse,
    OCRMetadataUpdateRequest,
    OCRMetadataUpdateResponse,
    SaveCroppedImageRequest,
    SaveCroppedImageResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def resolve_document_path(
    document_id: str,
    processing_path: Optional[str] = None
) -> Path:
    """
    Resolve the actual document path on filesystem.

    Args:
        document_id: Document UUID (used as fallback path component)
        processing_path: Actual processing output directory (preferred)

    Returns:
        Path: Resolved document directory path

    The path resolution strategy:
    1. If processing_path is provided, use it directly
    2. Otherwise, fall back to {STORAGE_BASE_PATH}/{document_id}
    """
    if processing_path:
        # Use provided processing path
        path = Path(processing_path)
        if path.is_absolute():
            return path
        # If relative, resolve against STORAGE_BASE_PATH
        return Path(settings.STORAGE_BASE_PATH) / processing_path

    # Fallback to document_id-based path
    return Path(settings.STORAGE_BASE_PATH) / document_id


@router.post("/crop", response_model=CropImageResponse)
async def crop_image(
    document_id: str,
    page_number: int,
    request: CropImageRequest,
    processing_path: Optional[str] = Query(
        None,
        description="Actual processing output directory path"
    ),
    current_user: dict = Depends(require_admin),
):
    """
    Crop a region from a document page image.

    This endpoint:
    1. Locates the page image for the document
    2. Crops the specified region
    3. Saves and returns the cropped image
    """
    try:
        from app.services.processor import ImageCropper

        # Find page image
        doc_path = resolve_document_path(document_id, processing_path)
        if not doc_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Document not found: {document_id}"
            )

        # Find page image (try common naming conventions)
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

        # Crop image
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
                detail=f"Image cropping failed: {result.get('error', 'Unknown error')}"
            )

        return CropImageResponse(
            success=True,
            image_path=result["image_path"],
            full_path=result["full_path"],
            download_url=f"/api/doc/ocr/images/{document_id}/{result['image_path']}",
            width=result["width"],
            height=result["height"],
            file_size=result["file_size"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cropping image: {e}")
        raise HTTPException(
            status_code=500, detail=f"Image cropping failed: {str(e)}"
        )


@router.get("/images/{document_id}/{path:path}")
async def get_image(
    document_id: str,
    path: str,
    processing_path: Optional[str] = Query(
        None,
        description="Actual processing output directory path"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Serve an image from a processed document.

    Supports:
    - Page images
    - Cropped figure images
    - Generated images
    """
    try:
        # Build full path
        doc_base = resolve_document_path(document_id, processing_path)
        full_path = doc_base / path
        try:
            full_path.resolve().relative_to(doc_base.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")

        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")

        # Determine media type
        suffix = full_path.suffix.lower()
        media_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        media_type = media_types.get(suffix, "application/octet-stream")

        return FileResponse(full_path, media_type=media_type)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving image: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to serve image: {str(e)}"
        )


@router.get("/metadata/{document_id}", response_model=OCRMetadataResponse)
async def get_ocr_metadata(
    document_id: str,
    processing_path: Optional[str] = Query(
        None,
        description="Actual processing output directory path"
    ),
    current_user: dict = Depends(get_current_user),
):
    """
    Get OCR metadata for a processed document.

    Returns:
    - Hierarchical structure metadata
    - Page information
    - Element information (text blocks, figures, tables)

    Note: If processing_path is provided, it will be used to locate the metadata.
    Otherwise, falls back to {STORAGE_BASE_PATH}/{document_id}.
    """
    try:
        import json

        doc_path = resolve_document_path(document_id, processing_path)
        logger.debug(f"Resolved document path: {doc_path}")

        if not doc_path.exists():
            logger.warning(
                f"Document path not found: {doc_path}, "
                f"document_id={document_id}, processing_path={processing_path}"
            )
            raise HTTPException(
                status_code=404, detail=f"Document not found: {document_id}"
            )

        # Try to find metadata file
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

        # Check for edited metadata
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
            last_edited_at=None,  # TODO: Track from file mtime
            edited_by=None,
            source="filesystem",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting OCR metadata: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get metadata: {str(e)}"
        )


@router.put("/metadata/{document_id}", response_model=OCRMetadataUpdateResponse)
async def update_ocr_metadata(
    document_id: str,
    request: OCRMetadataUpdateRequest,
    processing_path: Optional[str] = Query(
        None,
        description="Actual processing output directory path"
    ),
    current_user: dict = Depends(require_admin),
):
    """
    Update OCR metadata for a document.

    Saves edited metadata to a separate file to preserve original.
    """
    try:
        import json

        doc_path = resolve_document_path(document_id, processing_path)
        if not doc_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Document not found: {document_id}"
            )

        # Save edited metadata
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
        logger.error(f"Error updating OCR metadata: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to update metadata: {str(e)}"
        )


@router.post("/save-cropped-image", response_model=SaveCroppedImageResponse)
async def save_cropped_image(
    document_id: str,
    request: SaveCroppedImageRequest,
    processing_path: Optional[str] = Query(
        None,
        description="Actual processing output directory path"
    ),
    current_user: dict = Depends(require_admin),
):
    """
    Save a cropped image permanently.

    Moves the image from temporary location to permanent storage.
    """
    try:
        import shutil

        doc_path = resolve_document_path(document_id, processing_path)
        if not doc_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Document not found: {document_id}"
            )

        # Source path (temp)
        temp_path = Path(request.tempImagePath)
        if not temp_path.exists():
            raise HTTPException(
                status_code=404, detail="Temporary image not found"
            )

        # Destination path
        dest_dir = doc_path / "cropped" / request.elementType
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / f"{request.rectangleId}.png"

        # Copy file
        shutil.copy2(temp_path, dest_path)

        return SaveCroppedImageResponse(
            success=True,
            saved_image_path=str(dest_path.relative_to(doc_path)),
            message="Image saved successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving cropped image: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to save image: {str(e)}"
        )


@router.post("/ocr-region")
async def ocr_region(
    document_id: str,
    page_number: int,
    x: float,
    y: float,
    width: float,
    height: float,
    language: str = "jpn+eng",
    processing_path: Optional[str] = Query(
        None,
        description="Actual processing output directory path"
    ),
    current_user: dict = Depends(require_admin),
):
    """
    Perform OCR on a specific region of a page.

    Uses EasyOCR or Tesseract based on configuration.
    """
    try:
        from app.services.processor import RegionOCRProcessor

        # Find page image
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

        # Perform OCR
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
        logger.error(f"Error performing region OCR: {e}")
        raise HTTPException(
            status_code=500, detail=f"OCR failed: {str(e)}"
        )
