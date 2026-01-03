"""
Lightweight document processing utilities for API Doc service.

This module provides lightweight, synchronous processing utilities:
- ImageCropper: Image cropping from processed documents
- RegionOCRProcessor: OCR on specific image regions

Heavy document processing (OCR, layout extraction, hierarchical conversion)
is handled by celery-doc worker service.

Usage:
    from app.services.processor import ImageCropper, RegionOCRProcessor

    # Crop an image region
    cropper = ImageCropper()
    result = cropper.crop_image(image_path, x, y, width, height)

    # OCR a specific region
    ocr = RegionOCRProcessor()
    text = ocr.process_region(image_path, region_coords)
"""

from .image_cropper import ImageCropper
from .region_ocr_processor import RegionOCRProcessor

__all__ = [
    "ImageCropper",
    "RegionOCRProcessor",
]

__version__ = "2.0.0"
__author__ = "AI Micro Service Team"
__description__ = "Lightweight document processing utilities (gateway mode)"
