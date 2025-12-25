"""
Text extraction utilities for document processing.
Handles text content extraction from various document elements and OCR operations.
"""

import logging
import re
from typing import Dict, Any


def clean_docling_text(text: str) -> str:
    """Doclingが生成する非標準テキストをクリーンアップ"""
    if not text:
        return ""
    text = re.sub(r'<non-compliant-utf8-text>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

# GPU detection
try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
except ImportError:
    GPU_AVAILABLE = False

from PIL import Image
import pytesseract

from .utils import get_element_type

logger = logging.getLogger(__name__)


class TextExtractor:
    """Text extraction for document analysis operations"""
    
    def __init__(self, easyocr_cache_dir=None):
        self.easyocr_cache_dir = easyocr_cache_dir
        self._easyocr_reader = None
    
    def get_easyocr_reader(self):
        """Get or initialize EasyOCR reader with caching"""
        if not EASYOCR_AVAILABLE:
            return None
        
        if self._easyocr_reader is None:
            try:
                use_gpu = GPU_AVAILABLE
                logger.info(f"Initializing EasyOCR reader (GPU: {use_gpu})...")
                # モデルをキャッシュディレクトリに保存
                if self.easyocr_cache_dir:
                    self._easyocr_reader = easyocr.Reader(
                        ['ja', 'en'],
                        gpu=use_gpu,
                        model_storage_directory=str(self.easyocr_cache_dir)
                    )
                else:
                    self._easyocr_reader = easyocr.Reader(['ja', 'en'], gpu=use_gpu)
                logger.info(f"EasyOCR reader initialized successfully (GPU: {use_gpu})")
            except Exception as e:
                logger.warning(f"Failed to initialize EasyOCR: {e}")
                self._easyocr_reader = None
        
        return self._easyocr_reader
    
    def extract_text_from_element(self, element) -> str:
        """要素からテキスト内容を抽出（改良版・テーブル対応）"""
        try:
            # テーブル要素の場合は構造化データを抽出
            if hasattr(element, 'data') and hasattr(element.data, 'table_cells'):
                return self.extract_table_text(element)
            
            # 方法1: text属性
            if hasattr(element, 'text') and element.text:
                return clean_docling_text(str(element.text).strip())

            # 方法2: content属性
            if hasattr(element, 'content') and element.content:
                return clean_docling_text(str(element.content).strip())

            # 方法3: export_to_text()メソッド
            if hasattr(element, 'export_to_text'):
                return clean_docling_text(str(element.export_to_text()).strip())
            
            # 方法4: 要素タイプを確認して適切なテキストを抽出
            element_type = get_element_type(element)
            if element_type in ['Table', 'table']:
                return self.extract_table_text(element)
            
            # 方法5: __str__()メソッド（オブジェクト表現は避ける）
            text_str = str(element).strip()
            if text_str and not text_str.startswith('<') and 'self_ref=' not in text_str:
                return clean_docling_text(text_str)
        
        except Exception as e:
            logger.debug(f"Failed to extract text from element: {e}")
        
        return ""
    
    def extract_table_text(self, table_element) -> str:
        """テーブル要素からテキストを抽出"""
        try:
            text_parts = []
            
            # 方法1: data.table属性（Docling v1.7.0+）
            if hasattr(table_element, 'data') and hasattr(table_element.data, 'table'):
                table_data = table_element.data.table
                
                if hasattr(table_data, 'rows'):
                    for row in table_data.rows:
                        row_text = []
                        if hasattr(row, 'cells'):
                            for cell in row.cells:
                                if hasattr(cell, 'text') and cell.text:
                                    row_text.append(clean_docling_text(str(cell.text).strip()))
                        if row_text:
                            text_parts.append(" | ".join(row_text))
            
            # 方法2: table_cells属性
            elif hasattr(table_element, 'data') and hasattr(table_element.data, 'table_cells'):
                cells_data = table_element.data.table_cells
                for cell in cells_data:
                    if hasattr(cell, 'text') and cell.text:
                        text_parts.append(clean_docling_text(str(cell.text).strip()))
            
            # 方法3: テーブル内のテキスト要素を直接抽出
            elif hasattr(table_element, 'elements'):
                for sub_element in table_element.elements:
                    sub_text = self.extract_text_from_element(sub_element)
                    if sub_text:
                        text_parts.append(sub_text)
            
            result_text = "\n".join(text_parts) if text_parts else "Table content"
            logger.debug(f"Extracted table text: {result_text[:100]}...")
            return result_text
            
        except Exception as e:
            logger.warning(f"Error extracting table text: {e}")
            return "Table content"
    
    def extract_text_content(self, item) -> str:
        """Docling要素からテキスト内容を抽出"""
        if hasattr(item, 'text') and item.text:
            return clean_docling_text(str(item.text).strip())[:200]
        elif hasattr(item, 'content') and item.content:
            return clean_docling_text(str(item.content).strip())[:200]
        elif hasattr(item, 'value') and item.value:
            return clean_docling_text(str(item.value).strip())[:200]
        return ""
    
    def extract_text_with_tesseract(self, image_path: str, languages: str = 'jpn+eng') -> str:
        """Tesseract OCRを使用してテキストを抽出"""
        try:
            with Image.open(image_path) as img:
                try:
                    text = pytesseract.image_to_string(img, lang=languages)
                    return text.strip()
                except Exception as e:
                    logger.warning(f"Tesseract OCR with {languages} failed: {e}")
                    # フォールバック: 英語のみ
                    try:
                        text = pytesseract.image_to_string(img, lang='eng')
                        return text.strip()
                    except Exception as e2:
                        logger.warning(f"Tesseract OCR with eng failed: {e2}")
                        # 最終フォールバック: 言語指定なし
                        text = pytesseract.image_to_string(img)
                        return text.strip()
        except Exception as e:
            logger.error(f"Failed to extract text with Tesseract: {e}")
            return ""
    
    def extract_text_with_easyocr(self, image_path: str) -> str:
        """EasyOCRを使用してテキストを抽出"""
        try:
            reader = self.get_easyocr_reader()
            if not reader:
                logger.warning("EasyOCR not available")
                return ""
            
            results = reader.readtext(image_path)
            text_parts = []
            
            for (bbox, text, confidence) in results:
                if confidence > 0.5:  # 信頼度閾値
                    text_parts.append(text.strip())
            
            return " ".join(text_parts)
            
        except Exception as e:
            logger.error(f"Failed to extract text with EasyOCR: {e}")
            return ""
    
    def extract_text_from_image(self, image_path: str, prefer_easyocr: bool = True) -> str:
        """画像からテキストを抽出（EasyOCRまたはTesseractを使用）"""
        if prefer_easyocr and EASYOCR_AVAILABLE:
            text = self.extract_text_with_easyocr(image_path)
            if text:
                return text
            
            # EasyOCRで失敗した場合、Tesseractにフォールバック
            logger.info("EasyOCR failed, falling back to Tesseract")
        
        return self.extract_text_with_tesseract(image_path)