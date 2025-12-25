"""
Base document processor class.
Main orchestrator for document processing operations using modular components.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, List, Any
import logging
from datetime import datetime
import gc
import psutil
import os
import asyncio
import time

from .file_manager import FileManager
from .image_processor import ImageProcessor
from .layout_extractor import LayoutExtractor
from .text_extractor import TextExtractor
from .docling_processor import DoclingProcessor
from .image_cropper import ImageCropper

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Main document processor class that orchestrates all processing operations"""
    
    def __init__(self, use_layout_extractor: bool = True):
        """Initialize DocumentProcessor.
        
        Args:
            use_layout_extractor: Whether to use layout extraction (default: True)
        """
        self.output_base_dir = Path("/tmp/document_processing")
        self.output_base_dir.mkdir(exist_ok=True)
        
        # Cache directories
        self.easyocr_cache_dir = Path(os.environ.get("EASYOCR_MODULE_PATH", "/tmp/.easyocr_models"))
        self.docling_cache_dir = Path(os.environ.get("DOCLING_CACHE_DIR", "/tmp/.docling_cache"))
        self.easyocr_cache_dir.mkdir(exist_ok=True)
        self.docling_cache_dir.mkdir(exist_ok=True)
        
        # Layout extractor flag
        self.use_layout_extractor = use_layout_extractor
        
        # Initialize modular components
        self.file_manager = FileManager(self.output_base_dir)
        self.image_processor = ImageProcessor()
        if self.use_layout_extractor:
            self.layout_extractor = LayoutExtractor()
        else:
            self.layout_extractor = None
            logger.info("Layout Extractor is disabled")
        self.text_extractor = TextExtractor(self.easyocr_cache_dir)
        self.docling_processor = DoclingProcessor(self.docling_cache_dir)
        self.image_cropper = ImageCropper()
        
        logger.info(f"DocumentProcessor initialized with modular components (layout_extractor={use_layout_extractor})")

    def _log_progress_with_timing(self, description: str, step: int, total: int, start_time: float = None, progress_callback=None):
        """進捗ログをタイミング情報付きで出力"""
        current_time = time.time()
        elapsed = round(current_time - start_time, 2) if start_time else 0

        # progress_callbackを呼び出し
        if progress_callback:
            progress_callback(step=step, total=total, description=description)

        # 詳細な進捗ログを出力
        progress_log = {
            "timestamp": datetime.now().isoformat(),
            "component": "DocumentProcessor",
            "operation": "processing_step",
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
        logger.info(f"📈 DOCUMENT_PROGRESS: {json.dumps(progress_log, ensure_ascii=False)}")

    def _check_memory_usage(self) -> None:
        """メモリ使用量を監視し、必要に応じてガベージコレクションを実行"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            logger.info(f"Current memory usage: {memory_mb:.1f}MB")
            
            # 4GB以上使用している場合はガベージコレクションを強制実行（12GB制限に調整）
            if memory_mb > 4000:
                logger.warning(f"High memory usage detected: {memory_mb:.1f}MB, forcing garbage collection")
                gc.collect()
                # GC後のメモリ使用量を再確認
                new_memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
                logger.info(f"Memory usage after GC: {new_memory_mb:.1f}MB (freed: {memory_mb - new_memory_mb:.1f}MB)")
                
                # 10GB以上の場合は警告（12GB制限の83%）
                if new_memory_mb > 10000:
                    logger.error(f"Critical memory usage: {new_memory_mb:.1f}MB - approaching 12GB container limit")
                    raise MemoryError(f"Memory usage too high: {new_memory_mb:.1f}MB")
        except Exception as e:
            logger.warning(f"Failed to check memory usage: {e}")
    
    async def process_document_async(self, file_path: str, original_filename: str) -> Dict[str, Any]:
        """Process document asynchronously."""
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                self.process_document,
                file_path,
                original_filename
            )
            return result
        except Exception as e:
            logger.error(f"Async document processing failed: {e}")
            raise
    
    def process_document_with_progress(self, document_path: str, original_filename: str = None, progress_callback=None) -> Dict[str, Any]:
        """メイン文書処理関数（進捗報告付き）"""
        start_time = time.time()
        self._log_progress_with_timing("初期化中...", 0, 10, start_time, progress_callback)

        start_datetime = datetime.now()
        timestamp = start_datetime.strftime("%Y%m%d_%H%M%S")
        
        try:
            self._check_memory_usage()
            
            doc_path = Path(document_path)
            if not doc_path.exists():
                raise FileNotFoundError(f"Document not found: {document_path}")
            
            if original_filename is None:
                original_filename = doc_path.name
            
            logger.info(f"Starting document processing: {original_filename}")

            self._log_progress_with_timing("ファイル検証完了", 1, 10, start_time, progress_callback)
            
            # 出力ディレクトリ作成
            output_dir = self.file_manager.create_output_directory(timestamp, original_filename)
            
            # 元ファイルを保存
            self.file_manager.save_original_file(document_path, output_dir, original_filename)

            self._log_progress_with_timing("出力ディレクトリ作成完了", 2, 10, start_time, progress_callback)
            
            # Docling処理を試行
            try:
                logger.info("Attempting Docling processing...")
                self._log_progress_with_timing("Docling変換開始... (数分かかる場合があります)", 3, 10, start_time, progress_callback)

                # Docling初期化の進捗を報告
                self._log_progress_with_timing("Doclingモデルを初期化中...", 3, 10, start_time, progress_callback)

                document = self.docling_processor.convert_document(document_path, progress_callback, str(self.output_base_dir))

                self._log_progress_with_timing("Docling変換完了、結果を検証中...", 5, 10, start_time, progress_callback)

                if not self.docling_processor.validate_document(document):
                    raise ValueError("Invalid document structure")

                self._log_progress_with_timing("ドキュメント構造検証完了", 6, 10, start_time, progress_callback)
                
                return self._process_with_docling_progress(document, output_dir, timestamp, original_filename, progress_callback)
                
            except Exception as e:
                logger.warning(f"Docling processing failed: {e}")
                logger.info("Falling back to basic processing...")
                self._log_progress_with_timing("Docling処理に失敗、基本処理に切り替え中...", 8, 10, start_time, progress_callback)
                return self.file_manager.create_fallback_output(doc_path, output_dir, timestamp, original_filename)
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            self._log_progress_with_timing(f"エラー: {str(e)}", 10, 10, start_time, progress_callback)
            raise
        
        finally:
            self._check_memory_usage()
            # Cleanup
            self.docling_processor.cleanup()

    def process_document(self, document_path: str, original_filename: str = None) -> Dict[str, Any]:
        """メイン文書処理関数（Docling + othersystem準拠）"""
        return self.process_document_with_progress(document_path, original_filename, None)

    def _process_with_docling_progress(self, document, output_dir: Path, timestamp: str, original_filename: str, progress_callback=None) -> Dict[str, Any]:
        """Doclingを使用した文書処理（進捗報告付き）"""
        logger.info("Processing document with Docling")
        process_start_time = time.time()

        self._log_progress_with_timing("ドキュメントメタデータ解析中...", 6, 10, process_start_time, progress_callback)
        
        # 基本メタデータを取得
        doc_metadata = self.docling_processor.extract_document_metadata(document)
        num_pages = doc_metadata.get("total_pages", 0)
        
        # PDF次元情報を早期取得（ページ処理で座標変換に使用）
        early_page_dimensions = None
        early_image_dimensions = None
        
        if hasattr(document, 'page_dimensions') and document.page_dimensions:
            try:
                # 最初のページのサイズを取得
                first_page_dim = document.page_dimensions[0]
                early_page_dimensions = {
                    "width": first_page_dim.width,
                    "height": first_page_dim.height
                }
                logger.info(f"Early PDF page dimensions: {first_page_dim.width}x{first_page_dim.height}")
            except Exception as e:
                logger.warning(f"Failed to get early PDF dimensions: {e}")
        
        # DISABLED: raw_pages.json generation - not used by any endpoint, saves storage space
        # # Docling生ページデータを抽出してraw_pages.jsonとして保存
        # try:
        #     raw_pages_data = self.docling_processor.extract_raw_pages_data(document)
        #     raw_pages_file = output_dir / "raw_pages.json"
        #     with open(raw_pages_file, 'w', encoding='utf-8') as f:
        #         import json
        #         json.dump(raw_pages_data, f, ensure_ascii=False, indent=2)
        #     logger.info(f"Raw pages data saved: {raw_pages_file}")
        # except Exception as e:
        #     logger.warning(f"Failed to save raw pages data: {e}")
        
        if num_pages == 0:
            logger.warning("No pages found in document")
            self._log_progress_with_timing("ページが見つかりません、フォールバック処理中...", 10, 10, process_start_time, progress_callback)
            return self.file_manager.create_fallback_output(
                Path(document._original_pdf_path), output_dir, timestamp, original_filename
            )

        self._log_progress_with_timing(f"{num_pages}ページの処理を開始...", 7, 10, process_start_time, progress_callback)
        
        # ステップ1: Doclingオブジェクトから統合構造を分析
        unified_structure = None
        try:
            from .document_structure_analyzer import DocumentStructureAnalyzer
            structure_analyzer = DocumentStructureAnalyzer()
            unified_structure = structure_analyzer.create_unified_structure_from_docling(
                document, num_pages
            )
            logger.info(f"Unified structure created with {len(unified_structure.get('sections', []))} sections")
        except Exception as e:
            logger.warning(f"Failed to create unified structure: {e}")
            unified_structure = None
        
        pages_data = []
        total_elements = 0
        
        # 文書全体で共有するHierarchyConverterインスタンスを作成
        from .hierarchical_extractor import HierarchicalExtractor
        from .hierarchy_converter import HierarchyConverter
        document_hierarchy_converter = HierarchyConverter()  # 文書全体で通し番号を管理
        
        # ステップ2: 各ページを処理（統合構造を参照しながら）
        for page_num in range(num_pages):
            try:
                page_progress = 7 + (page_num / num_pages) * 2  # 7から9の間で進捗
                if progress_callback:
                    progress_callback(
                        step=int(page_progress), 
                        total=10, 
                        description=f"ページ {page_num + 1}/{num_pages} を処理中..."
                    )
                
                logger.info(f"Processing page {page_num + 1}/{num_pages}")
                
                # ステップ1: レイアウト抽出 (docling処理)
                if self.use_layout_extractor and self.layout_extractor:
                    page_layout = self.layout_extractor.extract_page_layout(document, page_num, output_dir)
                else:
                    # Layout Extractorが無効の場合は空のレイアウトを返す
                    page_layout = {
                        "page_number": page_num + 1,
                        "elements": [],
                        "raw_docling_elements": []  # Doclingの生データを保持
                    }
                    logger.info(f"Layout extraction skipped for page {page_num + 1}")
                
                # 統合構造から該当ページのセクション情報を追加
                if unified_structure and "sections" in unified_structure:
                    page_sections = [
                        section["section_id"] 
                        for section in unified_structure["sections"]
                        if section["start_page"] <= page_num + 1 <= section["end_page"]
                    ]
                    page_layout["sections"] = page_sections
                    page_layout["document_structure_ref"] = "metadata_ext.json#/unified_document_structure"
                
                # ステップ2: 階層構造変換 (hierarchy処理)
                # ページレベルで階層構造を生成し、hierarchical_elementsを作成
                try:
                    # まず拡張メタデータを部分的に作成（このページのみ）
                    hierarchical_extractor = HierarchicalExtractor()
                    temp_metadata = {
                        "document_name": original_filename,
                        "processing_timestamp": timestamp,
                        "total_pages": num_pages,
                        "pages": [{"page_number": page_num + 1}]  # 一時的な単一ページメタデータ
                    }
                    
                    # dimensions情報を追加（座標変換で使用）
                    if early_page_dimensions:
                        temp_metadata["dimensions"] = {
                            "pdf_page": early_page_dimensions,
                            "image_page": early_image_dimensions
                        }
                    
                    # DISABLED: metadata_ext.json generation - not used by frontend, all data in metadata_hierarchy.json
                    # # ページ拡張メタデータを作成
                    # page_metadata_ext = hierarchical_extractor.create_extended_metadata(
                    #     document, output_dir, temp_metadata, original_filename, single_page=page_num
                    # )
                    page_metadata_ext = temp_metadata  # temp_metadataにはdimensions情報が含まれている
                    
                    # 文書全体で共有するHierarchyConverterでページレベル変換を実行
                    page_layout = document_hierarchy_converter.convert_page_to_hierarchy(
                        page_layout, page_num + 1, page_metadata_ext, document
                    )
                    
                    logger.info(f"✅ Page {page_num + 1}: Created hierarchical_elements ({len(page_layout.get('hierarchical_elements', []))} elements)")
                    
                except Exception as e:
                    logger.warning(f"Failed to create hierarchical structure for page {page_num + 1}: {e}")
                    # エラー時はもとのpage_layoutをそのまま使用
                
                # DISABLED: Individual layout file creation - data included in metadata_hierarchy.json
                # layout_file = self.file_manager.create_layout_file(output_dir, page_num + 1, page_layout)
                layout_file = f"layout/page_{page_num + 1}_layout.json"  # Path reference only
                
                # ページ画像作成
                images_dir = output_dir / "images"
                page_images = self.image_processor.create_page_image(page_num, images_dir, document)
                
                # ステップ3: 画像切り出し (crop処理)
                # hierarchical_elementsが存在する場合はそれを使用、なければelementsを使用
                cropped_elements = []
                has_hierarchical = page_layout.get("hierarchical_elements") is not None
                elements_source = page_layout.get("hierarchical_elements") if has_hierarchical else page_layout.get("elements", [])
                logger.info(f"📋 Page {page_num + 1}: Using {'hierarchical_elements' if has_hierarchical else 'elements'} ({len(elements_source)} elements)")
                
                if elements_source:
                    page_image_path = images_dir / f"page_{page_num + 1}_full.png"
                    if page_image_path.exists():
                        # 画像要素（figure, picture, table, caption）を抽出してIDを確認
                        croppable_elements = [elem for elem in elements_source if elem.get("type") in ["figure", "picture", "image", "table", "caption"]]
                        
                        # IDがない要素にIDを生成
                        for elem in croppable_elements:
                            if not elem.get("id"):
                                elem["id"] = f"auto-{page_num + 1}-{elem.get('type', 'unknown')}-{id(elem)}"
                                logger.info(f"🆔 Generated ID for element: {elem['id']}")
                        
                        logger.info(f"🖼️ Found {len(croppable_elements)} croppable elements on page {page_num + 1}")
                        
                        # 新しいcrop_single_element方式で各要素を処理
                        if croppable_elements:
                            try:
                                cropped_count = 0
                                for elem in croppable_elements:
                                    if self.image_cropper.crop_single_element(
                                        str(page_image_path), elem, str(images_dir), scale_factor=2.0
                                    ):
                                        cropped_elements.append(elem)
                                        cropped_count += 1
                                        logger.info(f"✅ Successfully cropped element {elem.get('id')} ({elem.get('type')})")
                                    else:
                                        logger.warning(f"❌ Failed to crop element {elem.get('id')} ({elem.get('type')})")
                                
                                logger.info(f"📊 Successfully cropped {cropped_count}/{len(croppable_elements)} elements on page {page_num + 1}")
                                
                            except Exception as e:
                                logger.warning(f"Failed to crop elements on page {page_num + 1}: {e}")
                
                # 注釈付き画像作成（レイアウト要素がある場合）
                if page_layout.get("hierarchical_elements"):
                    page_image_path = images_dir / f"page_{page_num + 1}_full.png"
                    annotated_image_path = images_dir / f"page_{page_num + 1}_full_annotated.png"
                    
                    if page_image_path.exists():
                        self.image_processor.create_annotated_image(
                            page_image_path, page_layout, annotated_image_path, scale_factor=2.0
                        )
                
                # DISABLED: Individual text file creation - data included in metadata_hierarchy.json
                page_text = self._extract_page_text(document, page_num, page_layout)
                # text_file = self.file_manager.create_text_file(output_dir, page_num + 1, page_text)
                text_file = f"text/page_{page_num + 1}.txt"  # Path reference only
                
                # ページデータ作成
                page_data = {
                    "page_number": page_num + 1,
                    "layout_file": layout_file,  # Direct string path
                    "image_files": [img["file"] for img in page_images] if page_images else [],
                    "text_file": text_file,  # Direct string path
                    "text_content": page_text[:500] + "..." if len(page_text) > 500 else page_text,
                    "hierarchical_elements": page_layout.get("hierarchical_elements", []),
                    "has_hierarchy": True,
                    "cropped_elements_count": len(cropped_elements),
                    "cropped_figure_count": len([elem for elem in cropped_elements if elem.get("type") in ["figure", "picture", "image"]]),
                    "cropped_table_count": len([elem for elem in cropped_elements if elem.get("type") == "table"])
                }
                
                pages_data.append(page_data)
                total_elements += len(page_layout.get("hierarchical_elements", []))
                
            except Exception as e:
                logger.error(f"Failed to process page {page_num + 1}: {e}")
                # エラーページのフォールバック
                pages_data.append({
                    "page_number": page_num + 1,
                    "layout_file": None,
                    "image_files": [],
                    "text_file": None,
                    "text_content": f"Error processing page {page_num + 1}",
                    "hierarchical_elements": [],
                    "has_hierarchy": False
                })
        
        self._log_progress_with_timing("メタデータファイル作成中...", 9, 10, process_start_time, progress_callback)
        
        # 画像サイズとPDFサイズ情報を取得
        page_dimensions = None
        image_dimensions = None
        
        # 最初のページの画像サイズを取得
        if pages_data:
            first_page_image = images_dir / f"page_1_full.png"
            if first_page_image.exists():
                try:
                    from PIL import Image
                    with Image.open(first_page_image) as img:
                        image_dimensions = {
                            "width": img.width,
                            "height": img.height
                        }
                        logger.info(f"First page image dimensions: {img.width}x{img.height}")
                except Exception as e:
                    logger.warning(f"Failed to get image dimensions: {e}")
        
        # PDFページサイズを取得（Doclingから）
        if hasattr(document, 'page_dimensions') and document.page_dimensions:
            try:
                # 最初のページのサイズを取得
                first_page_dim = document.page_dimensions[0]
                page_dimensions = {
                    "width": first_page_dim.width,
                    "height": first_page_dim.height
                }
                logger.info(f"PDF page dimensions: {first_page_dim.width}x{first_page_dim.height}")
            except Exception as e:
                logger.warning(f"Failed to get PDF dimensions: {e}")
        
        # 総合メタデータ作成
        metadata = {
            "document_name": original_filename,
            "processing_timestamp": timestamp,
            "total_pages": num_pages,
            "total_elements": total_elements,
            "pages": pages_data,
            "processing_mode": "docling",
            "docling_metadata": doc_metadata,
            "text_extraction": {
                "method": "docling",
                "ocr_enabled": False
            },
            "dimensions": {
                "pdf_page": page_dimensions,
                "image_page": image_dimensions
            }
        }
        
        # メタデータファイル作成（削除予定：metadata_hierarchy.jsonに統合）
        # metadata_file = self.file_manager.create_metadata_file(output_dir, metadata)
        
        # 統合文書構造分析と拡張メタデータファイル作成
        try:
            from .hierarchical_extractor import HierarchicalExtractor
            
            # 拡張メタデータを作成（既存の階層構造付き）
            hierarchical_extractor = HierarchicalExtractor()
            extended_metadata = hierarchical_extractor.create_extended_metadata(
                document, output_dir, metadata, original_filename
            )
            
            # フロントエンド用階層構造メタデータを作成
            try:
                from .hierarchy_converter import HierarchyConverter
                
                hierarchy_converter = HierarchyConverter()
                
                # 処理済みのpages_dataからhierarchical_elementsを取得してhierarchy_metadataを構築
                hierarchy_metadata = metadata.copy()
                
                # pages_dataから処理済みのhierarchical_elementsを使用
                for page_idx, page_data in enumerate(pages_data):
                    if page_idx < len(hierarchy_metadata.get("pages", [])):
                        # 処理済みのhierarchical_elementsを使用
                        processed_hierarchical_elements = page_data.get("hierarchical_elements", [])
                        hierarchy_metadata["pages"][page_idx]["hierarchical_elements"] = processed_hierarchical_elements
                        hierarchy_metadata["pages"][page_idx]["has_hierarchy"] = True
                        
                        # cropped_image_pathが設定されている要素数をカウント
                        cropped_count = len([elem for elem in processed_hierarchical_elements 
                                           if elem.get("cropped_image_path") is not None])
                        
                        logger.info(f"📋 Updated page {page_idx + 1}: {len(processed_hierarchical_elements)} elements, "
                                  f"{cropped_count} with cropped images")
                
                logger.info("✅ Successfully transferred processed hierarchical_elements with cropped_image_path data")
                
                logger.info("✅ Using processed hierarchical_elements with cropped_image_path data")
                
                # document_structure_summary を階層メタデータに追加
                if unified_structure:
                    hierarchy_metadata["document_structure_summary"] = {
                        "total_sections": len(unified_structure.get("sections", [])),
                        "document_type": unified_structure.get("document_overview", {}).get("document_type", "unknown"),
                        "structure_confidence": unified_structure.get("document_overview", {}).get("structure_confidence", 0.0),
                        "has_unified_structure": True
                    }
                else:
                    # フォールバック構造情報
                    hierarchy_metadata["document_structure_summary"] = {
                        "total_sections": 1,
                        "document_type": "general_document", 
                        "structure_confidence": 0.0,
                        "has_unified_structure": True
                    }
                
                # metadata_hierarchy.json を保存
                hierarchy_file = hierarchy_converter.save_hierarchy_metadata(
                    hierarchy_metadata, output_dir
                )
                logger.info(f"Created frontend hierarchy metadata: {hierarchy_file}")
                
                # DB保存用に階層メタデータを保持
                self.processed_hierarchy_metadata = hierarchy_metadata
                
            except Exception as hierarchy_e:
                logger.warning(f"Failed to create hierarchy metadata: {hierarchy_e}")
                # エラーでも処理は続行
            
            # DISABLED: Extended metadata and document structure generation - not used by frontend
            # # 統合文書構造を拡張メタデータに追加（すでに作成済み）
            # if unified_structure:
            #     extended_metadata["unified_document_structure"] = unified_structure
            # else:
            #     # フォールバック：レイアウトファイルから作成
            #     from .document_structure_analyzer import DocumentStructureAnalyzer
            #     all_page_layouts = []
            #     for page_data in pages_data:
            #         layout_file_path = output_dir / page_data.get("layout_file", "")
            #         if layout_file_path.exists():
            #             try:
            #                 with open(layout_file_path, 'r', encoding='utf-8') as f:
            #                     import json
            #                     layout_data = json.load(f)
            #                     all_page_layouts.append(layout_data)
            #             except Exception as e:
            #                 logger.warning(f"Failed to load layout file {layout_file_path}: {e}")
            #     
            #     structure_analyzer = DocumentStructureAnalyzer()
            #     unified_structure = structure_analyzer.create_unified_document_structure(
            #         document, all_page_layouts, metadata
            #     )
            #     extended_metadata["unified_document_structure"] = unified_structure
            # 
            # # metadata_ext.jsonとして保存
            # metadata_ext_file = output_dir / "metadata_ext.json"
            # with open(metadata_ext_file, 'w', encoding='utf-8') as f:
            #     import json
            #     json.dump(extended_metadata, f, ensure_ascii=False, indent=2)
            # 
            # logger.info(f"Extended metadata with unified structure created: {metadata_ext_file}")
            
            # DISABLED: Structure visualization files generation - not used by frontend, saves storage space
            # # 構造視覚化ファイルを生成
            # try:
            #     from .structure_visualizer import DocumentStructureVisualizer
            #     visualizer = DocumentStructureVisualizer(metadata_ext_file)
            #     
            #     # 階層ツリーテキストファイル生成
            #     visualizer.generate_hierarchy_tree(output_dir)
            #     logger.info("Generated hierarchy tree text file")
            #     
            #     # インタラクティブHTMLビューアー生成
            #     visualizer.generate_html_viewer(output_dir)
            #     logger.info("Generated interactive HTML viewer")
            #     
            #     # Mermaidダイアグラム生成
            #     visualizer.generate_mermaid_diagram(output_dir)
            #     logger.info("Generated Mermaid diagram")
            #     
            # except Exception as e:
            #     logger.warning(f"Could not generate structure visualization: {e}")
            
            # 重複削除：document_structure_summaryは既にhierarchy_metadataに追加済み
            # metadata.jsonの重複作成を削除（metadata_hierarchy.jsonに統合）
            
        except Exception as e:
            logger.warning(f"Failed to create unified document structure: {e}")
            # 統合構造の作成に失敗しても処理は続行
            try:
                # フォールバック：既存の拡張メタデータのみ作成
                from .hierarchical_extractor import HierarchicalExtractor
                hierarchical_extractor = HierarchicalExtractor()
                
                extended_metadata = hierarchical_extractor.create_extended_metadata(
                    document, output_dir, metadata, original_filename
                )
                
                metadata_ext_file = output_dir / "metadata_ext.json"
                with open(metadata_ext_file, 'w', encoding='utf-8') as f:
                    import json
                    json.dump(extended_metadata, f, ensure_ascii=False, indent=2)
                
                logger.info(f"Fallback extended metadata created: {metadata_ext_file}")
                
            except Exception as fallback_e:
                logger.warning(f"Failed to create fallback extended metadata: {fallback_e}")
        
        # 処理時間計算
        processing_time = (datetime.now() - datetime.fromisoformat(timestamp.replace('_', '')[:8] + 'T' + timestamp.replace('_', '')[8:10] + ':' + timestamp.replace('_', '')[10:12] + ':' + timestamp.replace('_', '')[12:14])).total_seconds()
        
        self._log_progress_with_timing("処理完了!", 10, 10, process_start_time, progress_callback)
        
        logger.info(f"Docling processing completed: {total_elements} elements extracted in {processing_time:.1f}s")
        
        return {
            "status": "success",
            "output_directory": str(output_dir.relative_to(self.output_base_dir.parent)),
            "files_created": {
                "original": str((output_dir / "original" / original_filename).relative_to(self.output_base_dir.parent)),
                "metadata_hierarchy": str((output_dir / "metadata_hierarchy.json").relative_to(self.output_base_dir.parent)),
                "layout_dir": str((output_dir / "layout").relative_to(self.output_base_dir.parent)),
                "images_dir": str((output_dir / "images").relative_to(self.output_base_dir.parent)),
                "text_dir": str((output_dir / "text").relative_to(self.output_base_dir.parent))
            },
            "total_pages": num_pages,
            "total_elements": total_elements,
            "processing_mode": "docling",
            "processing_time": f"{processing_time:.1f}s",
            "original_filename": original_filename,
            "metadata": getattr(self, 'processed_hierarchy_metadata', None)  # DB保存用メタデータ
        }
    
    def _process_with_docling(self, document, output_dir: Path, timestamp: str, original_filename: str) -> Dict[str, Any]:
        """Doclingを使用した文書処理"""
        logger.info("Processing document with Docling")
        
        # 基本メタデータを取得
        doc_metadata = self.docling_processor.extract_document_metadata(document)
        num_pages = doc_metadata.get("total_pages", 0)
        
        if num_pages == 0:
            logger.warning("No pages found in document")
            return self.file_manager.create_fallback_output(
                Path(document._original_pdf_path), output_dir, timestamp, original_filename
            )
        
        # ステップ1: Doclingオブジェクトから統合構造を分析
        unified_structure = None
        try:
            from .document_structure_analyzer import DocumentStructureAnalyzer
            structure_analyzer = DocumentStructureAnalyzer()
            unified_structure = structure_analyzer.create_unified_structure_from_docling(
                document, num_pages
            )
            logger.info(f"Unified structure created with {len(unified_structure.get('sections', []))} sections")
        except Exception as e:
            logger.warning(f"Failed to create unified structure: {e}")
            unified_structure = None
        
        pages_data = []
        total_elements = 0
        
        # 各ページを処理
        for page_num in range(num_pages):
            try:
                logger.info(f"Processing page {page_num + 1}/{num_pages}")
                
                # レイアウト抽出
                if self.use_layout_extractor and self.layout_extractor:
                    page_layout = self.layout_extractor.extract_page_layout(document, page_num, output_dir)
                else:
                    # Layout Extractorが無効の場合は空のレイアウトを返す
                    page_layout = {
                        "page_number": page_num + 1,
                        "elements": [],
                        "raw_docling_elements": []  # Doclingの生データを保持
                    }
                    logger.info(f"Layout extraction skipped for page {page_num + 1}")
                
                # 統合構造から該当ページのセクション情報を追加
                if unified_structure and "sections" in unified_structure:
                    page_sections = [
                        section["section_id"] 
                        for section in unified_structure["sections"]
                        if section["start_page"] <= page_num + 1 <= section["end_page"]
                    ]
                    page_layout["sections"] = page_sections
                    page_layout["document_structure_ref"] = "metadata_ext.json#/unified_document_structure"
                
                # DISABLED: Individual layout file creation - data included in metadata_hierarchy.json
                # layout_file = self.file_manager.create_layout_file(output_dir, page_num + 1, page_layout)
                layout_file = f"layout/page_{page_num + 1}_layout.json"  # Path reference only
                
                # ページ画像作成
                images_dir = output_dir / "images"
                page_images = self.image_processor.create_page_image(page_num, images_dir, document)
                
                # ステップ3: 画像切り出し (crop処理)
                # hierarchical_elementsが存在する場合はそれを使用、なければelementsを使用
                cropped_elements = []
                has_hierarchical = page_layout.get("hierarchical_elements") is not None
                elements_source = page_layout.get("hierarchical_elements") if has_hierarchical else page_layout.get("elements", [])
                logger.info(f"📋 Page {page_num + 1}: Using {'hierarchical_elements' if has_hierarchical else 'elements'} ({len(elements_source)} elements)")
                
                if elements_source:
                    page_image_path = images_dir / f"page_{page_num + 1}_full.png"
                    if page_image_path.exists():
                        # 画像要素（figure, picture, table, caption）を抽出してIDを確認
                        croppable_elements = [elem for elem in elements_source if elem.get("type") in ["figure", "picture", "image", "table", "caption"]]
                        
                        # IDがない要素にIDを生成
                        for elem in croppable_elements:
                            if not elem.get("id"):
                                elem["id"] = f"auto-{page_num + 1}-{elem.get('type', 'unknown')}-{id(elem)}"
                                logger.info(f"🆔 Generated ID for element: {elem['id']}")
                        
                        logger.info(f"🖼️ Found {len(croppable_elements)} croppable elements on page {page_num + 1}")
                        
                        # 新しいcrop_single_element方式で各要素を処理
                        if croppable_elements:
                            try:
                                cropped_count = 0
                                for elem in croppable_elements:
                                    if self.image_cropper.crop_single_element(
                                        str(page_image_path), elem, str(images_dir), scale_factor=2.0
                                    ):
                                        cropped_elements.append(elem)
                                        cropped_count += 1
                                        logger.info(f"✅ Successfully cropped element {elem.get('id')} ({elem.get('type')})")
                                    else:
                                        logger.warning(f"❌ Failed to crop element {elem.get('id')} ({elem.get('type')})")
                                
                                logger.info(f"📊 Successfully cropped {cropped_count}/{len(croppable_elements)} elements on page {page_num + 1}")
                                
                            except Exception as e:
                                logger.warning(f"Failed to crop elements on page {page_num + 1}: {e}")
                
                # 注釈付き画像作成（レイアウト要素がある場合）
                if page_layout.get("hierarchical_elements"):
                    page_image_path = images_dir / f"page_{page_num + 1}_full.png"
                    annotated_image_path = images_dir / f"page_{page_num + 1}_full_annotated.png"
                    
                    if page_image_path.exists():
                        self.image_processor.create_annotated_image(
                            page_image_path, page_layout, annotated_image_path, scale_factor=2.0
                        )
                
                # DISABLED: Individual text file creation - data included in metadata_hierarchy.json
                page_text = self._extract_page_text(document, page_num, page_layout)
                # text_file = self.file_manager.create_text_file(output_dir, page_num + 1, page_text)
                text_file = f"text/page_{page_num + 1}.txt"  # Path reference only
                
                # ページデータ作成
                page_data = {
                    "page_number": page_num + 1,
                    "layout_file": layout_file,  # Direct string path
                    "image_files": [img["file"] for img in page_images] if page_images else [],
                    "text_file": text_file,  # Direct string path
                    "text_content": page_text[:500] + "..." if len(page_text) > 500 else page_text,
                    "hierarchical_elements": page_layout.get("hierarchical_elements", []),
                    "has_hierarchy": True,
                    "cropped_elements_count": len(cropped_elements),
                    "cropped_figure_count": len([elem for elem in cropped_elements if elem.get("type") in ["figure", "picture", "image"]]),
                    "cropped_table_count": len([elem for elem in cropped_elements if elem.get("type") == "table"])
                }
                
                pages_data.append(page_data)
                total_elements += len(page_layout.get("hierarchical_elements", []))
                
            except Exception as e:
                logger.error(f"Failed to process page {page_num + 1}: {e}")
                # エラーページのフォールバック
                pages_data.append({
                    "page_number": page_num + 1,
                    "layout_file": None,
                    "image_files": [],
                    "text_file": None,
                    "text_content": f"Error processing page {page_num + 1}",
                    "hierarchical_elements": [],
                    "has_hierarchy": False
                })
        
        # 画像サイズとPDFサイズ情報を取得（2つ目の場所）
        page_dimensions = None
        image_dimensions = None
        
        # 最初のページの画像サイズを取得
        if pages_data:
            first_page_image = images_dir / f"page_1_full.png"
            if first_page_image.exists():
                try:
                    from PIL import Image
                    with Image.open(first_page_image) as img:
                        image_dimensions = {
                            "width": img.width,
                            "height": img.height
                        }
                        logger.info(f"First page image dimensions (fallback): {img.width}x{img.height}")
                except Exception as e:
                    logger.warning(f"Failed to get image dimensions (fallback): {e}")
        
        # PDFページサイズを取得（Doclingから）
        if hasattr(document, 'page_dimensions') and document.page_dimensions:
            try:
                # 最初のページのサイズを取得
                first_page_dim = document.page_dimensions[0]
                page_dimensions = {
                    "width": first_page_dim.width,
                    "height": first_page_dim.height
                }
                logger.info(f"PDF page dimensions (fallback): {first_page_dim.width}x{first_page_dim.height}")
            except Exception as e:
                logger.warning(f"Failed to get PDF dimensions (fallback): {e}")
        
        # 総合メタデータ作成
        metadata = {
            "document_name": original_filename,
            "processing_timestamp": timestamp,
            "total_pages": num_pages,
            "total_elements": total_elements,
            "pages": pages_data,
            "processing_mode": "docling",
            "docling_metadata": doc_metadata,
            "text_extraction": {
                "method": "docling",
                "ocr_enabled": False
            },
            "dimensions": {
                "pdf_page": page_dimensions,
                "image_page": image_dimensions
            }
        }
        
        # メタデータファイル作成（削除予定：metadata_hierarchy.jsonに統合）
        # metadata_file = self.file_manager.create_metadata_file(output_dir, metadata)
        
        # フロントエンド用階層構造メタデータを作成（fallback処理）
        try:
            # 拡張メタデータが存在する場合のみ階層構造を作成
            metadata_ext_file = output_dir / "metadata_ext.json"
            if metadata_ext_file.exists():
                with open(metadata_ext_file, 'r', encoding='utf-8') as f:
                    extended_metadata = json.load(f)
                
                from .hierarchy_converter import HierarchyConverter
                
                hierarchy_converter = HierarchyConverter()
                hierarchy_metadata = hierarchy_converter.convert_to_frontend_hierarchy(
                    extended_metadata, metadata, document
                )
                
                # フォールバック時の構造サマリーを追加
                hierarchy_metadata["document_structure_summary"] = {
                    "total_sections": 1,
                    "document_type": "general_document",
                    "structure_confidence": 0.0,
                    "has_unified_structure": False
                }
                
                # metadata_hierarchy.json を保存
                hierarchy_file = hierarchy_converter.save_hierarchy_metadata(
                    hierarchy_metadata, output_dir
                )
                logger.info(f"Created frontend hierarchy metadata (fallback): {hierarchy_file}")
                
                # DB保存用に階層メタデータを保持
                self.processed_hierarchy_metadata = hierarchy_metadata
                
        except Exception as hierarchy_e:
            logger.warning(f"Failed to create hierarchy metadata in fallback: {hierarchy_e}")
        
        # 処理時間計算
        processing_time = (datetime.now() - datetime.fromisoformat(timestamp.replace('_', '')[:8] + 'T' + timestamp.replace('_', '')[8:10] + ':' + timestamp.replace('_', '')[10:12] + ':' + timestamp.replace('_', '')[12:14])).total_seconds()
        
        logger.info(f"Docling processing completed: {total_elements} elements extracted in {processing_time:.1f}s")
        
        return {
            "status": "success",
            "output_directory": str(output_dir.relative_to(self.output_base_dir.parent)),
            "files_created": {
                "original": str((output_dir / "original" / original_filename).relative_to(self.output_base_dir.parent)),
                "metadata_hierarchy": str((output_dir / "metadata_hierarchy.json").relative_to(self.output_base_dir.parent)),
                "layout_dir": str((output_dir / "layout").relative_to(self.output_base_dir.parent)),
                "images_dir": str((output_dir / "images").relative_to(self.output_base_dir.parent)),
                "text_dir": str((output_dir / "text").relative_to(self.output_base_dir.parent))
            },
            "total_pages": num_pages,
            "total_elements": total_elements,
            "processing_mode": "docling",
            "processing_time": f"{processing_time:.1f}s",
            "original_filename": original_filename,
            "metadata": getattr(self, 'processed_hierarchy_metadata', None)  # DB保存用メタデータ
        }
    
    def _extract_page_text(self, document, page_num: int, page_layout: Dict) -> str:
        """ページからテキストを抽出"""
        try:
            text_parts = []
            
            # レイアウト要素からテキストを抽出（階層構造対応）
            def extract_text_from_hierarchy(elements):
                for element in elements:
                    element_text = element.get("text", "")
                    if element_text and element_text.strip():
                        text_parts.append(element_text.strip())
                    # 子要素も再帰的に処理
                    if element.get("children"):
                        extract_text_from_hierarchy(element["children"])
            
            extract_text_from_hierarchy(page_layout.get("hierarchical_elements", []))
            
            # Docling document からの直接テキスト抽出（フォールバック）
            if not text_parts and hasattr(document, 'pages') and page_num < len(document.pages):
                try:
                    page = document.pages[page_num]
                    if hasattr(page, 'items'):
                        for item in page.items:
                            item_text = self.text_extractor.extract_text_content(item)
                            if item_text:
                                text_parts.append(item_text)
                except Exception as e:
                    logger.warning(f"Failed to extract text from page items: {e}")
            
            return "\\n".join(text_parts) if text_parts else f"Page {page_num + 1} - No text extracted"
            
        except Exception as e:
            logger.warning(f"Failed to extract page text: {e}")
            return f"Page {page_num + 1} - Text extraction failed"


# Global instance
_document_processor = None

def get_document_processor(use_layout_extractor: bool = True) -> DocumentProcessor:
    """Get global document processor instance.
    
    Args:
        use_layout_extractor: Whether to use layout extraction (default: True)
    """
    global _document_processor
    if _document_processor is None or _document_processor.use_layout_extractor != use_layout_extractor:
        _document_processor = DocumentProcessor(use_layout_extractor=use_layout_extractor)
    return _document_processor