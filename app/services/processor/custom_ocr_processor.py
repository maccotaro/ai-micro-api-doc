"""
カスタムOCR処理
DoclingのTesseract処理をバイパスして独自のOCR処理を実装
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
import io
import pandas as pd

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import ConversionStatus

logger = logging.getLogger(__name__)


class CustomOCRProcessor:
    """カスタムOCR処理クラス（Tesseract KeyError回避）"""
    
    def __init__(self):
        self.tesseract_available = self._check_tesseract()
    
    def _check_tesseract(self) -> bool:
        """Tesseractの利用可能性をチェック"""
        try:
            result = subprocess.run(['tesseract', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False
    
    def process_pdf_with_custom_ocr(self, pdf_path: str, progress_callback=None) -> Tuple[bool, Dict[str, Any]]:
        """
        PDFをカスタムOCR処理で変換
        
        Returns:
            Tuple[success, extracted_data]
        """
        try:
            if not self.tesseract_available:
                logger.error("Tesseract not available")
                return False, {}
            
            if progress_callback:
                progress_callback(step=5, total=10, description="カスタムOCR処理を実行中...")
            
            # 1. PDFを画像に変換
            images_dir = self._pdf_to_images(pdf_path)
            if not images_dir:
                return False, {}
            
            # 2. 各画像にOCR処理を適用
            ocr_results = self._process_images_with_ocr(images_dir, progress_callback)
            
            # 3. 結果をDocling互換形式に変換
            docling_compatible_data = self._convert_to_docling_format(ocr_results)
            
            return True, docling_compatible_data
            
        except Exception as e:
            logger.error(f"Custom OCR processing failed: {e}")
            return False, {}
    
    def _pdf_to_images(self, pdf_path: str) -> Optional[Path]:
        """PDFを高解像度画像に変換"""
        try:
            temp_dir = Path(tempfile.mkdtemp())
            
            cmd = [
                'gs',
                '-sDEVICE=png16m',
                '-r300',  # 300 DPI
                '-dNOPAUSE', '-dQUIET', '-dBATCH',
                f'-sOutputFile={temp_dir}/page_%d.png',
                pdf_path
            ]
            
            logger.info(f"Converting PDF to images: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            
            if result.returncode != 0:
                logger.error(f"PDF to images conversion failed: {result.stderr}")
                return None
            
            # 生成された画像を確認
            image_files = list(temp_dir.glob('page_*.png'))
            if not image_files:
                logger.error("No images generated from PDF")
                return None
            
            logger.info(f"Generated {len(image_files)} images from PDF")
            return temp_dir
            
        except Exception as e:
            logger.error(f"PDF to images conversion error: {e}")
            return None
    
    def _process_images_with_ocr(self, images_dir: Path, progress_callback=None) -> List[Dict[str, Any]]:
        """画像にOCR処理を適用"""
        results = []
        image_files = sorted(images_dir.glob('page_*.png'))
        
        for i, image_file in enumerate(image_files):
            try:
                if progress_callback:
                    progress_callback(
                        step=5 + i, 
                        total=10, 
                        description=f"ページ {i+1}/{len(image_files)} をOCR処理中..."
                    )
                
                # TesseractでOCR処理（安全な方法）
                ocr_result = self._safe_tesseract_ocr(image_file)
                
                results.append({
                    'page_number': i + 1,
                    'image_path': str(image_file),
                    'text_content': ocr_result.get('text', ''),
                    'confidence': ocr_result.get('confidence', 0),
                    'word_details': ocr_result.get('words', [])
                })
                
            except Exception as e:
                logger.error(f"OCR processing failed for {image_file}: {e}")
                results.append({
                    'page_number': i + 1,
                    'image_path': str(image_file),
                    'text_content': '',
                    'confidence': 0,
                    'word_details': []
                })
        
        return results
    
    def _safe_tesseract_ocr(self, image_path: Path) -> Dict[str, Any]:
        """安全なTesseract OCR処理（KeyError回避）"""
        try:
            # 方法1: プレーンテキスト抽出
            text_cmd = [
                'tesseract', 
                str(image_path), 
                'stdout', 
                '-l', 'jpn+eng'
            ]
            
            logger.info(f"Running Tesseract text extraction: {' '.join(text_cmd)}")
            text_result = subprocess.run(text_cmd, capture_output=True, text=True, timeout=30)
            
            if text_result.returncode != 0:
                logger.warning(f"Tesseract text extraction failed: {text_result.stderr}")
                extracted_text = ""
            else:
                extracted_text = text_result.stdout.strip()
            
            # 方法2: 信頼度情報付きTSV抽出（エラー処理付き）
            confidence_data = self._extract_confidence_safely(image_path)
            
            return {
                'text': extracted_text,
                'confidence': confidence_data.get('avg_confidence', 0),
                'words': confidence_data.get('words', [])
            }
            
        except Exception as e:
            logger.error(f"Safe Tesseract OCR failed: {e}")
            return {
                'text': '',
                'confidence': 0,
                'words': []
            }
    
    def _extract_confidence_safely(self, image_path: Path) -> Dict[str, Any]:
        """安全な信頼度抽出（TSVエラー回避）"""
        try:
            # TSV形式で詳細情報を取得
            tsv_cmd = [
                'tesseract', 
                str(image_path), 
                'stdout', 
                '-l', 'jpn+eng',
                'tsv'
            ]
            
            result = subprocess.run(tsv_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                logger.warning("TSV extraction failed, using basic mode")
                return {'avg_confidence': 0, 'words': []}
            
            # TSVデータをパース（安全な方法）
            tsv_lines = result.stdout.strip().split('\n')
            if len(tsv_lines) < 2:  # ヘッダー + データ行が必要
                return {'avg_confidence': 0, 'words': []}
            
            # ヘッダーを解析
            header = tsv_lines[0].split('\t')
            
            # 必要なカラムの存在確認
            required_columns = ['conf', 'text']
            column_indices = {}
            
            for col in required_columns:
                try:
                    column_indices[col] = header.index(col)
                except ValueError:
                    logger.warning(f"Required column '{col}' not found in TSV header")
                    return {'avg_confidence': 0, 'words': []}
            
            # データ行を処理
            words = []
            confidences = []
            
            for line in tsv_lines[1:]:
                parts = line.split('\t')
                if len(parts) <= max(column_indices.values()):
                    continue
                
                try:
                    conf = float(parts[column_indices['conf']])
                    text = parts[column_indices['text']].strip()
                    
                    if text and conf > 0:  # 有効なテキストと信頼度
                        words.append({'text': text, 'confidence': conf})
                        confidences.append(conf)
                
                except (ValueError, IndexError):
                    continue
            
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            return {
                'avg_confidence': avg_confidence,
                'words': words
            }
            
        except Exception as e:
            logger.error(f"Confidence extraction failed: {e}")
            return {'avg_confidence': 0, 'words': []}
    
    def _convert_to_docling_format(self, ocr_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """OCR結果をDocling互換形式に変換"""
        try:
            total_pages = len(ocr_results)
            all_text = []
            
            for result in ocr_results:
                page_text = result.get('text_content', '')
                if page_text.strip():
                    all_text.append(f"=== Page {result['page_number']} ===\n{page_text}")
            
            combined_text = '\n\n'.join(all_text)
            
            # Docling互換のメタデータ構造
            docling_data = {
                'total_pages': total_pages,
                'processing_mode': 'custom_ocr',
                'text_extraction_method': 'tesseract_direct',
                'combined_text': combined_text,
                'page_results': ocr_results,
                'success': True
            }
            
            logger.info(f"Custom OCR completed: {total_pages} pages, {len(combined_text)} characters")
            
            return docling_data
            
        except Exception as e:
            logger.error(f"Docling format conversion failed: {e}")
            return {'success': False, 'error': str(e)}