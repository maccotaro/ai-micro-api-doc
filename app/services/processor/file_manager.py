"""
File management utilities for document processing.
Handles file operations, directory creation, and fallback processing.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Any
import logging
from datetime import datetime
import os

try:
    import pypdfium2 as pdfium
    PYPDFIUM2_AVAILABLE = True
except ImportError:
    PYPDFIUM2_AVAILABLE = False

from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)


class FileManager:
    """File management for document processing operations"""
    
    def __init__(self, output_base_dir: Path):
        self.output_base_dir = output_base_dir
        self.output_base_dir.mkdir(exist_ok=True)
    
    def create_output_directory(self, timestamp: str, original_filename: str) -> Path:
        """Create output directory structure"""
        safe_filename = "".join(c for c in original_filename if c.isalnum() or c in (' ', '-', '_')).rstrip()
        output_dir = self.output_base_dir / f"{timestamp}_{safe_filename}"
        
        # Create directory structure
        # DISABLED: layout/ and text/ directories - data included in metadata_hierarchy.json
        subdirs = ["images", "original"]
        for subdir in subdirs:
            (output_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        return output_dir
    
    def save_original_file(self, source_path: str, output_dir: Path, original_filename: str) -> Path:
        """Save original file to output directory"""
        original_dir = output_dir / "original"
        dest_path = original_dir / original_filename
        shutil.copy2(source_path, dest_path)
        return dest_path
    
    def create_metadata_file(self, output_dir: Path, metadata: Dict[str, Any]) -> Path:
        """Create metadata.json file"""
        metadata_file = output_dir / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        return metadata_file
    
    # DISABLED: Individual layout file creation - data included in metadata_hierarchy.json
    # def create_layout_file(self, output_dir: Path, page_num: int, layout_data: Dict[str, Any]) -> Path:
    #     """Create layout JSON file for a page"""
    #     layout_dir = output_dir / "layout"
    #     layout_file = layout_dir / f"page_{page_num}_layout.json"
    #     with open(layout_file, 'w', encoding='utf-8') as f:
    #         json.dump(layout_data, f, ensure_ascii=False, indent=2)
    #     return layout_file
    
    # DISABLED: Individual text file creation - data included in metadata_hierarchy.json
    # def create_text_file(self, output_dir: Path, page_num: int, text_content: str) -> Path:
    #     """Create text file for a page"""
    #     text_dir = output_dir / "text"
    #     text_file = text_dir / f"page_{page_num}.txt"
    #     with open(text_file, 'w', encoding='utf-8') as f:
    #         f.write(text_content)
    #     return text_file
    
    def get_pdf_page_count(self, pdf_path: Path) -> int:
        """Get number of pages in PDF"""
        if not PYPDFIUM2_AVAILABLE:
            logger.warning("pypdfium2 not available, assuming 1 page")
            return 1
        
        try:
            pdf_doc = pdfium.PdfDocument(str(pdf_path))
            num_pages = len(pdf_doc)
            pdf_doc.close()
            return num_pages
        except Exception as e:
            logger.warning(f"Failed to get page count: {e}")
            return 1
    
    def create_fallback_output(self, doc_path: Path, output_dir: Path, timestamp: str, original_filename: str = None) -> Dict[str, Any]:
        """フォールバック処理：基本的なPDF情報のみ抽出"""
        logger.info("Creating fallback output structure")
        
        # Only images directory needed - all text data goes to metadata_hierarchy.json
        images_dir = output_dir / "images" 
        images_dir.mkdir(exist_ok=True)
        
        # pypdfium2でページ数取得
        num_pages = self.get_pdf_page_count(doc_path)
            
        # 各ページの基本テキスト抽出（OCR使用）
        pages_data = []
        for page_num in range(num_pages):
            page_data = {
                "page_number": page_num + 1,
                "layout_file": None,
                "image_file": None,
                "text_file": None,
                "text_content": "",
                "elements": []
            }
            
            # テキスト抽出（メタデータに直接格納、個別ファイル不要）
            try:
                if PYPDFIUM2_AVAILABLE:
                    # pypdfium2で画像を生成してOCR実行
                    pdf_doc = pdfium.PdfDocument(str(doc_path))
                    page = pdf_doc[page_num]
                    # 修正：render_to_pilではなくrenderを使用してからto_pilを呼び出す
                    bitmap = page.render(scale=2.0)
                    image = bitmap.to_pil()
                    
                    # Tesseract OCR実行（日本語と英語を試行）
                    try:
                        text_content = pytesseract.image_to_string(image, lang='jpn+eng')
                    except Exception as e:
                        logger.warning(f"OCR with jpn+eng failed: {e}, trying eng only")
                        try:
                            text_content = pytesseract.image_to_string(image, lang='eng')
                        except Exception as e2:
                            logger.warning(f"OCR with eng failed: {e2}, trying without lang specification")
                            text_content = pytesseract.image_to_string(image)
                    
                    # テキストはメタデータに直接格納（個別ファイル不要）
                    page_data["text_file"] = None
                    page_data["text_content"] = text_content[:500] + "..." if len(text_content) > 500 else text_content
                    
                    pdf_doc.close()
                else:
                    # pypdfium2が利用できない場合の処理
                    text_content = f"Page {page_num + 1} - OCR not available"
                    page_data["text_file"] = None
                    page_data["text_content"] = text_content
                
            except Exception as e:
                logger.warning(f"Failed to extract text from page {page_num + 1}: {e}")
                
            pages_data.append(page_data)
        
        # メタデータ作成
        filename_to_use = original_filename if original_filename else doc_path.name
        metadata = {
            "document_name": filename_to_use,
            "processing_timestamp": timestamp,
            "total_pages": num_pages,
            "pages": pages_data,
            "processing_mode": "fallback",
            "text_extraction": {
                "method": "tesseract_ocr",
                "ocr_enabled": True
            }
        }
        
        metadata_file = self.create_metadata_file(output_dir, metadata)
        
        return {
            "status": "success",
            "output_directory": str(output_dir.relative_to(self.output_base_dir.parent)),
            "files_created": {
                "original": str((output_dir / "original" / filename_to_use).relative_to(self.output_base_dir.parent)),
                "metadata": str(metadata_file.relative_to(self.output_base_dir.parent)),
                "images_dir": str(images_dir.relative_to(self.output_base_dir.parent))
            },
            "total_pages": num_pages,
            "processing_mode": "fallback",
            "original_filename": filename_to_use
        }