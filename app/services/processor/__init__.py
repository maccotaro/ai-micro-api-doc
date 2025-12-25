"""
Document processing module for AI Micro Service API Admin.

This module provides a modular document processing system built around Docling
for advanced document layout analysis, OCR, and content extraction.

Architecture:
- base.py: Main DocumentProcessor orchestrator class
- docling_processor.py: Docling-specific document conversion and processing
- layout_extractor.py: Page layout analysis and element extraction
- image_processor.py: Image generation, annotation, and rendering
- text_extractor.py: Text content extraction and OCR operations
- file_manager.py: File operations, directory management, and output handling
- utils.py: Utility functions for common operations

Usage:
    from app.core.document_processing import DocumentProcessor, get_document_processor
    
    # Get global instance
    processor = get_document_processor()
    
    # Process document
    result = processor.process_document("/path/to/document.pdf", "document.pdf")
    
    # Async processing
    result = await processor.process_document_async("/path/to/document.pdf", "document.pdf")

Features:
- Docling-based document layout analysis with element detection
- Universal element type processing (FigureElement, TextElement, TableElement, etc.)
- High-quality page image generation with annotation support
- OCR fallback processing using Tesseract and EasyOCR
- Model caching for improved performance
- Memory monitoring and management
- Comprehensive error handling and fallback strategies

Output Structure:
    timestamp_filename/
    ├── original/           # Original document files
    ├── layout/            # JSON layout data per page
    ├── images/            # Page images and annotated versions
    ├── text/              # Extracted text per page
    └── metadata.json      # Processing metadata and summary
"""

"""
AI Micro Service API Admin用の文書処理モジュールです。

このモジュールは、高度なドキュメントレイアウト分析、OCR、およびコンテンツ抽出のために、Docling
を中心に構築されたモジュール式ドキュメント処理システムを提供します。

アーキテクチャ
- base.py： メインDocumentProcessorオーケストレータクラス
- docling_processor.py： Docling固有の文書変換および処理
- layout_extractor.py： ページレイアウト解析と要素抽出
- image_processor.py： 画像生成、アノテーション、レンダリング
- text_extractor.py： テキスト内容の抽出と OCR 操作
- file_manager.py： ファイル操作、ディレクトリ管理、出力処理
- utils.py： 一般的な操作のためのユーティリティ関数

使用法:
 from app.core.document_processing import DocumentProcessor, get_document_processor
    
    # グローバルインスタンスを取得
 processor = get_document_processor()
    
    # 文書を処理
 result = processor.process_document("/path/to/document.pdf", "document.pdf")
    
    # 非同期処理
 result = await processor.process_document_async("/path/to/document.pdf", "document.pdf")

特徴
- 要素検出による Docling ベースの文書レイアウト解析
- 汎用的な要素タイプ処理 (FigureElement, TextElement, TableElement など)
- 注釈をサポートした高品質のページ画像生成
- TesseractとEasyOCRを使用したOCRフォールバック処理
- パフォーマンス向上のためのモデルキャッシュ
- メモリの監視と管理
- 包括的なエラー処理とフォールバック戦略

出力構造:
 timestamp_filename/
 ├── original/ # 元文書ファイル
 ├── layout/ # ページごとのJSONレイアウトデータ
 ├── images/ # ページ画像と注釈版
 ├── text/ # ページごとの抽出テキスト
 └── metadata. json # メタデータと要約の処理

 """

from .base import DocumentProcessor, get_document_processor
from .docling_processor import DoclingProcessor
from .layout_extractor import LayoutExtractor
from .image_processor import ImageProcessor
from .text_extractor import TextExtractor
from .file_manager import FileManager
from .image_cropper import ImageCropper
from .region_ocr_processor import RegionOCRProcessor
from .utils import (
    get_element_type,
    get_docling_element_type,
    extract_bbox,
    is_item_on_page,
    get_pdf_page_size
)

__all__ = [
    "DocumentProcessor",
    "get_document_processor",
    "DoclingProcessor",
    "LayoutExtractor",
    "ImageProcessor",
    "TextExtractor",
    "FileManager",
    "ImageCropper",
    "RegionOCRProcessor",
    "get_element_type",
    "get_docling_element_type",
    "extract_bbox",
    "is_item_on_page",
    "get_pdf_page_size"
]

__version__ = "1.0.0"
__author__ = "AI Micro Service Team"
__description__ = "Modular document processing system with Docling integration"