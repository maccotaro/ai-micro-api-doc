"""
PDF前処理フォールバック処理
日本語PDF特有のエンコーディング問題を解決するための段階的前処理
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
import shutil
import time
import json
from datetime import datetime

from docling.document_converter import DocumentConverter
from docling.datamodel.base_models import ConversionStatus

logger = logging.getLogger(__name__)

# GPU detection
try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
except ImportError:
    GPU_AVAILABLE = False


class PDFPreprocessor:
    """PDF前処理とDocling処理の組み合わせクラス"""
    
    def __init__(self, docling_converter: DocumentConverter, output_dir: Optional[str] = None):
        self.docling_converter = docling_converter
        self.output_dir = Path(output_dir) if output_dir else None

    def _log_pdf_preprocessor_progress(self, description: str, step: int, total: int, start_time: float = None, progress_callback=None):
        """PDF前処理専用の進捗ログを出力"""
        current_time = time.time()
        elapsed = round(current_time - start_time, 2) if start_time else 0

        # progress_callbackを呼び出し
        if progress_callback:
            progress_callback(step=step, total=total, description=description)

        # 詳細な進捗ログを出力
        progress_log = {
            "timestamp": datetime.now().isoformat(),
            "component": "PDFPreprocessor",
            "operation": "pdf_preprocessing",
            "step": step,
            "total_steps": total,
            "percentage": round((step / total) * 100, 1) if total > 0 else 0,
            "description": description,
            "elapsed_seconds": elapsed,
            "frontend_format": {
                "status_text": description,
                "step_display": f"ステップ {step}/{total}",
                "percentage_display": f"{(step / total) * 100:.1f}%" if total > 0 else "0.0%"
            }
        }
        logger.info(f"🔧 PDF_PREPROCESSOR_PROGRESS: {json.dumps(progress_log, ensure_ascii=False)}")
    
    def process_with_fallback(self, pdf_path: str, progress_callback=None) -> Tuple[bool, any, str]:
        """
        フォールバック処理でPDFを処理

        Returns:
            Tuple[success, document, method_used]
        """
        start_time = time.time()
        pdf_path = Path(pdf_path)

        # 0. まずEasyOCRで直接処理を試行（スキャンPDF用）
        self._log_pdf_preprocessor_progress(
            "EasyOCR処理を試行中...",
            step=3, total=10, start_time=start_time, progress_callback=progress_callback
        )

        success, document = self._try_easyocr_direct(pdf_path)
        if success:
            logger.info("EasyOCR直接処理が成功")
            return True, document, "easyocr_direct"

        # 1. qpdf前処理 + Docling
        self._log_pdf_preprocessor_progress(
            "qpdf前処理を試行中...",
            step=3, total=10, start_time=start_time, progress_callback=progress_callback
        )

        success, document = self._try_qpdf_preprocessing(pdf_path)
        if success:
            logger.info("qpdf前処理 + Docling処理が成功")
            return True, document, "qpdf_docling"

        # 2. Ghostscript前処理 + Docling
        self._log_pdf_preprocessor_progress(
            "Ghostscript前処理を試行中...",
            step=4, total=10, start_time=start_time, progress_callback=progress_callback
        )

        success, document = self._try_ghostscript_preprocessing(pdf_path)
        if success:
            logger.info("Ghostscript前処理 + Docling処理が成功")
            return True, document, "ghostscript_docling"

        # 3. 画像化 + Docling OCR
        self._log_pdf_preprocessor_progress(
            "画像化OCR処理を試行中...",
            step=5, total=10, start_time=start_time, progress_callback=progress_callback
        )

        success, document = self._try_image_ocr_processing(pdf_path)
        if success:
            logger.info("画像化 + Docling OCR処理が成功")
            return True, document, "image_ocr_docling"

        logger.error("全ての前処理方法が失敗しました")
        return False, None, "all_failed"
    
    def _try_easyocr_direct(self, pdf_path: Path) -> Tuple[bool, any]:
        """EasyOCRで直接処理（スキャンPDF用）"""
        try:
            logger.info("Attempting direct EasyOCR processing for scanned PDF...")

            from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption
            from docling.datamodel.base_models import InputFormat

            # EasyOCRオプション（bounding box自動検出）
            use_gpu = GPU_AVAILABLE
            ocr_options = EasyOcrOptions(
                lang=['ja', 'en'],  # 日本語と英語
                use_gpu=use_gpu,  # GPU auto-detection
                force_full_page_ocr=True,  # 非標準フォントエンコーディング対策
            )
            logger.info(f"EasyOCR direct processing with GPU: {use_gpu}, force_full_page_ocr=True")

            pdf_pipeline = PdfPipelineOptions(
                do_ocr=True,
                ocr_options=ocr_options,
                do_table_structure=True,  # EasyOCRはテーブル構造も検出可能
            )

            format_options = {InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_pipeline)}
            converter = DocumentConverter(format_options=format_options)
            
            logger.info(f"Running EasyOCR on: {pdf_path}")
            conversion_result = converter.convert(pdf_path)

            if conversion_result.status == ConversionStatus.SUCCESS:
                document = conversion_result.document

                # DoclingDocumentの確認（Docling 2.65.0+ API）
                from docling_core.types.doc.document import DoclingDocument
                if isinstance(document, DoclingDocument):
                    # Docling 2.65.0+: textsプロパティまたはbody.childrenをチェック
                    has_content = (hasattr(document, 'texts') and list(document.texts)) or \
                                  (hasattr(document, 'body') and document.body.children)
                    if has_content:
                        text_count = len(list(document.texts)) if hasattr(document, 'texts') else len(document.body.children)
                        logger.info(f"EasyOCR successfully extracted {text_count} text elements with bounding boxes")
                        return True, document
                    else:
                        logger.warning("EasyOCR produced document with no text content")
                        return False, None
                else:
                    logger.info("EasyOCR produced non-DoclingDocument format")
                    return True, document
            else:
                logger.warning(f"EasyOCR conversion failed: {conversion_result.status}")
                return False, None
                
        except ImportError as e:
            logger.warning(f"EasyOCR not available: {e}")
            return False, None
        except Exception as e:
            logger.warning(f"EasyOCR direct processing failed: {e}")
            return False, None
    
    def _try_qpdf_preprocessing(self, pdf_path: Path) -> Tuple[bool, any]:
        """qpdf前処理 + Docling処理"""
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_pdf_path = Path(temp_file.name)
            
            # qpdfでPDF構造を正規化（日本語エンコーディング問題対応）
            cmd = [
                'qpdf',
                '--qdf',                      # 構造を標準化
                '--object-streams=disable',   # オブジェクトストリームを無効化
                '--normalize-content=y',      # コンテンツを正規化
                '--filtered-stream-data',     # フィルター済みストリームデータを展開
                '--decode-level=all',         # 全てのストリームをデコード
                str(pdf_path),
                str(temp_pdf_path)
            ]
            
            logger.info(f"Running qpdf preprocessing: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                logger.warning(f"qpdf preprocessing failed: {result.stderr}")
                return False, None
            
            # qpdf処理結果をoutputディレクトリにも保存
            if self.output_dir and self.output_dir.exists():
                qpdf_output_path = self.output_dir / f"{pdf_path.stem}_qpdf_processed.pdf"
                shutil.copy2(temp_pdf_path, qpdf_output_path)
                logger.info(f"qpdf processed PDF saved to: {qpdf_output_path}")
            
            # Docling処理を実行
            success, document = self._try_docling_conversion(temp_pdf_path)
            
            # 一時ファイルクリーンアップ
            temp_pdf_path.unlink(missing_ok=True)
            
            return success, document
            
        except Exception as e:
            logger.error(f"qpdf preprocessing error: {e}")
            return False, None
    
    def _try_ghostscript_preprocessing(self, pdf_path: Path) -> Tuple[bool, any]:
        """Ghostscript前処理 + Docling処理"""
        # 複数のGhostscriptアプローチを試行
        approaches = [
            self._ghostscript_docling_compatible_fonts,  # Docling互換フォントへの置き換え
            self._ghostscript_font_preserving_approach,  # フォント保持重視
            self._ghostscript_minimal_approach  # 最小限の処理
        ]
        
        for i, approach in enumerate(approaches):
            try:
                approach_name = approach.__name__.replace('_ghostscript_', '').replace('_', ' ')
                logger.info(f"Trying Ghostscript approach {i+1}/{len(approaches)}: {approach_name}")
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                    temp_pdf_path = Path(temp_file.name)
                
                success = approach(pdf_path, temp_pdf_path)
                if not success:
                    temp_pdf_path.unlink(missing_ok=True)
                    continue
                
                # Ghostscript処理結果をoutputディレクトリにも保存
                if self.output_dir and self.output_dir.exists():
                    approach_suffix = approach.__name__.replace('_ghostscript_', '').replace('_approach', '')
                    gs_output_path = self.output_dir / f"{pdf_path.stem}_ghostscript_{approach_suffix}.pdf"
                    shutil.copy2(temp_pdf_path, gs_output_path)
                    logger.info(f"Ghostscript processed PDF saved to: {gs_output_path}")
                
                # Docling処理を実行
                success, document = self._try_docling_conversion(temp_pdf_path)
                
                # 一時ファイルクリーンアップ
                temp_pdf_path.unlink(missing_ok=True)
                
                if success:
                    logger.info(f"Ghostscript approach {i+1} succeeded")
                    return success, document
                
            except Exception as e:
                logger.warning(f"Ghostscript approach {i+1} failed: {e}")
                continue
        
        logger.error("All Ghostscript approaches failed")
        return False, None
    
    def _ghostscript_docling_compatible_fonts(self, pdf_path: Path, temp_pdf_path: Path) -> bool:
        """Docling互換の日本語フォントに置き換えるGhostscriptアプローチ"""
        # 利用可能な日本語フォントを検出
        target_font = self._detect_available_japanese_font()
        logger.info(f"Using Japanese font for replacement: {target_font}")
        
        # CIDフォントマップファイルを作成（標準的な日本語フォントにマッピング）
        # 検出されたフォントまたはデフォルトフォントを使用
        cid_fontmap = f"""
% Adobe Japan1 CID fonts to Unicode fonts mapping
/Ryumin-Light /{target_font} ;
/GothicBBB-Medium /{target_font} ;
/HeiseiMin-W3 /{target_font} ;
/HeiseiKakuGo-W5 /{target_font} ;
/MS-Mincho /{target_font} ;
/MS-Gothic /{target_font} ;
/MS-PMincho /{target_font} ;
/MS-PGothic /{target_font} ;
/MidashiGo-MB31 /{target_font} ;
/MidashiMin-MA31 /{target_font} ;
/Jun101-Light /{target_font} ;
/HiraMinPro-W3 /{target_font} ;
/HiraKakuPro-W3 /{target_font} ;
/HiraMaruPro-W4 /{target_font} ;
/KozGoPr6N-Regular /{target_font} ;
/KozMinPr6N-Regular /{target_font} ;
        """
        
        # 一時的なフォントマップファイルを作成
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.map', delete=False) as fontmap_file:
            fontmap_file.write(cid_fontmap)
            fontmap_path = fontmap_file.name
        
        try:
            cmd = [
                'gs',
                '-sDEVICE=pdfwrite',
                '-dCompatibilityLevel=1.7',
                '-dNOPAUSE', '-dQUIET', '-dBATCH',
                '-dPDFSETTINGS=/printer',  # プリンター品質（フォント埋め込み重視）
                # 日本語フォントの処理
                '-dSubsetFonts=false',      # フォント全体を埋め込み（サブセット化しない）
                '-dEmbedAllFonts=true',     # 全フォントを埋め込み
                '-dCompressFonts=false',    # フォント圧縮を無効化（文字化け防止）
                # CIDフォントの置き換え設定
                '-dNOCIDFONTMAP',           # デフォルトのCIDフォントマップを無効化
                f'-sFONTMAP={fontmap_path}', # カスタムフォントマップを使用
                # テキスト抽出の最適化
                '-dDetectDuplicateImages=false',  # 重複画像検出を無効化
                '-dConvertCMYKImagesToRGB=false', # CMYK画像変換を無効化
                '-dUseFlateCompression=true',     # Flate圧縮を使用（テキスト向け）
                # 出力設定
                f'-sOutputFile={temp_pdf_path}',
                str(pdf_path)
            ]
            
            logger.info(f"Running Ghostscript with Docling-compatible fonts: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                logger.warning(f"Ghostscript Docling-compatible fonts approach failed: {result.stderr}")
                return False
            
            logger.info("Ghostscript successfully replaced fonts with Docling-compatible ones")
            return True
            
        finally:
            # フォントマップファイルをクリーンアップ
            Path(fontmap_path).unlink(missing_ok=True)
    
    def _ghostscript_font_preserving_approach(self, pdf_path: Path, temp_pdf_path: Path) -> bool:
        """フォント保持重視のGhostscriptアプローチ"""
        cmd = [
            'gs',
            '-sDEVICE=pdfwrite',
            '-dCompatibilityLevel=1.7',
            '-dNOPAUSE', '-dQUIET', '-dBATCH',
            '-dPDFSETTINGS=/prepress',  # 高品質設定
            '-dSubsetFonts=true',       # フォントサブセットを保持
            '-dEmbedAllFonts=true',     # 全フォントを埋め込み
            '-dCompressFonts=false',    # フォント圧縮を無効化
            '-dOptimize=false',         # 最適化を無効化してフォントを保持
            '-dPreserveAnnots=true',    # 注釈を保持
            '-dPreserveCopyPage=true',  # ページコピーを保持
            '-dPreserveMarkedContent=true',  # マークされたコンテンツを保持
            f'-sOutputFile={temp_pdf_path}',
            str(pdf_path)
        ]
        
        logger.info(f"Running Ghostscript font-preserving approach: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            logger.warning(f"Ghostscript font-preserving approach failed: {result.stderr}")
            return False
        
        return True
    
    def _ghostscript_minimal_approach(self, pdf_path: Path, temp_pdf_path: Path) -> bool:
        """最小限の処理でPDF構造を正規化するGhostscriptアプローチ"""
        cmd = [
            'gs',
            '-sDEVICE=pdfwrite',
            '-dCompatibilityLevel=1.7',
            '-dNOPAUSE', '-dQUIET', '-dBATCH',
            '-dAutoRotatePages=/None',     # 自動回転を無効化
            '-dAutoFilterColorImages=false', # 色画像フィルタを無効化
            '-dAutoFilterGrayImages=false',  # グレー画像フィルタを無効化
            '-dDownsampleColorImages=false', # 色画像ダウンサンプル無効化
            '-dDownsampleGrayImages=false',  # グレー画像ダウンサンプル無効化
            f'-sOutputFile={temp_pdf_path}',
            str(pdf_path)
        ]
        
        logger.info(f"Running Ghostscript minimal approach: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode != 0:
            logger.warning(f"Ghostscript minimal approach failed: {result.stderr}")
            return False
        
        return True
    
    def _try_image_ocr_processing(self, pdf_path: Path) -> Tuple[bool, any]:
        """画像化 + カスタムOCR処理（Docling KeyError回避）"""
        try:
            logger.info("Trying custom OCR processing to avoid Docling KeyError")
            
            # カスタムOCR処理を使用
            from .custom_ocr_processor import CustomOCRProcessor
            
            custom_ocr = CustomOCRProcessor()
            success, ocr_data = custom_ocr.process_pdf_with_custom_ocr(str(pdf_path))
            
            if success and ocr_data.get('success'):
                logger.info("Custom OCR processing successful")
                
                # カスタムOCR結果をDocling互換の疑似ドキュメントオブジェクトに変換
                mock_document = self._create_mock_document_from_ocr(ocr_data)
                return True, mock_document
            else:
                logger.warning("Custom OCR processing failed")
                
                # フォールバック: 元のDocling OCR処理を試行
                logger.info("Falling back to original Docling OCR (may encounter KeyError)")
                success, document = self._try_docling_conversion_force_ocr(pdf_path)
                return success, document
                
        except Exception as e:
            logger.error(f"Image OCR processing error: {e}")
            return False, None
    
    def _create_mock_document_from_ocr(self, ocr_data: Dict[str, Any]) -> Any:
        """カスタムOCR結果からDocling互換の疑似ドキュメントを作成"""
        try:
            # 疑似ドキュメントクラス（Docling形式を模倣）
            class MockDocument:
                def __init__(self, ocr_data):
                    self.processing_mode = 'custom_ocr'
                    self.total_pages = ocr_data.get('total_pages', 0)
                    self.combined_text = ocr_data.get('combined_text', '')
                    self.page_results = ocr_data.get('page_results', [])
                    self._original_pdf_path = None
                    self._processing_method = 'custom_ocr'
                    
                    # main_text属性を模倣（layout_extractorで使用）
                    self.main_text = []
                    for i, page_result in enumerate(self.page_results):
                        if page_result.get('text_content'):
                            # MockTextElementを作成
                            text_element = MockTextElement(
                                text=page_result['text_content'],
                                page_number=i + 1
                            )
                            self.main_text.append(text_element)
                    
                    # pages属性を模倣
                    self.pages = [f"Page {i+1}" for i in range(self.total_pages)]
            
            class MockTextElement:
                def __init__(self, text, page_number):
                    self.text = text
                    self.page_number = page_number
                    
                def export(self):
                    return {'text': self.text, 'page': self.page_number}
            
            mock_doc = MockDocument(ocr_data)
            logger.info(f"Created mock document with {len(mock_doc.main_text)} text elements")
            
            return mock_doc
            
        except Exception as e:
            logger.error(f"Mock document creation failed: {e}")
            return None
    
    def _try_docling_conversion(self, pdf_path: Path) -> Tuple[bool, any]:
        """Docling変換を試行（シンプルな設定で高速化）"""
        try:
            logger.info(f"Attempting Docling conversion: {pdf_path}")

            # PDF version 1.3など古いPDFに対応するため、最小限の設定で試行
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import PdfFormatOption
            from docling.datamodel.base_models import InputFormat

            # 最初は最小限の設定で高速に試行
            minimal_pipeline = PdfPipelineOptions(
                do_ocr=False,  # OCRを無効化（高速化）
                do_table_structure=False,  # テーブル構造解析を無効化
            )

            # 新しいコンバーターインスタンスを作成
            format_options = {InputFormat.PDF: PdfFormatOption(pipeline_options=minimal_pipeline)}
            minimal_converter = DocumentConverter(format_options=format_options)
            
            try:
                logger.info("Trying minimal Docling conversion (no OCR, no table structure)")
                conversion_result = minimal_converter.convert(pdf_path)

                if conversion_result.status == ConversionStatus.SUCCESS:
                    logger.info("Minimal Docling conversion successful")
                    document = conversion_result.document

                    # DoclingDocumentの場合（Docling 2.65.0+ API）
                    from docling_core.types.doc.document import DoclingDocument
                    if isinstance(document, DoclingDocument):
                        # Docling 2.65.0+: textsプロパティまたはbody.childrenをチェック
                        has_content = (hasattr(document, 'texts') and list(document.texts)) or \
                                      (hasattr(document, 'body') and document.body.children)
                        if has_content:
                            text_count = len(list(document.texts)) if hasattr(document, 'texts') else len(document.body.children)
                            logger.info(f"Successfully extracted {text_count} text elements")
                            return True, document
                        else:
                            logger.warning("Document has no text content, trying with OCR")
                            # OCRが必要な場合は失敗として次の方法へ
                            return False, None
                    else:
                        # 従来のDocument形式
                        return True, document
                else:
                    logger.warning(f"Minimal Docling conversion failed with status: {conversion_result.status}")
                    return False, None
                    
            except Exception as inner_e:
                logger.warning(f"Minimal conversion failed: {inner_e}")
                
                # フォールバック：デフォルト設定で再試行
                try:
                    logger.info("Falling back to default Docling settings")
                    conversion_result = self.docling_converter.convert(pdf_path)

                    if conversion_result.status == ConversionStatus.SUCCESS:
                        logger.info("Default Docling conversion successful")
                        return True, conversion_result.document
                    else:
                        logger.warning(f"Default Docling conversion failed with status: {conversion_result.status}")
                        return False, None
                        
                except Exception as fallback_e:
                    logger.error(f"Default conversion also failed: {fallback_e}")
                    return False, None
                
        except Exception as e:
            logger.error(f"Docling conversion error: {e}")
            return False, None
    
    def _try_docling_conversion_force_ocr(self, pdf_path: Path) -> Tuple[bool, any]:
        """OCR強制モードでDocling変換を試行（EasyOCR優先）"""
        try:
            # まずEasyOCRを試行
            try:
                logger.info("Trying EasyOCR for better layout detection...")
                from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
                from docling.document_converter import PdfFormatOption
                from docling.datamodel.base_models import InputFormat

                # EasyOCRオプション（bounding box自動検出）
                use_gpu = GPU_AVAILABLE
                ocr_options = EasyOcrOptions(
                    lang=['ja', 'en'],  # 日本語と英語
                    use_gpu=use_gpu,  # GPU auto-detection
                    force_full_page_ocr=True,  # 非標準フォントエンコーディング対策
                )
                logger.info(f"Docling force OCR with GPU: {use_gpu}, force_full_page_ocr=True")

                force_ocr_pipeline = PdfPipelineOptions(
                    do_ocr=True,
                    ocr_options=ocr_options,
                    do_table_structure=True,  # EasyOCRはテーブル構造も検出可能
                )

                format_options = {InputFormat.PDF: PdfFormatOption(pipeline_options=force_ocr_pipeline)}
                force_ocr_converter = DocumentConverter(format_options=format_options)

                logger.info(f"Attempting Docling conversion with EasyOCR: {pdf_path}")
                conversion_result = force_ocr_converter.convert(pdf_path)

                if conversion_result.status == ConversionStatus.SUCCESS:
                    logger.info("Docling conversion with EasyOCR successful")
                    return True, conversion_result.document
                else:
                    logger.warning(f"EasyOCR conversion failed: {conversion_result.status}")
                    raise Exception("EasyOCR conversion failed")

            except (ImportError, Exception) as e:
                logger.warning(f"EasyOCR not available or failed: {e}")

                # Tesseract OCRへフォールバック
                logger.info("Falling back to Tesseract OCR...")
                from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions
                from docling.document_converter import PdfFormatOption
                from docling.datamodel.base_models import InputFormat

                ocr_options = TesseractCliOcrOptions(
                    lang=['jpn', 'eng'],
                    force_full_page_ocr=True,  # 非標準フォントエンコーディング対策
                )

                force_ocr_pipeline = PdfPipelineOptions(
                    do_ocr=True,
                    ocr_options=ocr_options,
                    do_table_structure=False,  # テーブル構造解析を無効化してOCRに集中
                )

                format_options = {InputFormat.PDF: PdfFormatOption(pipeline_options=force_ocr_pipeline)}
                force_ocr_converter = DocumentConverter(format_options=format_options)

                logger.info(f"Attempting Docling conversion with Tesseract OCR: {pdf_path}")
                conversion_result = force_ocr_converter.convert(pdf_path)

            if conversion_result.status == ConversionStatus.SUCCESS:
                logger.info("Docling conversion with forced OCR successful")
                return True, conversion_result.document
            else:
                logger.warning(f"Docling conversion with forced OCR failed: {conversion_result.status}")
                return False, None
                
        except Exception as e:
            logger.error(f"Docling forced OCR conversion error: {e}")
            return False, None
    
    def _detect_available_japanese_font(self) -> str:
        """利用可能な日本語フォントを検出"""
        # Ghostscriptで利用可能なフォントを確認
        try:
            # gsでフォント一覧を取得
            cmd = ['gs', '-dNODISPLAY', '-q', '-c', '(*) {==} 256 string /Font resourceforall', '-c', 'quit']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                available_fonts = result.stdout.strip().split('\n')
                
                # 優先順位の高い日本語フォントリスト
                preferred_fonts = [
                    'NotoSansCJKjp-Regular',
                    'NotoSerifCJKjp-Regular',
                    'IPAGothic',
                    'IPAMincho',
                    'IPAPGothic',
                    'IPAPMincho',
                    'TakaoGothic',
                    'TakaoMincho',
                    'VL-Gothic-Regular',
                    'VL-PGothic-Regular',
                ]
                
                # 利用可能なフォントから優先フォントを検索
                for font in preferred_fonts:
                    if font in available_fonts:
                        logger.info(f"Found preferred Japanese font: {font}")
                        return font
                
                # 日本語フォントパターンマッチング
                japanese_patterns = ['CJK', 'Japan', 'JP', 'Noto', 'IPA', 'Takao', 'VL']
                for font in available_fonts:
                    for pattern in japanese_patterns:
                        if pattern in font:
                            logger.info(f"Found Japanese font by pattern: {font}")
                            return font
            
        except Exception as e:
            logger.warning(f"Failed to detect available fonts: {e}")
        
        # デフォルトフォント（Ghostscriptの標準CIDフォント）
        # Helveticaではなく、GhostscriptのCIDフォントを使用
        default_font = 'HeiseiKakuGo-W5'  # Ghostscriptの日本語CIDフォント
        logger.warning(f"No Japanese font detected, using default CID font: {default_font}")
        return default_font
    
    @staticmethod
    def check_tools_availability() -> dict:
        """必要なツールの利用可能性をチェック"""
        tools_status = {}
        
        for tool in ['qpdf', 'gs']:
            try:
                result = subprocess.run([tool, '--version'], 
                                      capture_output=True, text=True, timeout=5)
                tools_status[tool] = result.returncode == 0
            except Exception:
                tools_status[tool] = False
        
        return tools_status