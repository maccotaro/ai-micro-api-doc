from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List


class DocumentProcessResponse(BaseModel):
    """Response model for document processing."""
    status: str = Field(..., description="Processing status (success, processing, error)")
    message: str = Field(..., description="Processing message")
    output_directory: str = Field("", description="Relative path to output directory")
    files_created: Dict[str, str] = Field(default_factory=dict, description="Created file paths")
    total_pages: int = Field(0, description="Total number of pages processed")
    original_filename: str = Field(..., description="Original uploaded filename")
    processing_mode: str = Field(..., description="Processing mode used (celery_async, docling)")
    task_id: Optional[str] = Field(None, description="Celery task ID for async tracking")


class DocumentProcessStatus(BaseModel):
    """Response model for processing service status."""
    status: str = Field(..., description="Service status (ready, error)")
    message: str = Field(..., description="Status message")
    mode: str = Field(..., description="Available processing mode")
    output_directory: Optional[str] = Field(None, description="Output directory path")
    cache_directories: Optional[Dict[str, str]] = Field(None, description="Cache directory paths")


class ProcessingError(BaseModel):
    """Error response model for document processing."""
    status: str = Field(default="error", description="Error status")
    message: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Specific error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class DocumentMetadataResponse(BaseModel):
    """Response model for document metadata retrieval."""
    document_id: str = Field(..., description="Document UUID")
    processing_timestamp: Optional[str] = Field(None, description="When the document was processed")
    output_directory: str = Field(..., description="Output directory path")
    metadata: Dict[str, Any] = Field(..., description="Content of metadata.json")
    available_files: List[str] = Field(..., description="List of available files in output directory")


class CropImageRequest(BaseModel):
    """Request model for image cropping."""
    x: float = Field(..., description="Left coordinate of crop area")
    y: float = Field(..., description="Top coordinate of crop area")
    width: float = Field(..., description="Width of crop area")
    height: float = Field(..., description="Height of crop area")
    page_number: int = Field(..., description="Page number (1-based)")
    element_id: Optional[str] = Field(None, description="Optional element ID for naming")
    element_type: Optional[str] = Field(None, description="Optional element type for categorization")


class CropImageResponse(BaseModel):
    """Response model for image cropping."""
    success: bool = Field(..., description="Whether cropping was successful")
    image_path: str = Field(..., description="Relative path to cropped image")
    full_path: str = Field(..., description="Full filesystem path to cropped image")
    download_url: str = Field(..., description="URL for downloading the cropped image")
    width: int = Field(..., description="Width of cropped image in pixels")
    height: int = Field(..., description="Height of cropped image in pixels")
    file_size: int = Field(..., description="File size in bytes")


class OCRMetadataResponse(BaseModel):
    """Response model for OCR metadata retrieval."""
    metadata: Dict[str, Any] = Field(..., description="OCR metadata content")
    is_edited: bool = Field(..., description="Whether the metadata has been edited")
    editing_status: str = Field(..., description="Editing status (unedited, edited)")
    last_edited_at: Optional[str] = Field(None, description="Last edit timestamp")
    edited_by: Optional[str] = Field(None, description="User ID who last edited")
    source: str = Field(..., description="Data source (database, filesystem)")


class OCRMetadataUpdateRequest(BaseModel):
    """Request model for OCR metadata update."""
    metadata: Dict[str, Any] = Field(..., description="Updated OCR metadata content")


class OCRMetadataUpdateResponse(BaseModel):
    """Response model for OCR metadata update."""
    success: bool = Field(..., description="Whether update was successful")
    message: str = Field(..., description="Update result message")


class SaveCroppedImageRequest(BaseModel):
    """Request model for saving a cropped image permanently."""
    rectangleId: str = Field(..., description="ID of the rectangle element")
    tempImagePath: str = Field(..., description="Temporary path of the cropped image")
    elementType: str = Field("text", description="Type of the element (text, figure, picture, etc.)")


class SaveCroppedImageResponse(BaseModel):
    """Response model for saving a cropped image permanently."""
    success: bool = Field(..., description="Whether saving was successful")
    saved_image_path: str = Field(..., description="Permanent path to saved image")
    message: str = Field(..., description="Success or error message")