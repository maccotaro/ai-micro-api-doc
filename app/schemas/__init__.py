"""Pydantic schemas for document processing service."""
from app.schemas.documents import (
    DocumentProcessResponse,
    DocumentProcessStatus,
    ProcessingError,
    DocumentMetadataResponse,
    CropImageRequest,
    CropImageResponse,
    OCRMetadataResponse,
    OCRMetadataUpdateRequest,
    OCRMetadataUpdateResponse,
    SaveCroppedImageRequest,
    SaveCroppedImageResponse,
)

__all__ = [
    "DocumentProcessResponse",
    "DocumentProcessStatus",
    "ProcessingError",
    "DocumentMetadataResponse",
    "CropImageRequest",
    "CropImageResponse",
    "OCRMetadataResponse",
    "OCRMetadataUpdateRequest",
    "OCRMetadataUpdateResponse",
    "SaveCroppedImageRequest",
    "SaveCroppedImageResponse",
]
