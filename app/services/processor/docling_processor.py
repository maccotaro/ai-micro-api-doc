"""
Docling-specific processing utilities.
Handles Docling document conversion, configuration, and specialized processing.
"""

import logging
from pathlib import Path
from typing import Dict, Any
import os
import gc
from datetime import datetime
import json
import time

from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)

# GPU detection
try:
    import torch
    GPU_AVAILABLE = torch.cuda.is_available()
except ImportError:
    GPU_AVAILABLE = False


class DoclingProcessor:
    """Docling document processing and conversion operations"""
    
    def __init__(self, docling_cache_dir: Path = None):
        self.docling_cache_dir = docling_cache_dir or Path("/tmp/.docling_cache")
        self._document_converter = None
        self._setup_docling_environment()
    
    def _setup_docling_environment(self):
        """Setup Docling environment and cache directories"""
        try:
            # 必要なディレクトリがない場合に作成
            models_dir = Path("/usr/local/lib/python3.11/site-packages/deepsearch_glm/resources/models/crf/part-of-speech")
            models_dir.mkdir(parents=True, exist_ok=True)
            
            # 権限設定
            os.chmod(models_dir, 0o755)
            
            # HuggingFace設定（環境変数が未設定の場合のみ設定）
            if "HF_HOME" not in os.environ:
                os.environ["HF_HOME"] = str(self.docling_cache_dir / "huggingface")
            if "TRANSFORMERS_CACHE" not in os.environ:
                os.environ["TRANSFORMERS_CACHE"] = str(self.docling_cache_dir / "transformers")
            if "TORCH_HOME" not in os.environ:
                os.environ["TORCH_HOME"] = str(self.docling_cache_dir / "torch")
            
            # キャッシュディレクトリを作成
            self.docling_cache_dir.mkdir(parents=True, exist_ok=True)
            (self.docling_cache_dir / "huggingface").mkdir(parents=True, exist_ok=True)
            (self.docling_cache_dir / "transformers").mkdir(parents=True, exist_ok=True)
            (self.docling_cache_dir / "torch").mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Docling environment setup completed. Cache dir: {self.docling_cache_dir}")
            
        except Exception as e:
            logger.warning(f"Failed to setup Docling environment: {e}")
    
    def get_document_converter(self) -> DocumentConverter:
        """Get or initialize Docling DocumentConverter with Japanese support"""
        if self._document_converter is None:
            try:
                logger.info("Initializing Docling DocumentConverter with EasyOCR for better layout detection...")

                # Docling 2.65.0 API を使用
                from docling.document_converter import PdfFormatOption
                from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
                from docling.datamodel.base_models import InputFormat

                # EasyOCRオプション設定（レイアウト境界ボックス検出）
                use_gpu = GPU_AVAILABLE
                ocr_options = EasyOcrOptions(
                    lang=['ja', 'en'],  # 日本語と英語を指定（EasyOCRの言語コード）
                    use_gpu=use_gpu,  # GPU auto-detection
                    force_full_page_ocr=True,  # 非標準フォントエンコーディング対策：全ページでOCRを強制実行
                )
                logger.info(f"Docling OCR configured with GPU: {use_gpu}, force_full_page_ocr=True")

                # PDFパイプラインオプション設定
                pdf_pipeline_options = PdfPipelineOptions(
                    do_ocr=True,  # OCRを有効化
                    ocr_options=ocr_options,
                    do_table_structure=True,  # テーブル構造解析を有効
                )

                # フォーマットオプションを設定
                format_options = {
                    InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_pipeline_options)
                }

                # DocumentConverterを初期化
                self._document_converter = DocumentConverter(format_options=format_options)

                logger.info("DocumentConverter initialized with EasyOCR for enhanced layout extraction")
            except ImportError as import_e:
                logger.warning(f"EasyOCR not available: {import_e}")
                # TesseractOCRへフォールバック
                try:
                    logger.info("Falling back to Tesseract OCR...")

                    from docling.document_converter import PdfFormatOption
                    from docling.datamodel.pipeline_options import PdfPipelineOptions, TesseractCliOcrOptions
                    from docling.datamodel.base_models import InputFormat

                    # 日本語OCRオプション設定（TesseractCLI使用）
                    ocr_options = TesseractCliOcrOptions(
                        lang=['jpn', 'eng'],  # 日本語と英語を指定
                        tesseract_cmd='tesseract',  # Tesseractコマンド指定
                        force_full_page_ocr=True,  # 非標準フォントエンコーディング対策：全ページでOCRを強制実行
                    )

                    # PDFパイプラインオプション設定
                    pdf_pipeline_options = PdfPipelineOptions(
                        do_ocr=True,  # OCRを有効化
                        ocr_options=ocr_options,
                        do_table_structure=True,  # テーブル構造解析を有効
                    )

                    # フォーマットオプションを設定
                    format_options = {
                        InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_pipeline_options)
                    }

                    # DocumentConverterを初期化
                    self._document_converter = DocumentConverter(format_options=format_options)

                    logger.info("DocumentConverter initialized with Tesseract OCR")

                except Exception as e:
                    logger.warning(f"Failed to initialize DocumentConverter with OCR settings: {e}")
                    # 最終フォールバック：完全にデフォルト
                    self._document_converter = DocumentConverter()
                    logger.info("DocumentConverter initialized with complete default settings")

        return self._document_converter

    def _log_docling_progress(self, description: str, step: int, total: int, start_time: float = None, progress_callback=None):
        """Docling専用の進捗ログを出力"""
        current_time = time.time()
        elapsed = round(current_time - start_time, 2) if start_time else 0

        # progress_callbackを呼び出し
        if progress_callback:
            progress_callback(step=step, total=total, description=description)

        # 詳細な進捗ログを出力
        progress_log = {
            "timestamp": datetime.now().isoformat(),
            "component": "DoclingProcessor",
            "operation": "docling_conversion",
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
        logger.info(f"🔧 DOCLING_PROGRESS: {json.dumps(progress_log, ensure_ascii=False)}")

    def convert_document(self, document_path: str, progress_callback=None, output_dir: str = None) -> Any:
        """Convert document using Docling with PDF preprocessing fallback"""
        try:
            start_time = time.time()
            logger.info(f"Converting document with Docling: {document_path}")

            # Step 3: Doclingコンバーター初期化
            self._log_docling_progress(
                "Doclingコンバーターを初期化中...",
                step=3, total=10, start_time=start_time, progress_callback=progress_callback
            )

            converter = self.get_document_converter()

            # Step 4: 変換開始
            self._log_docling_progress(
                f"{Path(document_path).name} の変換を開始...",
                step=4, total=10, start_time=start_time, progress_callback=progress_callback
            )

            logger.info(f"Starting Docling conversion for: {Path(document_path).name}")
            
            # PDF前処理フォールバック処理を使用
            from .pdf_preprocessor import PDFPreprocessor
            
            preprocessor = PDFPreprocessor(converter, output_dir)
            
            # ツールの利用可能性をチェック
            tools_status = PDFPreprocessor.check_tools_availability()
            logger.info(f"PDF preprocessing tools status: {tools_status}")
            
            # フォールバック処理を実行
            self._log_docling_progress(
                "PDF前処理フォールバックを実行中...",
                step=4, total=10, start_time=start_time, progress_callback=progress_callback
            )

            success, document, method_used = preprocessor.process_with_fallback(
                document_path, progress_callback
            )

            if success:
                self._log_docling_progress(
                    f"Docling変換が成功しました ({method_used})",
                    step=5, total=10, start_time=start_time, progress_callback=progress_callback
                )
                
                logger.info(f"Conversion successful using {method_used}: {type(document)}")
                logger.info(f"Document has {len(document.pages) if hasattr(document, 'pages') else 0} pages")
                
                # 元のPDFパスを保存（画像生成で使用）
                document._original_pdf_path = document_path
                document._processing_method = method_used
                
                logger.info(f"Docling conversion completed successfully with {method_used}")
                
                # assembled elements の情報をログ出力
                if hasattr(document, 'assembled') and document.assembled:
                    if hasattr(document.assembled, 'elements'):
                        logger.info(f"Assembled elements: {len(document.assembled.elements)}")
                        for i, element in enumerate(document.assembled.elements[:5]):  # 最初の5個を確認
                            logger.info(f"Element {i}: {type(element).__name__}")
                
                return document
            else:
                logger.error("All PDF preprocessing methods failed")
                raise RuntimeError("All PDF preprocessing and Docling conversion methods failed")
            
        except Exception as e:
            logger.error(f"Docling conversion failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def extract_document_metadata(self, document) -> Dict[str, Any]:
        """Extract metadata from Docling document"""
        try:
            # Docling 2.65.0+: DoclingDocument または ExportedCCSDocument を判定
            doc_type_name = type(document).__name__
            is_docling_doc = doc_type_name in ('DoclingDocument', 'ExportedCCSDocument')

            if is_docling_doc:
                # page_dimensionsから実際のページ数を取得
                actual_pages = 1  # デフォルト
                if hasattr(document, 'page_dimensions') and document.page_dimensions:
                    actual_pages = len(document.page_dimensions)
                    logger.info(f"{doc_type_name} has {actual_pages} pages from page_dimensions")
                elif hasattr(document, 'pages') and document.pages:
                    actual_pages = len(document.pages)
                    logger.info(f"{doc_type_name} has {actual_pages} pages from pages attribute")

                metadata = {
                    "total_pages": actual_pages,
                    "processing_mode": "docling",
                    "docling_version": "2.65.0+",
                    "document_type": doc_type_name,
                    "elements_count": 0,
                    "element_types": {}
                }

                # テキストやその他のコンテンツがあるかチェック
                if hasattr(document, 'main_text') and document.main_text:
                    metadata["has_main_text"] = True
                if hasattr(document, 'texts') and list(document.texts):
                    metadata["texts_count"] = len(list(document.texts))
                if hasattr(document, 'body') and document.body.children:
                    metadata["body_children_count"] = len(document.body.children)

                return metadata
            
            # 従来のDocument用のメタデータ抽出
            metadata = {
                "total_pages": len(document.pages) if hasattr(document, 'pages') else 0,
                "processing_mode": "docling",
                "docling_version": "1.7.0+",
                "document_type": "legacy",
                "elements_count": 0,
                "element_types": []
            }
            
            # assembled elements の統計情報
            if hasattr(document, 'assembled') and document.assembled:
                if hasattr(document.assembled, 'elements'):
                    metadata["elements_count"] = len(document.assembled.elements)
                    
                    # 要素タイプの統計
                    element_types = {}
                    for element in document.assembled.elements:
                        element_type = type(element).__name__
                        element_types[element_type] = element_types.get(element_type, 0) + 1
                    
                    metadata["element_types"] = element_types
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Failed to extract document metadata: {e}")
            return {
                "total_pages": 0,
                "processing_mode": "docling",
                "error": str(e)
            }
    
    def extract_raw_pages_data(self, document) -> Dict[str, Any]:
        """Extract raw pages data from Docling document"""
        try:
            # Docling 2.65.0+: DoclingDocument または ExportedCCSDocument を判定
            doc_type_name = type(document).__name__
            is_docling_doc = doc_type_name in ('DoclingDocument', 'ExportedCCSDocument')

            if is_docling_doc:
                raw_pages_data = {
                    "document_type": doc_type_name,
                    "extraction_timestamp": datetime.now().isoformat(),
                    "total_pages": 0,
                    "pages": []
                }

                # page_dimensionsまたはpagesから実際のページ数を取得
                actual_pages = 1  # デフォルト
                if hasattr(document, 'page_dimensions') and document.page_dimensions:
                    actual_pages = len(document.page_dimensions)
                    logger.info(f"Extracting raw pages data from {actual_pages} pages")
                
                raw_pages_data["total_pages"] = actual_pages
                
                # 各ページのデータを初期化
                for page_idx in range(actual_pages):
                    page_data = {
                        "page_number": page_idx + 1,
                        "width": None,
                        "height": None,
                        "elements": []
                    }
                    
                    # ページ寸法を取得
                    if hasattr(document, 'page_dimensions') and document.page_dimensions:
                        if page_idx < len(document.page_dimensions):
                            dimensions = document.page_dimensions[page_idx]
                            if hasattr(dimensions, 'width') and hasattr(dimensions, 'height'):
                                page_data["width"] = dimensions.width
                                page_data["height"] = dimensions.height
                    
                    raw_pages_data["pages"].append(page_data)
                
                # 共通の要素抽出処理
                element_id_counter = 0
                
                def extract_elements_from_collection(collection_name, collection_items, expected_type):
                    """コレクションから要素を抽出する共通処理"""
                    nonlocal element_id_counter
                    
                    if not collection_items:
                        return
                        
                    logger.info(f"Extracting {len(collection_items)} {collection_name} elements")
                    
                    for item in collection_items:
                        # テキストがある要素のみ処理（空のテキストはスキップ）
                        text_content = getattr(item, 'text', '').strip()
                        if not text_content and expected_type != 'table' and expected_type != 'figure':
                            continue  # テーブルと図以外は空のテキストをスキップ
                        
                        # provリストからページ番号とbbox情報を取得
                        if hasattr(item, 'prov') and item.prov:
                            # 最初のprovエントリーのみを使用（重複を防ぐ）
                            prov_item = item.prov[0]
                            page_num = getattr(prov_item, 'page', 1)
                            bbox_list = getattr(prov_item, 'bbox', [])
                            
                            if 1 <= page_num <= actual_pages:
                                page_idx = page_num - 1
                                
                                # obj_typeに基づいて適切なtypeを決定
                                obj_type = getattr(item, 'obj_type', None)
                                element_type = expected_type
                                
                                # obj_typeに基づいてtypeを調整
                                if obj_type:
                                    if 'title' in obj_type.lower() or 'subtitle' in obj_type.lower():
                                        element_type = 'title'
                                    elif obj_type in ['header', 'page-header']:
                                        element_type = 'page_header'
                                    elif obj_type in ['footer', 'page-footer']:
                                        element_type = 'page_footer'
                                
                                element_data = {
                                    "element_id": element_id_counter,
                                    "type": element_type,
                                    "text": text_content if text_content else f"[{element_type.title()}]",
                                    "bbox": {}
                                }
                                
                                # bounding box情報を抽出（[x1, y1, x2, y2]形式）
                                if bbox_list and len(bbox_list) >= 4:
                                    element_data["bbox"] = {
                                        "x1": bbox_list[0],
                                        "y1": bbox_list[1], 
                                        "x2": bbox_list[2],
                                        "y2": bbox_list[3]
                                    }
                                
                                # 追加属性があれば含める
                                if obj_type:
                                    element_data["obj_type"] = obj_type
                                
                                raw_pages_data["pages"][page_idx]["elements"].append(element_data)
                                element_id_counter += 1
                                
                                # テーブル要素の場合、テーブルセルを追加抽出
                                if expected_type == 'table' and hasattr(item, 'data'):
                                    extract_table_cells(item, page_idx, page_num)
                
                def extract_table_cells(table_element, page_idx: int, page_num: int):
                    """テーブル要素からセルを抽出"""
                    nonlocal element_id_counter
                    
                    try:
                        logger.info(f"Attempting to extract table cells from {type(table_element).__name__}")
                        logger.info(f"Table element attributes: {[attr for attr in dir(table_element) if not attr.startswith('_')]}")
                        
                        # テーブルの構造を調べる
                        if hasattr(table_element, 'data'):
                            logger.info(f"Table element has 'data' attribute: {type(table_element.data)}")
                            
                            # table.dataが直接リストの場合（layout_extractorと同じ構造）
                            if isinstance(table_element.data, list):
                                logger.info(f"Table has {len(table_element.data)} rows (direct list)")
                                for row_idx, row in enumerate(table_element.data):
                                    if isinstance(row, list):
                                        logger.info(f"Row {row_idx} has {len(row)} cells")
                                        for col_idx, cell in enumerate(row):
                                            # セルオブジェクトから情報を抽出
                                            cell_text = getattr(cell, 'text', '').strip()
                                            logger.info(f"Cell [{row_idx}][{col_idx}]: '{cell_text}'")
                                            
                                            if cell_text:  # 空でないセルのみ
                                                    
                                                    # セルのbbox情報を取得（もしあれば）
                                                    cell_bbox = {}
                                                    # セルのbbox情報を取得（リスト形式）
                                                    if hasattr(cell, 'bbox') and cell.bbox:
                                                        bbox = cell.bbox
                                                        if isinstance(bbox, list) and len(bbox) >= 4:
                                                            cell_bbox = {
                                                                "x1": float(bbox[0]),
                                                                "y1": float(bbox[1]), 
                                                                "x2": float(bbox[2]),
                                                                "y2": float(bbox[3])
                                                            }
                                                        elif hasattr(bbox, 'l') and hasattr(bbox, 't') and hasattr(bbox, 'r') and hasattr(bbox, 'b'):
                                                            cell_bbox = {
                                                                "x1": float(bbox.l),
                                                                "y1": float(bbox.t), 
                                                                "x2": float(bbox.r),
                                                                "y2": float(bbox.b)
                                                            }
                                                    
                                                    cell_data = {
                                                        "element_id": element_id_counter,
                                                        "type": "table_cell",
                                                        "text": cell_text,
                                                        "bbox": cell_bbox,
                                                        "table_info": {
                                                            "row": row_idx,
                                                            "col": col_idx,
                                                            "cell_type": getattr(cell, 'obj_type', 'body'),
                                                            "is_header": getattr(cell, 'col_header', False) or getattr(cell, 'row_header', False)
                                                        }
                                                    }
                                                    
                                                    raw_pages_data["pages"][page_idx]["elements"].append(cell_data)
                                                    element_id_counter += 1
                                                    logger.info(f"Added table cell: {cell_text}")
                                    else:
                                        logger.info(f"Row {row_idx} is not a list")
                            
                            # table.data.tableの構造もチェック（別のフォーマットの場合）
                            elif hasattr(table_element.data, 'table'):
                                logger.info(f"Table data has 'table' attribute: {type(table_element.data.table)}")
                                # 従来の処理をここに保持（必要に応じて）
                        else:
                            logger.info("Table element has no 'data' attribute")
                            
                    except Exception as e:
                        logger.warning(f"Failed to extract table cells: {e}")
                        import traceback
                        logger.warning(f"Traceback: {traceback.format_exc()}")
                
                # 利用可能なコレクションをログ出力（デバッグ用）
                available_collections = []
                for attr_name in dir(document):
                    if not attr_name.startswith('_'):
                        attr_value = getattr(document, attr_name, None)
                        if hasattr(attr_value, '__len__') and not callable(attr_value):
                            try:
                                if len(attr_value) > 0:
                                    available_collections.append(f"{attr_name}({len(attr_value)})")
                            except:
                                pass
                logger.info(f"Available collections: {available_collections}")
                
                # 各コレクションから要素を抽出
                if hasattr(document, 'main_text'):
                    extract_elements_from_collection('main_text', document.main_text, 'text')
                
                # 各コレクションから要素を抽出（共通処理を使用）
                if hasattr(document, 'tables'):
                    extract_elements_from_collection('tables', document.tables, 'table')
                
                # テーブルセルも抽出（もしあれば）
                if hasattr(document, 'table_cells'):
                    extract_elements_from_collection('table_cells', document.table_cells, 'table_cell')
                
                if hasattr(document, 'figures'):
                    extract_elements_from_collection('figures', document.figures, 'figure')
                
                if hasattr(document, 'page_headers'):
                    extract_elements_from_collection('page_headers', document.page_headers, 'page_header')
                
                if hasattr(document, 'page_footers'):
                    extract_elements_from_collection('page_footers', document.page_footers, 'page_footer')
                
                # titles コレクションも抽出（もしあれば）
                if hasattr(document, 'titles'):
                    extract_elements_from_collection('titles', document.titles, 'title')
                
                # 各ページの要素をY座標で並び替え（上から下へ）
                for page_data in raw_pages_data["pages"]:
                    page_data["elements"].sort(key=lambda x: x["bbox"].get("y1", 0) if x["bbox"] else 0, reverse=True)
                
                # 各ページの要素数を集計
                total_elements = sum(len(page["elements"]) for page in raw_pages_data["pages"])
                logger.info(f"Raw pages data extracted: {actual_pages} pages with {total_elements} total elements")
                
                # 各ページの要素タイプ別の統計をログ出力
                for i, page_data in enumerate(raw_pages_data["pages"], 1):
                    if page_data["elements"]:
                        type_counts = {}
                        for element in page_data["elements"]:
                            element_type = element["type"]
                            type_counts[element_type] = type_counts.get(element_type, 0) + 1
                        logger.info(f"Page {i}: {len(page_data['elements'])} elements - {type_counts}")
                
                return raw_pages_data
            
            else:
                logger.warning(f"Unsupported document type for raw pages extraction: {type(document)}")
                return {
                    "document_type": str(type(document)),
                    "extraction_timestamp": datetime.now().isoformat(),
                    "total_pages": 0,
                    "pages": [],
                    "error": "Unsupported document type"
                }
                
        except Exception as e:
            logger.error(f"Failed to extract raw pages data: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return {
                "extraction_timestamp": datetime.now().isoformat(),
                "total_pages": 0,
                "pages": [],
                "error": str(e)
            }
    
    def cleanup(self):
        """Cleanup Docling resources"""
        try:
            if self._document_converter:
                # DocumentConverterには明示的なcleanupメソッドがないため、
                # オブジェクトを削除してガベージコレクションに任せる
                self._document_converter = None
                gc.collect()
                logger.info("Docling DocumentConverter cleanup completed")
        except Exception as e:
            logger.warning(f"Failed to cleanup Docling resources: {e}")
    
    def validate_document(self, document) -> bool:
        """Validate Docling document structure (ExportedCCSDocument)"""
        try:
            # 基本的な検証
            if not document:
                logger.warning("Document is None")
                return False
            
            # Docling 2.65.0+: DoclingDocument または ExportedCCSDocument の検証
            try:
                from docling_core.types.doc.document import DoclingDocument
                if isinstance(document, DoclingDocument):
                    # DoclingDocumentは常に有効とみなす
                    logger.info(f"DoclingDocument validation passed: {type(document)}")
                    return True
            except ImportError:
                pass

            try:
                from docling_core.types.doc.document import ExportedCCSDocument
                if isinstance(document, ExportedCCSDocument):
                    # ExportedCCSDocumentは常に有効とみなす（構造が異なるため）
                    logger.info(f"ExportedCCSDocument validation passed: {type(document)}")
                    return True
            except ImportError:
                pass

            # 型名での判定（インポートが失敗した場合のフォールバック）
            doc_type_name = type(document).__name__
            if doc_type_name in ('DoclingDocument', 'ExportedCCSDocument'):
                logger.info(f"{doc_type_name} validation passed (by name)")
                return True
            
            # 従来のDocument用の検証（互換性のため残す）
            if not hasattr(document, 'pages'):
                logger.warning("Document has no pages attribute")
                return False
            
            if len(document.pages) == 0:
                logger.warning("Document has no pages")
                return False
            
            # assembled elements の検証
            if hasattr(document, 'assembled') and document.assembled:
                if hasattr(document.assembled, 'elements'):
                    if len(document.assembled.elements) == 0:
                        logger.warning("Document has no assembled elements")
                    else:
                        logger.info(f"Document validation passed: {len(document.pages)} pages, {len(document.assembled.elements)} elements")
                        return True
            
            logger.warning("Document has no assembled elements")
            return True  # ページがあれば有効とみなす
            
        except Exception as e:
            logger.error(f"Document validation failed: {e}")
            return False