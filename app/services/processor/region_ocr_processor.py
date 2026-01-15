"""
Region OCR Processor
矩形エリア指定でのOCR処理を実行するモジュール
"""

import logging
import tempfile
import subprocess
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from PIL import Image
import io
import numpy as np

logger = logging.getLogger(__name__)

# GPU detection
try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
    logger.info(f"GPU detection: {'GPU available' if GPU_AVAILABLE else 'GPU not available, using CPU'}")
except ImportError:
    GPU_AVAILABLE = False
    logger.warning("PyTorch not available, GPU detection disabled")

# EasyOCR import with fallback
try:
    import easyocr
    EASYOCR_AVAILABLE = True
    logger.info("EasyOCR is available")
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.warning("EasyOCR not available, falling back to Tesseract only")


class RegionOCRProcessor:
    """矩形エリア指定でのOCR処理クラス"""
    
    def __init__(self):
        self.tesseract_available = self._check_tesseract()
        self.easyocr_reader = None
        
        # Initialize EasyOCR if available
        if EASYOCR_AVAILABLE:
            try:
                # Initialize with Japanese and English, auto-detect GPU
                use_gpu = GPU_AVAILABLE
                self.easyocr_reader = easyocr.Reader(['ja', 'en'], gpu=use_gpu)
                logger.info(f"EasyOCR reader initialized successfully (GPU: {use_gpu})")
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                self.easyocr_reader = None
    
    def _check_tesseract(self) -> bool:
        """Tesseractの利用可能性をチェック"""
        try:
            result = subprocess.run(['tesseract', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False
    
    def process_region_ocr(
        self, 
        image_path: str,
        x: float, 
        y: float, 
        width: float, 
        height: float,
        page_width: float = 595.32,  # A4幅（ポイント）
        page_height: float = 841.92  # A4高さ（ポイント）
    ) -> Dict[str, Any]:
        """
        指定された矩形エリアのOCRを実行
        
        Args:
            image_path: 元画像のパス
            x, y: 矩形の左上座標（PDF座標系）
            width, height: 矩形のサイズ（PDF座標系）
            page_width, page_height: PDFページサイズ
            
        Returns:
            OCR結果を含む辞書
        """
        try:
            # 画像の読み込み
            image = Image.open(image_path)
            img_width, img_height = image.size
            
            # PDF座標系から画像座標系への変換
            # PDF座標系（左下原点）→ 画像座標系（左上原点）
            scale_x = img_width / page_width
            scale_y = img_height / page_height
            
            logger.info(f"Image size: {img_width}x{img_height}, Page size: {page_width}x{page_height}")
            logger.info(f"Scale factors: scale_x={scale_x}, scale_y={scale_y}")
            
            # フロントエンド座標をrectangleScale=2.0で補正
            rectangle_scale = 2.0
            img_x = int(x * rectangle_scale)
            img_y = int(y * rectangle_scale)  
            img_width_crop = int(width * rectangle_scale)
            img_height_crop = int(height * rectangle_scale)
            
            logger.info(f"Frontend coords: ({x}, {y}, {width}, {height})")
            logger.info(f"Scaled coords: ({img_x}, {img_y}, {img_width_crop}, {img_height_crop})")
            
            logger.info(f"Before clipping: img_x={img_x}, img_y={img_y}, img_width_crop={img_width_crop}, img_height_crop={img_height_crop}")
            
            # 画像サイズ内にクリップ
            img_x = max(0, min(img_x, img_width))
            img_y = max(0, min(img_y, img_height))
            img_width_crop = max(1, min(img_width_crop, img_width - img_x))
            img_height_crop = max(1, min(img_height_crop, img_height - img_y))
            
            logger.info(f"OCR region - PDF coords: ({x}, {y}, {width}, {height})")
            logger.info(f"OCR region - Image coords: ({img_x}, {img_y}, {img_width_crop}, {img_height_crop})")
            
            # 矩形エリアをクロップ
            crop_box = (img_x, img_y, img_x + img_width_crop, img_y + img_height_crop)
            cropped_image = image.crop(crop_box)
            
            # デバッグ用: クロップした画像を保存
            debug_path = f"/tmp/debug_crop_{int(x)}_{int(y)}_{int(width)}_{int(height)}.png"
            cropped_image.save(debug_path)
            logger.info(f"Debug: Cropped image saved to {debug_path}")
            logger.info(f"Debug: Cropped image size: {cropped_image.size}")
            
            # OCR実行 (EasyOCR優先、Tesseractフォールバック)
            ocr_text, confidence = self._perform_ocr_with_fallback(cropped_image)
            
            return {
                "text": ocr_text,
                "confidence": confidence,
                "coordinates": {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height
                },
                "image_coordinates": {
                    "x": img_x,
                    "y": img_y,
                    "width": img_width_crop,
                    "height": img_height_crop
                },
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Region OCR processing failed: {e}")
            return {
                "text": "",
                "confidence": 0.0,
                "error": str(e),
                "success": False
            }
    
    def _perform_ocr(self, image: Image.Image) -> Tuple[str, float]:
        """
        画像に対してOCR処理を実行
        
        Args:
            image: OCRを実行する画像（PIL Image）
            
        Returns:
            Tuple[OCR結果テキスト, 信頼度スコア]
        """
        if not self.tesseract_available:
            logger.warning("Tesseract not available, returning empty result")
            return "", 0.0
        
        try:
            # 一時ファイルに画像を保存
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                image.save(temp_file.name, format='PNG')
                temp_path = temp_file.name
            
            try:
                # TesseractでOCR実行（日本語 + 英語）
                result = subprocess.run([
                    'tesseract', 
                    temp_path, 
                    'stdout', 
                    '-l', 'jpn+eng',
                    '--psm', '6',  # Uniform block of text
                    '-c', 'preserve_interword_spaces=1'
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    ocr_text = result.stdout.strip()
                    
                    # 信頼度取得を試行（TSV出力）
                    confidence = self._get_confidence(temp_path)
                    
                    logger.info(f"OCR result: '{ocr_text}' (confidence: {confidence})")
                    return ocr_text, confidence
                else:
                    logger.error(f"Tesseract error: {result.stderr}")
                    return "", 0.0
                    
            finally:
                # 一時ファイル削除
                Path(temp_path).unlink(missing_ok=True)
                
        except subprocess.TimeoutExpired:
            logger.error("OCR processing timeout")
            return "", 0.0
        except Exception as e:
            logger.error(f"OCR processing error: {e}")
            return "", 0.0
    
    def _get_confidence(self, image_path: str) -> float:
        """
        OCR結果の信頼度スコアを取得
        
        Args:
            image_path: 画像ファイルパス
            
        Returns:
            信頼度スコア（0-100）
        """
        try:
            # TSV形式で詳細な結果を取得
            result = subprocess.run([
                'tesseract', 
                image_path, 
                'stdout', 
                '-l', 'jpn+eng',
                '--psm', '6',
                'tsv'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                confidences = []
                
                for line in lines[1:]:  # ヘッダーをスキップ
                    fields = line.split('\t')
                    if len(fields) >= 10 and fields[9]:  # confidenceフィールド
                        try:
                            conf = float(fields[9])
                            if conf > 0:  # 有効な信頼度のみ
                                confidences.append(conf)
                        except (ValueError, IndexError):
                            continue
                
                if confidences:
                    avg_confidence = sum(confidences) / len(confidences)
                    return round(avg_confidence, 2)
            
            return 0.0
            
        except Exception as e:
            logger.warning(f"Failed to get confidence score: {e}")
            return 0.0
    
    def _perform_ocr_with_fallback(self, image: Image.Image) -> Tuple[str, float]:
        """
        EasyOCRを優先してOCRを実行、失敗時はTesseractにフォールバック
        
        Args:
            image: OCRを実行する画像（PIL Image）
            
        Returns:
            Tuple[OCR結果テキスト, 信頼度スコア]
        """
        # EasyOCRを試行
        if self.easyocr_reader is not None:
            try:
                logger.info("Attempting OCR with EasyOCR")
                ocr_text, confidence = self._perform_easyocr(image)
                if ocr_text.strip():  # 結果が空でない場合
                    logger.info(f"EasyOCR succeeded: '{ocr_text}' (confidence: {confidence})")
                    return ocr_text, confidence
                else:
                    logger.warning("EasyOCR returned empty result, falling back to Tesseract")
            except Exception as e:
                logger.error(f"EasyOCR failed: {e}, falling back to Tesseract")
        
        # Tesseractにフォールバック
        logger.info("Using Tesseract OCR")
        return self._perform_ocr(image)
    
    def _perform_easyocr(self, image: Image.Image) -> Tuple[str, float]:
        """
        EasyOCRでOCR処理を実行
        
        Args:
            image: OCRを実行する画像（PIL Image）
            
        Returns:
            Tuple[OCR結果テキスト, 信頼度スコア]
        """
        try:
            # PIL ImageをNumPy配列に変換
            image_np = np.array(image)
            
            # EasyOCRで処理
            results = self.easyocr_reader.readtext(image_np)
            
            if not results:
                return "", 0.0
            
            # 結果を統合
            texts = []
            confidences = []
            
            for (bbox, text, confidence) in results:
                if text.strip() and confidence > 0.1:  # 低信頼度テキストを除外
                    texts.append(text.strip())
                    confidences.append(confidence)
            
            if not texts:
                return "", 0.0
            
            # テキストを結合
            combined_text = '\n'.join(texts)
            
            # 平均信頼度を計算
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            confidence_percentage = round(avg_confidence * 100, 2)
            
            logger.info(f"EasyOCR found {len(texts)} text regions")
            return combined_text, confidence_percentage
            
        except Exception as e:
            logger.error(f"EasyOCR processing error: {e}")
            raise
    
