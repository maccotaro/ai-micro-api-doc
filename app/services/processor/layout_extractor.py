"""
Layout extraction utilities for document processing.
Handles page layout analysis, element processing, and bounding box extraction.
"""

from pathlib import Path
from typing import Dict, List, Any
import logging
import re

from .utils import (
    get_element_type,
    get_docling_element_type,
    extract_bbox,
    is_item_on_page,
    get_pdf_page_size
)

logger = logging.getLogger(__name__)


def clean_docling_text(text: str) -> str:
    """Doclingが生成する非標準テキストをクリーンアップ"""
    if not text:
        return ""
    text = re.sub(r'<non-compliant-utf8-text>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


class LayoutExtractor:
    """Layout analysis and element extraction for document processing"""
    
    def __init__(self):
        pass
    
    def extract_page_layout(self, document, page_num: int, output_dir: Path) -> Dict[str, Any]:
        """Doclingドキュメントから特定ページのレイアウト情報を抽出（ExportedCCSDocument対応版）"""
        logger.info(f"Extracting layout for page {page_num + 1} using correct Docling API")
        
        # 実際のPDFページサイズを取得
        page_width, page_height = get_pdf_page_size(document, page_num)
        
        # ページレイアウト情報を初期化
        page_layout = {
            "page_number": page_num + 1,
            "width": page_width,
            "height": page_height,
            "elements": []
        }
        
        try:
            # ExportedCCSDocumentの場合の特別処理（最優先）
            try:
                from docling_core.types.doc.document import ExportedCCSDocument
                document_type_name = type(document).__name__
                logger.info(f"Document type check: {document_type_name}")
                
                if isinstance(document, ExportedCCSDocument):
                    logger.info(f"✅ Detected ExportedCCSDocument - using specialized extraction")
                    return self._extract_from_exported_ccs_document(document, page_num, page_width, page_height)
                elif document_type_name == 'ExportedCCSDocument':
                    logger.info(f"✅ Document type name matches ExportedCCSDocument - using specialized extraction")  
                    return self._extract_from_exported_ccs_document(document, page_num, page_width, page_height)
                else:
                    logger.info(f"Document is not ExportedCCSDocument, using traditional extraction")
            except ImportError as e:
                logger.warning(f"Could not import ExportedCCSDocument: {e}")
                # フォールバック: クラス名で判定
                if type(document).__name__ == 'ExportedCCSDocument':
                    logger.info(f"Using name-based ExportedCCSDocument detection")
                    return self._extract_from_exported_ccs_document(document, page_num, page_width, page_height)
            
            # 従来のDocumentタイプ処理
            # 方法1: Docling assembled elements (テーブルセルからレイアウト情報を抽出)
            logger.info(f"Trying assembled elements approach for page {page_num + 1}")
            if hasattr(document, 'assembled') and document.assembled and hasattr(document.assembled, 'elements'):
                logger.info(f"Found assembled elements: {len(document.assembled.elements)}")
                
                element_id = 0
                logger.error(f"DEBUG: Starting assembled elements loop with {len(document.assembled.elements)} elements")
                
                for i, assembled_element in enumerate(document.assembled.elements):
                    element_type = type(assembled_element).__name__
                    logger.info(f"Processing assembled element: {element_type}")
                    logger.info(f"Element class: {assembled_element.__class__}")
                    logger.info(f"Element module: {assembled_element.__class__.__module__}")
                    
                    # 汎用的な要素処理 - すべてのタイプに対応
                    logger.error(f"DEBUG: About to start universal processing for element {i}")
                    try:
                        logger.error(f"UNIVERSAL PROCESSING: Starting for {element_type}")
                        
                        # 複数の方法でバウンディングボックスを取得
                        element_bbox = None
                        
                        # 方法1: cluster.bbox
                        if hasattr(assembled_element, 'cluster') and assembled_element.cluster:
                            if hasattr(assembled_element.cluster, 'bbox'):
                                bbox = assembled_element.cluster.bbox
                                logger.error(f"UNIVERSAL: Found cluster.bbox: {bbox}")
                                element_bbox = {
                                    "x1": float(getattr(bbox, 'l', 0)),
                                    "y1": float(getattr(bbox, 't', 0)),
                                    "x2": float(getattr(bbox, 'r', 0)),
                                    "y2": float(getattr(bbox, 'b', 0))
                                }
                                logger.error(f"UNIVERSAL: Successfully extracted bbox from cluster: {element_bbox}")
                        
                        # 方法2: 直接bbox
                        if not element_bbox and hasattr(assembled_element, 'bbox') and assembled_element.bbox:
                            bbox = assembled_element.bbox
                            logger.error(f"UNIVERSAL: Found direct bbox: {bbox}")
                            element_bbox = {
                                "x1": float(getattr(bbox, 'l', 0)),
                                "y1": float(getattr(bbox, 't', 0)),
                                "x2": float(getattr(bbox, 'r', 0)),
                                "y2": float(getattr(bbox, 'b', 0))
                            }
                            logger.error(f"UNIVERSAL: Successfully extracted direct bbox: {element_bbox}")
                        
                        # 方法3: prov.bbox
                        if not element_bbox and hasattr(assembled_element, 'prov') and assembled_element.prov:
                            if len(assembled_element.prov) > 0 and hasattr(assembled_element.prov[0], 'bbox'):
                                bbox = assembled_element.prov[0].bbox
                                logger.error(f"UNIVERSAL: Found prov bbox: {bbox}")
                                element_bbox = {
                                    "x1": float(getattr(bbox, 'l', 0)),
                                    "y1": float(getattr(bbox, 't', 0)),
                                    "x2": float(getattr(bbox, 'r', 0)),
                                    "y2": float(getattr(bbox, 'b', 0))
                                }
                                logger.error(f"UNIVERSAL: Successfully extracted prov bbox: {element_bbox}")
                        
                        # バウンディングボックスが取得できた場合、要素を作成
                        if element_bbox:
                            # 要素を作成
                            layout_element = {
                                "type": "figure",  # FigureElementはfigureタイプ
                                "element_id": element_id,
                                "bbox": element_bbox,
                                "text": f"{element_type} 要素 {element_id + 1}"
                            }
                            page_layout["elements"].append(layout_element)
                            element_id += 1
                            logger.error(f"UNIVERSAL: Added element to layout: {layout_element}")
                        else:
                            logger.error(f"UNIVERSAL: No bbox found for {element_type}")
                        
                    except Exception as e:
                        logger.error(f"CRITICAL ERROR: Exception in universal processing for {element_type}: {e}")
                        import traceback
                        logger.error(f"TRACEBACK: {traceback.format_exc()}")
                        continue
                    
                    logger.error(f"DEBUG: Finished processing element {i}")
                
                logger.error(f"DEBUG: Finished assembled elements loop")
                logger.info(f"Found {len(page_layout['elements'])} elements in assembled approach")
            
            # 方法2: 通常のDocling elements（フォールバック）
            if len(page_layout['elements']) == 0:
                logger.info(f"No elements found in assembled approach, trying items approach")
                if hasattr(document, 'pages') and len(document.pages) > page_num:
                    page = document.pages[page_num]
                    
                    # Docling items from page
                    if hasattr(page, 'items') and page.items:
                        logger.info(f"Found {len(page.items)} items on page {page_num + 1}")
                        element_id = 0
                        
                        for item in page.items:
                            try:
                                if is_item_on_page(item, page_num):
                                    element_data = self.process_docling_element(item, element_id, page_height)
                                    if element_data:
                                        page_layout["elements"].append(element_data)
                                        element_id += 1
                            except Exception as e:
                                logger.warning(f"Failed to process item: {e}")
                                continue
                    
                    logger.info(f"Found {len(page_layout['elements'])} elements in items approach")
            
            # 方法3: 最終フォールバック（要素が見つからない場合）
            if len(page_layout['elements']) == 0:
                logger.warning(f"No layout elements detected for page {page_num + 1}")
                # フォールバック要素を作成
                fallback_element = {
                    "type": "text",
                    "element_id": 0,
                    "bbox": {
                        "x1": 50,
                        "y1": 50,
                        "x2": page_width - 50,
                        "y2": 150
                    },
                    "text": f"Page {page_num + 1} - No layout elements detected"
                }
                page_layout["elements"].append(fallback_element)
            
            logger.info(f"Final element count for page {page_num + 1}: {len(page_layout['elements'])}")
            return page_layout
            
        except Exception as e:
            logger.error(f"Error extracting page layout: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # エラー時のフォールバック
            page_layout["elements"] = [{
                "type": "text",
                "element_id": 0,
                "bbox": {
                    "x1": 50,
                    "y1": 50,
                    "x2": page_width - 50,
                    "y2": 150
                },
                "text": f"Page {page_num + 1} - Error in layout extraction"
            }]
            return page_layout
    
    def process_docling_element(self, element, element_id: int, page_height: float) -> Dict[str, Any]:
        """Docling要素を処理してlayout element形式に変換（デバッグ付き）"""
        try:
            logger.debug(f"Processing Docling element: {type(element).__name__}")
            
            # バウンディングボックスを取得
            bbox_data = self.extract_bbox_from_element(element, page_height)
            logger.debug(f"Extracted bbox: {bbox_data}")
            if not bbox_data:
                logger.debug(f"No bbox data found for {type(element).__name__}, skipping")
                return None
            
            # 要素タイプを取得
            element_type = get_element_type(element)
            logger.debug(f"Element type: {element_type}")
            
            # テキスト内容を取得
            text_content = self.extract_text_from_element(element)
            logger.debug(f"Text content: {text_content[:50] if text_content else 'None'}...")
            
            # テキストが文字化けしているかチェック
            if text_content and self._is_garbled_text(text_content):
                logger.warning(f"Detected garbled text: {repr(text_content[:100])}")
                # PDFから直接的にテキストを抽出する試み（将来の拡張用）
                # fallback_text = self._extract_text_from_pdf_region(document, bbox_data, page_num)
                # if fallback_text:
                #     text_content = fallback_text
            
            element_data = {
                "type": element_type,
                "element_id": element_id,
                "bbox": bbox_data,
                "text": text_content or f"{element_type} element"
            }
            
            # テーブル要素の場合は詳細データを追加
            if element_type.lower() in ['table'] and hasattr(element, 'data'):
                table_structure = self.extract_table_structure(element)
                if table_structure:
                    element_data["table_data"] = table_structure
            
            logger.debug(f"Created element data: {element_data}")
            return element_data
            
        except Exception as e:
            logger.warning(f"Failed to process Docling element: {e}")
            return None
    
    def extract_bbox_from_element(self, element, page_height: float) -> Dict[str, float]:
        """要素からバウンディングボックスを抽出（Docling prov対応版、座標変換付き）"""
        try:
            logger.debug(f"Extracting bbox from {type(element).__name__}")
            
            # 方法1: 直接bbox属性
            if hasattr(element, 'bbox') and element.bbox:
                bbox = element.bbox
                logger.debug(f"Found direct bbox: {bbox}")
                if hasattr(bbox, 'l') and hasattr(bbox, 't') and hasattr(bbox, 'r') and hasattr(bbox, 'b'):
                    return {
                        "x1": float(bbox.l),
                        "y1": float(bbox.t),
                        "x2": float(bbox.r),
                        "y2": float(bbox.b)
                    }
            
            # 方法2: prov[0].bbox属性（Doclingのメインケース）
            if hasattr(element, 'prov') and element.prov and len(element.prov) > 0:
                prov_item = element.prov[0]
                logger.debug(f"Found prov item: {prov_item}")
                if hasattr(prov_item, 'bbox') and prov_item.bbox:
                    bbox = prov_item.bbox
                    logger.debug(f"Found prov bbox: {bbox}")
                    if hasattr(bbox, 'l') and hasattr(bbox, 't') and hasattr(bbox, 'r') and hasattr(bbox, 'b'):
                        # Doclingのbboxは底左原点なので、画像描画用に上左原点に変換
                        # 底左原点での座標: t > b (tが上、bが下)
                        # 上左原点での座標: y1 < y2 (y1が上、y2が下)
                        # したがって: y1 = page_height - t, y2 = page_height - b
                        y1 = float(page_height - bbox.t)
                        y2 = float(page_height - bbox.b)
                        
                        # y1 > y2の場合は座標を交換
                        if y1 > y2:
                            y1, y2 = y2, y1
                        
                        return {
                            "x1": float(bbox.l),
                            "y1": y1,
                            "x2": float(bbox.r),
                            "y2": y2
                        }
            
            # 方法3: 他のbbox形式
            bbox_data = extract_bbox(element)
            if bbox_data and bbox_data.get('x1', 0) != bbox_data.get('x2', 0):
                logger.debug(f"Found bbox via extract_bbox: {bbox_data}")
                return bbox_data
            
            logger.debug(f"No valid bbox found for {type(element).__name__}")
            return None
            
        except Exception as e:
            logger.warning(f"Error extracting bbox from element: {e}")
            return None
    
    def extract_text_from_element(self, element) -> str:
        """要素からテキスト内容を抽出（Docling対応版）"""
        try:
            # デバッグ情報を詳細にログ出力
            logger.info(f"Extracting text from element type: {type(element).__name__}")
            logger.info(f"Element attributes: {[attr for attr in dir(element) if not attr.startswith('_')]}")
            
            # テキストをUTF-8として正しくデコードする補助関数
            def safe_decode_text(text_obj, source_attr="unknown") -> str:
                if text_obj is None:
                    return ""
                
                original_text = text_obj
                logger.info(f"Processing text from {source_attr}: type={type(text_obj)}, repr={repr(text_obj)}")
                
                # バイト列の場合はUTF-8でデコード
                if isinstance(text_obj, bytes):
                    try:
                        decoded = text_obj.decode('utf-8', errors='replace').strip()
                        logger.debug(f"Decoded bytes as UTF-8: {repr(decoded)}")
                        return clean_docling_text(decoded)
                    except:
                        decoded = text_obj.decode('latin-1', errors='replace').strip()
                        logger.debug(f"Decoded bytes as Latin-1: {repr(decoded)}")
                        return clean_docling_text(decoded)
                
                # 文字列の場合、エンコーディングの問題を修正
                text_str = str(text_obj)
                logger.debug(f"String representation: {repr(text_str)}")
                
                # 誤ったエンコーディングの文字列を修正する試み
                try:
                    # すべての文字を確認
                    char_analysis = [(i, ord(c), hex(ord(c)), c) for i, c in enumerate(text_str[:20])]
                    logger.debug(f"Character analysis (first 20): {char_analysis}")
                    
                    # Latin-1として誤って解釈された可能性がある場合、修正を試みる
                    if any(ord(c) > 127 for c in text_str):
                        # 方法1: Latin-1エンコード → UTF-8デコード
                        try:
                            fixed_text = text_str.encode('latin-1').decode('utf-8')
                            logger.debug(f"Fixed via latin-1→utf-8: {repr(fixed_text)}")
                            return clean_docling_text(fixed_text.strip())
                        except Exception as e1:
                            logger.debug(f"Latin-1→UTF-8 conversion failed: {e1}")
                        
                        # 方法2: cp1252エンコード → UTF-8デコード（Windowsファイル対応）
                        try:
                            fixed_text = text_str.encode('cp1252').decode('utf-8')
                            logger.debug(f"Fixed via cp1252→utf-8: {repr(fixed_text)}")
                            return clean_docling_text(fixed_text.strip())
                        except Exception as e2:
                            logger.debug(f"CP1252→UTF-8 conversion failed: {e2}")
                        
                        # 方法3: より詳細なエンコーディング変換を試行
                        encoding_attempts = [
                            ('latin-1', 'utf-8'),
                            ('cp1252', 'utf-8'),
                            ('iso-8859-1', 'utf-8'),
                            ('windows-1252', 'utf-8'),
                        ]
                        
                        for source_enc, target_enc in encoding_attempts:
                            try:
                                # エンコーディング変換を試行
                                temp_bytes = text_str.encode(source_enc)
                                fixed_text = temp_bytes.decode(target_enc)
                                
                                # 結果に日本語文字が含まれているかチェック
                                if any('\u3040' <= c <= '\u309F' or '\u30A0' <= c <= '\u30FF' or '\u4E00' <= c <= '\u9FAF' for c in fixed_text):
                                    logger.debug(f"Successful conversion via {source_enc}→{target_enc}: {repr(fixed_text)}")
                                    return clean_docling_text(fixed_text.strip())
                                elif len(fixed_text.strip()) > 0 and all(ord(c) < 256 for c in fixed_text):
                                    # ASCII/拡張ASCII文字のみの場合でも有効な結果として保存
                                    logger.debug(f"ASCII conversion via {source_enc}→{target_enc}: {repr(fixed_text)}")
                                    candidate_result = fixed_text.strip()
                            except Exception as e_inner:
                                logger.debug(f"Encoding conversion {source_enc}→{target_enc} failed: {e_inner}")
                                continue
                        
                        # 直接的な日本語フォント文字コードの処理を試行
                        try:
                            clean_chars = []
                            for c in text_str:
                                char_code = ord(c)
                                if char_code < 128:  # ASCII範囲
                                    clean_chars.append(c)
                                elif 0xFF61 <= char_code <= 0xFF9F:  # 半角カタカナ範囲
                                    clean_chars.append(c)  # そのまま保持
                                elif char_code in range(128, 256):  # 拡張ASCII
                                    # PDFフォントエンコーディングからUnicodeへの変換を試行
                                    try:
                                        # 一般的なPDFエンコーディングマッピング
                                        if 0x81 <= char_code <= 0x9F or 0xE0 <= char_code <= 0xFC:
                                            # Shift_JISの1バイト目の可能性
                                            clean_chars.append('?')  # プレースホルダー
                                        else:
                                            # Latin-1として扱える文字
                                            byte_val = bytes([char_code])
                                            try:
                                                utf8_char = byte_val.decode('utf-8', errors='replace')
                                                clean_chars.append(utf8_char)
                                            except:
                                                clean_chars.append('?')
                                    except:
                                        clean_chars.append('?')
                                else:
                                    clean_chars.append(c)  # Unicode文字はそのまま
                            
                            result = ''.join(clean_chars)
                            logger.debug(f"Character-by-character conversion: {repr(result)}")
                            return clean_docling_text(result.strip())
                        except Exception as e3:
                            logger.debug(f"Character-by-character conversion failed: {e3}")
                
                except Exception as outer_e:
                    logger.debug(f"Text fixing attempts failed: {outer_e}")

                return clean_docling_text(text_str.strip())
            
            # 新しいアプローチ: Doclingの正しいテキスト抽出方法
            # Docling 1.7.0+では、要素から直接テキストを取得する正しい方法が異なる可能性
            try:
                # ExportedCCSDocumentの要素にはexport()メソッドがある場合
                if hasattr(element, 'export'):
                    exported = element.export()
                    logger.info(f"Exported element data: {type(exported)}, {repr(exported)}")
                    if hasattr(exported, 'text'):
                        result = safe_decode_text(exported.text, "exported.text")
                        logger.info(f"Extracted via exported.text: {repr(result)}")
                        return result
                
                # CCS要素の場合、正しいテキスト取得方法
                if hasattr(element, 'text') and element.text is not None:
                    # 直接文字列として扱わず、適切にデコード
                    raw_text = element.text
                    logger.info(f"Raw element.text: type={type(raw_text)}, value={repr(raw_text)}")
                    
                    # 文字列の場合、直接使用（エンコーディング変換なし）
                    if isinstance(raw_text, str):
                        logger.info(f"Using direct string: {repr(raw_text)}")
                        return clean_docling_text(raw_text)  # エンコーディング変換を避ける
                    else:
                        result = safe_decode_text(raw_text, "element.text")
                        logger.info(f"Extracted via safe_decode (element.text): {repr(result)}")
                        return result
                
            except Exception as text_extract_error:
                logger.warning(f"Failed to extract text using new method: {text_extract_error}")
            
            # 方法1: 直接text属性（フォールバック）
            if hasattr(element, 'text') and element.text:
                result = safe_decode_text(element.text, "element.text")
                logger.info(f"Extracted via element.text (fallback): {repr(result)}")
                return result
            
            # 方法2: content属性
            if hasattr(element, 'content') and element.content:
                result = safe_decode_text(element.content, "element.content")
                logger.info(f"Extracted via element.content: {repr(result)}")
                return result
            
            # 方法3: prov経由でのテキスト取得
            if hasattr(element, 'prov') and element.prov:
                text_parts = []
                for i, prov_item in enumerate(element.prov):
                    if hasattr(prov_item, 'text') and prov_item.text:
                        decoded_text = safe_decode_text(prov_item.text, f"prov[{i}].text")
                        if decoded_text:
                            text_parts.append(decoded_text)
                    
                    # prov_itemから直接rawテキストを取得する試み
                    if hasattr(prov_item, 'raw_text'):
                        raw_decoded = safe_decode_text(prov_item.raw_text, f"prov[{i}].raw_text")
                        if raw_decoded and raw_decoded not in text_parts:
                            text_parts.append(raw_decoded)
                    
                    # bbox情報とともに格納されているテキストの確認
                    if hasattr(prov_item, 'content'):
                        content_decoded = safe_decode_text(prov_item.content, f"prov[{i}].content")
                        if content_decoded and content_decoded not in text_parts:
                            text_parts.append(content_decoded)
                
                if text_parts:
                    result = " ".join(text_parts)
                    logger.debug(f"Extracted via prov: {repr(result)}")
                    return result
            
            # 方法4: value属性（数式など）
            if hasattr(element, 'value') and element.value:
                result = safe_decode_text(element.value, "element.value")
                logger.debug(f"Extracted via element.value: {repr(result)}")
                return result
            
            # 方法5: data属性（構造化データ）
            if hasattr(element, 'data') and element.data:
                # テーブルデータの場合
                if hasattr(element.data, 'table'):
                    return self.extract_table_text(element)
                # その他のデータ構造
                elif isinstance(element.data, str):
                    result = safe_decode_text(element.data, "element.data")
                    logger.debug(f"Extracted via element.data: {repr(result)}")
                    return result
            
            # デバッグ用：要素の属性を確認
            logger.debug(f"Element attributes: {dir(element)}")
            logger.debug(f"No text found in element {type(element).__name__}")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting text from element: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return ""
    
    def extract_table_text(self, table_element) -> str:
        """テーブル要素からテキストを抽出"""
        try:
            if not hasattr(table_element, 'data') or not hasattr(table_element.data, 'table'):
                return ""
            
            # テキストをUTF-8として正しくデコードする補助関数
            def safe_decode_text(text_obj) -> str:
                if text_obj is None:
                    return ""

                # バイト列の場合はUTF-8でデコード
                if isinstance(text_obj, bytes):
                    try:
                        return clean_docling_text(text_obj.decode('utf-8', errors='replace').strip())
                    except:
                        return clean_docling_text(text_obj.decode('latin-1', errors='replace').strip())

                # 文字列の場合、エンコーディングの問題を修正
                text_str = str(text_obj)

                # 誤ったエンコーディングの文字列を修正する試み
                try:
                    if any(ord(c) > 127 for c in text_str):
                        try:
                            fixed_text = text_str.encode('latin-1').decode('utf-8')
                            return clean_docling_text(fixed_text.strip())
                        except:
                            pass
                except:
                    pass

                return clean_docling_text(text_str.strip())
            
            table_data = table_element.data.table
            text_parts = []
            
            # テーブルの各行を処理
            if hasattr(table_data, 'rows'):
                for row in table_data.rows:
                    row_text = []
                    if hasattr(row, 'cells'):
                        for cell in row.cells:
                            if hasattr(cell, 'text') and cell.text:
                                decoded_text = safe_decode_text(cell.text)
                                if decoded_text:
                                    row_text.append(decoded_text)
                    if row_text:
                        text_parts.append(" | ".join(row_text))
            
            return "\n".join(text_parts) if text_parts else "Table content"
            
        except Exception as e:
            logger.warning(f"Error extracting table text: {e}")
            return "Table content"
    
    def extract_table_structure(self, table_element) -> dict:
        """テーブル要素から構造化情報を抽出"""
        try:
            if not hasattr(table_element, 'data') or not hasattr(table_element.data, 'table'):
                return None
            
            # テキストをUTF-8として正しくデコードする補助関数
            def safe_decode_text(text_obj) -> str:
                if text_obj is None:
                    return ""

                # バイト列の場合はUTF-8でデコード
                if isinstance(text_obj, bytes):
                    try:
                        return clean_docling_text(text_obj.decode('utf-8', errors='replace').strip())
                    except:
                        return clean_docling_text(text_obj.decode('latin-1', errors='replace').strip())

                # 文字列の場合、エンコーディングの問題を修正
                text_str = str(text_obj)

                # 誤ったエンコーディングの文字列を修正する試み
                try:
                    if any(ord(c) > 127 for c in text_str):
                        try:
                            fixed_text = text_str.encode('latin-1').decode('utf-8')
                            return clean_docling_text(fixed_text.strip())
                        except:
                            pass
                except:
                    pass

                return clean_docling_text(text_str.strip())
            
            table_data = table_element.data.table
            structure = {
                "rows": [],
                "columns": 0,
                "cells": []
            }
            
            # テーブルの各行と列を処理
            if hasattr(table_data, 'rows'):
                max_cols = 0
                for row_idx, row in enumerate(table_data.rows):
                    row_info = {"cells": []}
                    if hasattr(row, 'cells'):
                        for col_idx, cell in enumerate(row.cells):
                            cell_text = safe_decode_text(cell.text) if hasattr(cell, 'text') else ""
                            cell_info = {
                                "text": cell_text,
                                "row": row_idx,
                                "column": col_idx
                            }
                            
                            # セルのbboxがある場合は追加
                            if hasattr(cell, 'bbox'):
                                cell_info["bbox"] = extract_bbox(cell)
                            
                            row_info["cells"].append(cell_info)
                            structure["cells"].append(cell_info)
                        
                        max_cols = max(max_cols, len(row.cells))
                    
                    structure["rows"].append(row_info)
                
                structure["columns"] = max_cols
            
            return structure if structure["cells"] else None
            
        except Exception as e:
            logger.warning(f"Error extracting table structure: {e}")
            return None
    
    def _is_garbled_text(self, text: str) -> bool:
        """テキストが文字化けしているかどうかを判定"""
        if not text or len(text.strip()) == 0:
            return False
        
        # 文字化けのパターンを検出
        try:
            # 拡張ASCII文字が30%以上含まれている
            high_ascii_ratio = sum(1 for c in text if 127 < ord(c) < 256) / len(text)
            if high_ascii_ratio > 0.3:
                return True
            
            # #記号と高位文字の組み合わせ
            if '#' in text and any(ord(c) > 200 for c in text):
                return True
            
            # Latin-1特殊文字が20%以上
            latin1_chars = '¡¢£¤¥¦§¨©ª«¬­®¯°±²³´µ¶·¸¹º»¼½¾¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏ'
            latin1_ratio = sum(1 for c in text if c in latin1_chars) / len(text)
            if latin1_ratio > 0.2:
                return True
            
            # ?と高位文字の組み合わせ
            if '?' in text and any(ord(c) > 200 for c in text):
                return True
            
            # 日本語文字が含まれている場合は正常とみなす
            if any('\u3040' <= c <= '\u309F' or '\u30A0' <= c <= '\u30FF' or '\u4E00' <= c <= '\u9FAF' for c in text):
                return False
            
            # ASCII文字のみの場合は正常とみなす
            if all(ord(c) < 128 for c in text):
                return False
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking garbled text: {e}")
            return False
    
    def _extract_from_exported_ccs_document(self, document, page_num: int, page_width: float, page_height: float) -> Dict[str, Any]:
        """ExportedCCSDocument形式からFigureElementやその他の要素を抽出"""
        try:
            logger.info(f"ExportedCCSDocument processing for page {page_num + 1}")
            
            page_layout = {
                "page_number": page_num + 1,
                "width": page_width,
                "height": page_height,
                "elements": []
            }
            
            # ページ全体のインデント構造を事前分析
            self.page_indent_analysis = self._analyze_page_indent_structure(document, page_num)
            
            element_id = 0
            
            # ExportedCCSDocumentの要素抽出方法を探索
            logger.info(f"ExportedCCSDocument attributes: {[attr for attr in dir(document) if not attr.startswith('_')]}")
            
            # 方法1: figuresからの抽出（図表要素、ページフィルタ付き）
            if hasattr(document, 'figures') and document.figures:
                logger.info(f"Found figures collection: {len(document.figures)} items")
                
                for i, figure in enumerate(document.figures):
                    # ページ番号でフィルタリング
                    if not self._is_element_on_page(figure, page_num + 1):
                        continue
                        
                    logger.info(f"Processing figure {i}: {type(figure).__name__}")
                    
                    figure_element = self._process_figure_element(figure, element_id, page_height)
                    if figure_element:
                        page_layout["elements"].append(figure_element)
                        element_id += 1
                        logger.info(f"Added figure to layout: {figure_element}")
            
            # 方法1b: tablesからの抽出（テーブル要素、ページフィルタ付き）
            if hasattr(document, 'tables') and document.tables:
                logger.info(f"Found tables collection: {len(document.tables)} items")
                
                for i, table in enumerate(document.tables):
                    # ページ番号でフィルタリング
                    if not self._is_element_on_page(table, page_num + 1):
                        continue
                        
                    logger.info(f"Processing table {i}: {type(table).__name__}")
                    
                    table_elements = self._process_table_element(table, element_id, page_height)
                    if table_elements:
                        for table_element in table_elements:
                            page_layout["elements"].append(table_element)
                            element_id += 1
                        logger.info(f"Added {len(table_elements)} table elements to layout")
            
            # 方法1c: body.elementsからの抽出（その他要素のフォールバック）
            if hasattr(document, 'body') and document.body:
                logger.info(f"Found document.body: {type(document.body)}")
                if hasattr(document.body, 'elements') and document.body.elements:
                    logger.info(f"Found body elements: {len(document.body.elements)}")
                    
                    for i, element in enumerate(document.body.elements):
                        element_type = type(element).__name__
                        logger.info(f"Processing body element {i}: {element_type}")
                        
                        # FigureElementやその他の要素を処理
                        layout_element = self._process_ccs_element(element, element_id, page_height)
                        if layout_element:
                            page_layout["elements"].append(layout_element)
                            element_id += 1
                            logger.info(f"Added {element_type} to layout: {layout_element}")
            
            # 方法2: main_textからの個別テキスト要素抽出（ページフィルタ付き）
            if hasattr(document, 'main_text') and document.main_text:
                logger.info(f"Found main_text collection: {len(document.main_text)} items")
                
                for i, text_item in enumerate(document.main_text):
                    logger.info(f"Processing main_text item {i}: {type(text_item).__name__}")
                    
                    # テーブル参照はスキップ（既にtablesコレクションで処理済み）
                    if hasattr(text_item, 'obj_type') and text_item.obj_type == 'table':
                        logger.info(f"Skipping table reference (already processed from tables collection)")
                        continue
                    
                    # ページ番号でフィルタリング
                    if not self._is_element_on_page(text_item, page_num + 1):
                        continue
                    
                    # prov属性があるテキスト要素を処理
                    if hasattr(text_item, 'prov') and text_item.prov:
                        text_element = self._process_main_text_item(text_item, element_id)
                        if text_element:
                            page_layout["elements"].append(text_element)
                            element_id += 1
                            logger.info(f"Added main_text item to layout: {text_element}")
                    else:
                        logger.debug(f"Skipping main_text item without prov: {type(text_item).__name__}")
            
            # 方法2b: フォールバック（要素が全く見つからない場合のみ）
            if len(page_layout["elements"]) == 0 and hasattr(document, 'main_text') and document.main_text:
                logger.warning("No elements found, creating fallback text element")
                text_element = {
                    "type": "text", 
                    "element_id": element_id,
                    "bbox": {
                        "x1": 50,
                        "y1": 50, 
                        "x2": page_width - 50,
                        "y2": 200
                    },
                    "text": "Fallback text element"
                }
                page_layout["elements"].append(text_element)
                element_id += 1
            
            # 方法3: textsからの抽出
            if hasattr(document, 'texts') and document.texts:
                logger.info(f"Found texts collection: {len(document.texts)} items")
                
                for i, text_item in enumerate(document.texts):
                    logger.info(f"Processing text item {i}: {type(text_item)}")
                    
                    text_element = self._process_text_item(text_item, element_id, page_height)
                    if text_element:
                        page_layout["elements"].append(text_element)
                        element_id += 1
            
            # 方法4: picturesからの抽出（図表要素）
            if hasattr(document, 'pictures') and document.pictures:
                logger.info(f"Found pictures collection: {len(document.pictures)} items")
                
                for i, picture_item in enumerate(document.pictures):
                    logger.info(f"Processing picture item {i}: {type(picture_item)}")
                    
                    picture_element = self._process_picture_item(picture_item, element_id, page_height)
                    if picture_element:
                        page_layout["elements"].append(picture_element)
                        element_id += 1
            
            # 結果の確認
            logger.info(f"ExportedCCSDocument extraction completed: {len(page_layout['elements'])} elements found")
            
            # 要素が見つからない場合のフォールバック
            if len(page_layout["elements"]) == 0:
                logger.warning("No elements found in ExportedCCSDocument, adding fallback element")
                fallback_element = {
                    "type": "text",
                    "element_id": 0,
                    "bbox": {
                        "x1": 50,
                        "y1": 50,
                        "x2": page_width - 50,
                        "y2": 150
                    },
                    "text": f"Page {page_num + 1} - ExportedCCSDocument (no elements detected)"
                }
                page_layout["elements"].append(fallback_element)
            
            return page_layout
            
        except Exception as e:
            logger.error(f"Error extracting from ExportedCCSDocument: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            # エラー時のフォールバック
            return {
                "page_number": page_num + 1,
                "width": page_width,
                "height": page_height,
                "elements": [{
                    "type": "text",
                    "element_id": 0,
                    "bbox": {
                        "x1": 50,
                        "y1": 50,
                        "x2": page_width - 50,
                        "y2": 150
                    },
                    "text": f"Page {page_num + 1} - ExportedCCSDocument extraction error"
                }]
            }
    
    def _process_ccs_element(self, element, element_id: int, page_height: float) -> Dict[str, Any]:
        """ExportedCCSDocumentの個別要素を処理"""
        try:
            element_type = type(element).__name__
            logger.info(f"Processing CCS element: {element_type}")
            
            # バウンディングボックスを抽出
            bbox_data = self._extract_bbox_from_ccs_element(element, page_height)
            if not bbox_data:
                logger.warning(f"No bbox found for CCS element: {element_type}")
                return None
            
            # テキストを抽出
            text_content = self._extract_text_from_ccs_element(element)
            
            # 要素タイプを決定
            layout_type = self._determine_layout_type(element_type)
            
            return {
                "type": layout_type,
                "element_id": element_id,
                "bbox": bbox_data,
                "text": text_content or f"{element_type} element"
            }
            
        except Exception as e:
            logger.warning(f"Error processing CCS element: {e}")
            return None
    
    def _process_text_item(self, text_item, element_id: int, page_height: float) -> Dict[str, Any]:
        """テキストアイテムを処理"""
        try:
            bbox_data = self._extract_bbox_from_ccs_element(text_item, page_height)
            text_content = self._extract_text_from_ccs_element(text_item)
            
            if not bbox_data or not text_content:
                return None
            
            return {
                "type": "text",
                "element_id": element_id,
                "bbox": bbox_data,
                "text": text_content
            }
            
        except Exception as e:
            logger.warning(f"Error processing text item: {e}")
            return None
    
    def _process_picture_item(self, picture_item, element_id: int, page_height: float) -> Dict[str, Any]:
        """画像アイテムを処理"""
        try:
            bbox_data = self._extract_bbox_from_ccs_element(picture_item, page_height)
            
            if not bbox_data:
                return None
            
            return {
                "type": "figure",
                "element_id": element_id,
                "bbox": bbox_data,
                "text": f"Figure {element_id + 1}"
            }
            
        except Exception as e:
            logger.warning(f"Error processing picture item: {e}")
            return None
    
    def _process_figure_element(self, figure, element_id: int, page_height: float) -> Dict[str, Any]:
        """ExportedCCSDocumentのFigure要素を処理"""
        try:
            logger.info(f"Processing Figure element: {type(figure).__name__}")
            
            # bboxを抽出（provから）
            bbox_data = None
            if hasattr(figure, 'prov') and figure.prov and len(figure.prov) > 0:
                prov_item = figure.prov[0]
                if hasattr(prov_item, 'bbox') and prov_item.bbox:
                    # Docling bbox形式: [left, top, right, bottom]のリスト
                    bbox_list = prov_item.bbox
                    if isinstance(bbox_list, list) and len(bbox_list) == 4:
                        left, top, right, bottom = bbox_list
                        # 座標変換: Doclingの底左原点から上左原点へ
                        y1 = float(page_height - top)
                        y2 = float(page_height - bottom)
                        if y1 > y2:
                            y1, y2 = y2, y1
                        
                        bbox_data = {
                            "x1": float(left),
                            "y1": y1,
                            "x2": float(right),
                            "y2": y2
                        }
                        logger.info(f"Figure bbox extracted: {bbox_data}")
            
            if not bbox_data:
                logger.warning(f"No bbox found for figure element")
                return None
            
            # テキストを取得
            raw_text = getattr(figure, 'text', '')
            text_content = clean_docling_text(raw_text) if raw_text else f"Figure {element_id + 1}"
            
            return {
                "type": "figure",
                "element_id": element_id,
                "bbox": bbox_data,
                "text": text_content
            }
            
        except Exception as e:
            logger.warning(f"Error processing figure element: {e}")
            import traceback
            logger.warning(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _process_table_element(self, table, element_id: int, page_height: float) -> List[Dict[str, Any]]:
        """ExportedCCSDocumentのTable要素を処理（セル単位で）"""
        try:
            logger.info(f"Processing Table element: {type(table).__name__}")
            
            # テーブル全体のbboxを取得
            table_bbox_data = None
            if hasattr(table, 'prov') and table.prov and len(table.prov) > 0:
                prov_item = table.prov[0]
                if hasattr(prov_item, 'bbox') and prov_item.bbox:
                    bbox_list = prov_item.bbox
                    if isinstance(bbox_list, list) and len(bbox_list) == 4:
                        left, top, right, bottom = bbox_list
                        # テーブルの座標は画像座標系（左上原点）として扱う
                        # Doclingのテーブル処理は画像座標系で返す
                        table_bbox_data = {
                            "x1": float(left),
                            "y1": float(top),
                            "x2": float(right),
                            "y2": float(bottom)
                        }
                        logger.info(f"Table bbox extracted: {table_bbox_data}")
            
            if not table_bbox_data:
                logger.warning(f"No bbox found for table element")
                return []
            
            elements = []
            cell_element_id = element_id
            
            # セル単位で処理
            if hasattr(table, 'data') and table.data:
                logger.info(f"Processing {len(table.data)} rows in table")
                
                for row_idx, row in enumerate(table.data):
                    if not isinstance(row, list):
                        continue
                        
                    for col_idx, cell in enumerate(row):
                        # GlmTableCellオブジェクトから情報を抽出
                        if hasattr(cell, 'text') and hasattr(cell, 'bbox'):
                            cell_text = clean_docling_text(getattr(cell, 'text', '').strip())
                            cell_bbox = getattr(cell, 'bbox', None)
                            
                            # 空のセルはスキップ
                            if not cell_text:
                                continue
                            
                            # bboxが存在する場合のみ処理
                            if cell_bbox and isinstance(cell_bbox, list) and len(cell_bbox) == 4:
                                left, top, right, bottom = cell_bbox
                                
                                # テーブルセルの座標も画像座標系の可能性があるため確認
                                if top < bottom:  # 正常な画像座標系
                                    cell_bbox_data = {
                                        "x1": float(left),
                                        "y1": float(top),
                                        "x2": float(right),
                                        "y2": float(bottom)
                                    }
                                else:  # PDF座標系の場合
                                    y1 = float(page_height - top)
                                    y2 = float(page_height - bottom)
                                    if y1 > y2:
                                        y1, y2 = y2, y1
                                    
                                    cell_bbox_data = {
                                        "x1": float(left),
                                        "y1": y1,
                                        "x2": float(right),
                                        "y2": y2
                                    }
                                
                                # セル要素を作成
                                cell_element = {
                                    "type": "table_cell",
                                    "element_id": cell_element_id,
                                    "bbox": cell_bbox_data,
                                    "text": cell_text,
                                    "table_info": {
                                        "row": row_idx,
                                        "col": col_idx,
                                        "cell_type": getattr(cell, 'obj_type', 'body'),
                                        "is_header": getattr(cell, 'col_header', False) or getattr(cell, 'row_header', False)
                                    }
                                }
                                
                                elements.append(cell_element)
                                cell_element_id += 1
                                
                                logger.debug(f"Added cell [{row_idx},{col_idx}]: {cell_text[:30]}...")
            
            # テーブル全体の要素も追加（背景として）
            table_element = {
                "type": "table",
                "element_id": element_id,
                "bbox": table_bbox_data,
                "text": f"Table with {len(elements)} cells"
            }
            elements.insert(0, table_element)
            
            logger.info(f"Processed table: {len(elements)} elements (1 table + {len(elements)-1} cells)")
            return elements
            
        except Exception as e:
            logger.warning(f"Error processing table element: {e}")
            import traceback
            logger.warning(f"Traceback: {traceback.format_exc()}")
            return []
    
    def _process_main_text_item(self, text_item, element_id: int) -> Dict[str, Any]:
        """ExportedCCSDocumentのmain_text項目を処理"""
        try:
            logger.info(f"Processing main_text item: {type(text_item).__name__}")
            
            # prov情報からbboxを抽出
            bbox_data = None
            if hasattr(text_item, 'prov') and text_item.prov and len(text_item.prov) > 0:
                prov_item = text_item.prov[0]
                if hasattr(prov_item, 'bbox') and prov_item.bbox:
                    bbox_list = prov_item.bbox
                    if isinstance(bbox_list, list) and len(bbox_list) == 4:
                        left, top, right, bottom = bbox_list
                        # Doclingの座標系はそのまま使用（左上原点）
                        # bbox形式: [x1, y1, x2, y2] where (x1,y1) is top-left and (x2,y2) is bottom-right
                        bbox_data = {
                            "x1": float(left),
                            "y1": float(top),
                            "x2": float(right),
                            "y2": float(bottom)
                        }
                        logger.debug(f"Main_text bbox extracted: {bbox_data}")
            
            if not bbox_data:
                logger.warning(f"No bbox found for main_text item")
                return None
            
            # テキスト内容を取得
            text_content = ""
            if hasattr(text_item, 'text') and text_item.text:
                text_content = clean_docling_text(str(text_item.text).strip())
            
            # obj_typeに基づいて要素タイプを決定
            element_type = "text"  # デフォルト
            if hasattr(text_item, 'obj_type'):
                obj_type = text_item.obj_type
                if obj_type == 'subtitle-level-1':
                    element_type = "title"
                elif obj_type == 'page-header':
                    element_type = "page_header"  # DocLayNet標準
                elif obj_type == 'section-header':
                    element_type = "title"  # DocLayNet標準にtitleに統一
                elif obj_type == 'paragraph':
                    element_type = "text"
                else:
                    element_type = "text"
            
            # テキスト内容によるキャプション判定
            if self._is_caption_text(text_content):
                element_type = "caption"
            
            # テキスト内容と位置によるフッター判定
            if bbox_data and self._is_footer_text(text_content, bbox_data):
                element_type = "page_footer"  # DocLayNet標準
            
            # テキスト内容によるリスト項目判定を最優先で行う
            # titleと判定されたものも再チェック（DocLayNet標準）
            if (element_type == "text" or element_type == "title") and self._is_list_item_text(text_content):
                element_type = "list_item"
            # 前ページからの継続テキストを判定（リスト項目でない場合）
            elif element_type == "text" and self._is_continuation_text(text_content, bbox_data):
                element_type = "text"  # DocLayNet標準では継続テキストもtext
            # テキスト内容と位置によるヘッダー判定（obj_typeがない場合）
            elif element_type == "text" and bbox_data and self._is_header_text(text_content, bbox_data):
                element_type = "page_header"  # DocLayNet標準
            # テキスト内容によるタイトル判定（リスト項目、継続テキスト、ヘッダーでない場合のみ）
            elif element_type == "text" and self._is_section_header_text(text_content):
                element_type = "title"  # DocLayNet標準にtitleに統一
            
            logger.debug(f"Main_text item type: {element_type}, text: '{text_content[:30]}...'")
            
            # リスト項目の場合、階層レベルを計算
            list_info = {}
            if element_type == "list_item" and bbox_data:
                # 動的インデント分析を優先使用
                indent_level = self._calculate_dynamic_list_indent_level(bbox_data)
                list_info = {
                    "indent_level": indent_level,
                    "is_nested": indent_level > 0
                }
            
            result = {
                "type": element_type,
                "element_id": element_id,
                "bbox": bbox_data,
                "text": text_content
            }
            
            if list_info:
                result["list_info"] = list_info
            
            return result
            
        except Exception as e:
            logger.warning(f"Error processing main_text item: {e}")
            import traceback
            logger.warning(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _is_caption_text(self, text_content: str) -> bool:
        """テキスト内容がキャプションかどうかを判定"""
        if not text_content or len(text_content) > 200:  # キャプションは通常短い
            return False
        
        text_lower = text_content.lower().strip()
        
        # 日本語のキャプションパターン
        japanese_patterns = [
            r'^図\s*\d+[\.\s]',      # 図1. 図 1.
            r'^表\s*\d+[\.\s]',      # 表1. 表 1.
            r'^写真\s*\d+[\.\s]',    # 写真1.
            r'^グラフ\s*\d+[\.\s]',  # グラフ1.
            r'^チャート\s*\d+[\.\s]', # チャート1.
        ]
        
        # 英語のキャプションパターン
        english_patterns = [
            r'^figure\s*\d+[\.\s]',   # Figure 1.
            r'^table\s*\d+[\.\s]',    # Table 1.
            r'^chart\s*\d+[\.\s]',    # Chart 1.
            r'^graph\s*\d+[\.\s]',    # Graph 1.
            r'^image\s*\d+[\.\s]',    # Image 1.
        ]
        
        import re
        
        # 日本語パターンをチェック
        for pattern in japanese_patterns:
            if re.match(pattern, text_content):
                logger.info(f"Detected Japanese caption pattern: '{text_content[:50]}...'")
                return True
        
        # 英語パターンをチェック
        for pattern in english_patterns:
            if re.match(pattern, text_lower):
                logger.info(f"Detected English caption pattern: '{text_content[:50]}...'")
                return True
        
        return False
    
    def _is_footer_text(self, text_content: str, bbox_data: Dict[str, float]) -> bool:
        """テキスト内容と位置がフッターかどうかを判定"""
        if not text_content or len(text_content) > 300:  # フッターは通常短い
            return False
        
        text_lower = text_content.lower().strip()
        
        # ページ下部に位置するかチェック（y座標が小さい = ページ下部）
        y1 = bbox_data.get('y1', 0)
        y2 = bbox_data.get('y2', 0)
        avg_y = (y1 + y2) / 2
        
        # ページ下部15%の範囲内にあることを確認（PDF座標系）
        is_bottom_area = avg_y < 130  # 842高さの約15%
        
        # フッターの典型的なパターン
        footer_patterns = [
            # 著作権表示
            r'copyright.*\d{4}',
            r'©.*\d{4}',
            r'\(c\).*\d{4}',
            
            # ページ番号（単独の数字）
            r'^\s*\d+\s*$',
            r'^\s*-\s*\d+\s*-\s*$',
            r'^\s*\|\s*\d+\s*\|\s*$',
            
            # 会社名・組織名
            r'all rights reserved',
            r'株式会社',
            r'有限会社',
            r'co\.,?\s*ltd',
            r'corporation',
            r'inc\.',
            
            # URLやEmail
            r'https?://',
            r'www\.',
            r'@.*\.(com|org|jp|gov)',
            
            # 機密性表示
            r'confidential',
            r'機密',
            r'内部資料',
            r'社外秘',
        ]
        
        import re
        
        # フッターパターンをチェック
        for pattern in footer_patterns:
            if re.search(pattern, text_lower):
                if is_bottom_area:
                    logger.info(f"Detected footer pattern in bottom area: '{text_content[:50]}...'")
                    return True
                else:
                    logger.debug(f"Footer pattern found but not in bottom area: '{text_content[:30]}...' at y={avg_y}")
        
        # ページ番号の特別判定（数字のみの場合）
        if re.match(r'^\s*\d+\s*$', text_content.strip()) and is_bottom_area:
            logger.info(f"Detected page number footer: '{text_content.strip()}'")
            return True
        
        return False
    
    def _is_header_text(self, text_content: str, bbox_data: Dict[str, float]) -> bool:
        """テキスト内容と位置がヘッダーかどうかを判定"""
        if not text_content or len(text_content) > 200:  # ヘッダーは通常短い
            return False
        
        # ページ上部に位置するかチェック（y座標が大きい = ページ上部）
        y1 = bbox_data.get('y1', 0)
        y2 = bbox_data.get('y2', 0)
        avg_y = (y1 + y2) / 2
        
        # ページ上部15%の範囲内にあることを確認（PDF座標系）
        is_top_area = avg_y > 712  # 842高さの約85%以上
        
        # 文の途中から始まるテキストを除外（前ページからの続き）
        text_strip = text_content.strip()
        if text_strip and not text_strip[0].isupper() and text_strip[0] not in '第（(':
            # 小文字や助詞で始まる場合は前ページからの続きの可能性が高い
            if text_strip[0] in 'わらずものことため' or text_strip.startswith('らず'):
                logger.debug(f"Excluded continuation text from header: '{text_content[:30]}...'")
                return False
        
        if is_top_area:
            # ページ上部にあれば、ヘッダーの可能性が高い
            # 但し、タイトルやセクション見出しでないことを確認
            if not self._is_section_header_text(text_content):
                logger.info(f"Detected header in top area: '{text_content[:50]}...'")
                return True
        
        return False
    
    def _is_continuation_text(self, text_content: str, bbox_data: Dict[str, float]) -> bool:
        """前ページからの継続テキストかどうかを判定"""
        if not text_content:
            return False
        
        # ページ上部に位置するかチェック
        y1 = bbox_data.get('y1', 0)
        y2 = bbox_data.get('y2', 0)
        avg_y = (y1 + y2) / 2
        is_top_area = avg_y > 700  # ページ上部約17%
        
        if not is_top_area:
            return False
        
        text_strip = text_content.strip()
        
        # 継続テキストのパターン（リスト項目は除外）
        continuation_patterns = [
            # 助詞や接続詞で始まる（ただしリスト番号は除外）
            r'^[わらずものことためにはでがをとも]',
            r'^[、。，．]',  # 句読点で始まる（OCRエラーの可能性）
            
            # 明らかに文の途中
            r'^らず[、，]',
            r'^ること[。、]',
            r'^もの[。、]',
            
            # 番号付きリストは除外（list_itemとして処理されるべき）
            # r'^[(（]\s*(?:1[0-9]|[2-9][0-9])\s*[)）]',  # これは削除
        ]
        
        import re
        
        for pattern in continuation_patterns:
            if re.match(pattern, text_strip):
                logger.info(f"Detected continuation text: '{text_content[:50]}...'")
                return True
        
        # 小文字で始まり、かつページ上部にある場合
        if text_strip and text_strip[0].islower():
            logger.info(f"Detected continuation text (lowercase start): '{text_content[:50]}...'")
            return True
        
        return False
    
    def _is_section_header_text(self, text_content: str) -> bool:
        """テキスト内容がセクション見出しかどうかを判定"""
        if not text_content or len(text_content) > 150:
            return False
        
        text_strip = text_content.strip()
        
        # 除外パターン（これらはセクション見出しではない）
        exclude_patterns = [
            r'^TEXT\s+#\d+',                   # TEXT #1, TEXT #2など（デバッグ用ラベル）
            r'^SECTION_HEADER\s+#\d+',         # SECTION_HEADER #4など
        ]
        
        import re
        
        # 除外パターンをチェック
        for pattern in exclude_patterns:
            if re.match(pattern, text_strip, re.IGNORECASE):
                return False
        
        # セクション見出しのパターン
        section_patterns = [
            # 日本語の条項パターン
            r'^第\s*[0-9０-９]+\s*条',         # 第1条、第２条
            r'^第\s*[0-9０-９]+\s*章',         # 第1章、第２章
            r'^第\s*[0-9０-９]+\s*節',         # 第1節
            r'^第\s*[0-9０-９]+\s*項',         # 第1項
            # r'^[(（]\s*[0-9０-９]+\s*[)）]',   # (1) （2）などはリスト項目として扱うため除外
            r'^[【\[]\s*.+\s*[】\]]',          # 【見出し】 [見出し]
            
            # 英語のセクションパターン
            r'^chapter\s+\d+',                 # Chapter 1
            r'^section\s+\d+',                 # Section 1
            r'^article\s+\d+',                 # Article 1
            r'^\d+\.\d+\s+',                   # 1.1 1.2 など
            
            # 括弧で囲まれた見出し（短いもののみ）
            r'^[（(][^)）]{1,30}[)）]$',       # (短い見出し内容)
        ]
        
        for pattern in section_patterns:
            if re.match(pattern, text_strip, re.IGNORECASE):
                logger.info(f"Detected section header pattern: '{text_content[:50]}...'")
                return True
        
        # 短いテキストで全て大文字の場合も見出しの可能性
        if len(text_strip) < 50 and text_strip.isupper():
            logger.info(f"Detected uppercase section header: '{text_content}'")
            return True
        
        return False
    
    def _is_list_item_text(self, text_content: str) -> bool:
        """テキスト内容がリスト項目かどうかを判定"""
        if not text_content:
            return False
        
        text_strip = text_content.strip()
        
        # リスト項目のパターン
        list_patterns = [
            # 日本語の箇条書きパターン
            r'^[・·•▪▫◆◇■□★☆○●◎◉]\s+',     # 各種記号付きリスト
            r'^[-－‐―ー]\s+',                    # ハイフン、ダッシュ
            r'^[(（]\s*[0-9０-９]+\s*[)）]',     # (1) （２）形式の番号付きリスト
            r'^[①-⑳]\s+',                       # 丸数字
            r'^[ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ]\s*[\.．)）]\s*',  # ローマ数字小文字
            r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]\s*[\.．)）]\s*',  # ローマ数字大文字
            r'^[ａ-ｚ]\s*[\.．)）]\s*',            # 全角英字小文字
            r'^[Ａ-Ｚ]\s*[\.．)）]\s*',            # 全角英字大文字
            
            # 英語のリストパターン  
            r'^[a-z]\s*[\.)\]]\s+',              # a. b. c) d]
            r'^[A-Z]\s*[\.)\]]\s+',              # A. B. C) D]
            r'^[ivxlcdm]+\s*[\.)\]]\s+',         # i. ii. iii) iv]（ローマ数字）
            r'^[IVXLCDM]+\s*[\.)\]]\s+',         # I. II. III) IV]
            
            # 特殊なリストマーカー
            r'^[→⇒▶▷]\s+',                      # 矢印
            r'^[※＊]\s+',                        # 注記マーク
            
            # インデントされた番号付きリスト（セクション見出しとは異なるパターン）
            r'^\s+[・·•▪▫◆◇■□★☆○●◎◉]\s+',    # インデント付き記号
            r'^\s+[-－‐―ー]\s+',                 # インデント付きハイフン
        ]
        
        import re
        
        for pattern in list_patterns:
            if re.match(pattern, text_content):
                logger.info(f"Detected list item pattern: '{text_content[:50]}...'")
                return True
        
        # 箇条書きの内容の特徴（短めで、文頭に特定のパターンがある）
        # 「〜すること」「〜である」などで終わる短い文
        if len(text_strip) < 200:
            # 動詞の連用形や体言止めで終わる
            ending_patterns = [
                r'こと[。、]?$',
                r'もの[。、]?$', 
                r'ため[。、]?$',
                r'必要がある[。、]?$',
                r'ものとする[。、]?$',
                r'場合[。、]?$',
                r'す\s*ること[。、]?$',  # 「〜すること」パターンを追加（スペース対応）
                r'る\s*こと[。、]?$',    # 「〜ること」パターン（スペース対応）
            ]
            
            for pattern in ending_patterns:
                if re.search(pattern, text_strip):
                    # 追加条件：先頭にスペースがある、または1行目でない位置にある
                    if text_content.startswith(' ') or text_content.startswith('　'):
                        logger.info(f"Detected list item by ending pattern with indent: '{text_content[:50]}...'")
                        return True
                    # 前後の要素を見て判断する必要があるが、ここでは簡易判定
                    logger.debug(f"Potential list item by ending pattern: '{text_content[:30]}...'")
                    # 単独では判定しない（誤検出防止）
        
        return False
    
    def _calculate_list_indent_level(self, bbox_data: Dict[str, float]) -> int:
        """リスト項目のインデントレベルを計算"""
        x1 = bbox_data.get('x1', 0)
        
        # 基準インデント値を定義（ポイント単位）
        base_indent = 106  # 通常のリスト項目の左マージン
        indent_step = 30   # 階層ごとのインデント幅
        
        # インデント量からレベルを計算
        if x1 <= base_indent + 5:  # 5ポイントの誤差を許容
            return 0  # レベル0（親リスト）
        elif x1 <= base_indent + indent_step + 5:
            return 1  # レベル1（子リスト）
        elif x1 <= base_indent + indent_step * 2 + 5:
            return 2  # レベル2（孫リスト）
        else:
            return 3  # レベル3以上
    
    def _analyze_page_indent_structure(self, document, page_num: int) -> Dict:
        """ページ全体のインデント構造を分析"""
        try:
            x_positions = []
            element_types = []
            
            # main_textから要素を収集
            if hasattr(document, 'main_text') and len(document.main_text) > page_num:
                main_text_page = document.main_text[page_num]
                for text_item in main_text_page:
                    if hasattr(text_item, 'prov') and text_item.prov:
                        prov_item = text_item.prov[0]
                        if hasattr(prov_item, 'bbox') and prov_item.bbox:
                            bbox_list = prov_item.bbox
                            if isinstance(bbox_list, list) and len(bbox_list) == 4:
                                x1 = float(bbox_list[0])
                                x_positions.append(x1)
                                
                                # テキスト内容からタイプを推定
                                text_content = clean_docling_text(str(text_item.text).strip()) if hasattr(text_item, 'text') else ""
                                if text_content.startswith('第') and '条' in text_content:
                                    element_types.append('article')
                                elif text_content.startswith('(') or text_content.startswith('（'):
                                    element_types.append('list_item')
                                else:
                                    element_types.append('text')
            
            # インデントレベルを動的に算出
            unique_x = sorted(set(x_positions))
            indent_levels = {}
            
            if len(unique_x) >= 1:
                base_indent = min(unique_x)  # 最小インデント = レベル0
                indent_levels[0] = base_indent
                
                for i, x in enumerate(unique_x[1:], 1):
                    indent_levels[i] = x
            
            analysis = {
                'base_indent': base_indent if unique_x else 80,
                'indent_levels': indent_levels,
                'x_positions': x_positions,
                'unique_indents': unique_x
            }
            
            logger.info(f"Page {page_num + 1} indent analysis: base={analysis['base_indent']:.1f}, levels={len(indent_levels)}")
            return analysis
            
        except Exception as e:
            logger.warning(f"Error analyzing page indent structure: {e}")
            # フォールバック: 固定値を返す
            return {
                'base_indent': 80,
                'indent_levels': {0: 80, 1: 110, 2: 140},
                'x_positions': [],
                'unique_indents': []
            }
    
    def _calculate_dynamic_list_indent_level(self, bbox_data: Dict[str, float]) -> int:
        """動的インデント分析に基づくリスト階層レベルの計算"""
        if not hasattr(self, 'page_indent_analysis'):
            return self._calculate_list_indent_level(bbox_data)  # フォールバック
            
        x1 = bbox_data.get('x1', 0)
        analysis = self.page_indent_analysis
        indent_levels = analysis.get('indent_levels', {})
        
        # 最も近いインデントレベルを見つける
        min_distance = float('inf')
        best_level = 0
        
        for level, indent_x in indent_levels.items():
            distance = abs(x1 - indent_x)
            if distance < min_distance and distance <= 10:  # 10ポイント以内の誤差を許容
                min_distance = distance
                best_level = level
        
        return best_level
    
    def _extract_bbox_from_ccs_element(self, element, page_height: float) -> Dict[str, float]:
        """CCS要素からバウンディングボックスを抽出"""
        try:
            # 方法1: 直接bbox属性
            if hasattr(element, 'bbox') and element.bbox:
                bbox = element.bbox
                if hasattr(bbox, 'l') and hasattr(bbox, 't') and hasattr(bbox, 'r') and hasattr(bbox, 'b'):
                    y1 = float(page_height - bbox.t)
                    y2 = float(page_height - bbox.b)
                    if y1 > y2:
                        y1, y2 = y2, y1
                    
                    return {
                        "x1": float(bbox.l),
                        "y1": y1,
                        "x2": float(bbox.r),
                        "y2": y2
                    }
            
            # 方法2: prov経由
            if hasattr(element, 'prov') and element.prov and len(element.prov) > 0:
                for prov_item in element.prov:
                    if hasattr(prov_item, 'bbox') and prov_item.bbox:
                        bbox = prov_item.bbox
                        if hasattr(bbox, 'l') and hasattr(bbox, 't') and hasattr(bbox, 'r') and hasattr(bbox, 'b'):
                            y1 = float(page_height - bbox.t)
                            y2 = float(page_height - bbox.b)
                            if y1 > y2:
                                y1, y2 = y2, y1
                            
                            return {
                                "x1": float(bbox.l),
                                "y1": y1,
                                "x2": float(bbox.r),
                                "y2": y2
                            }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error extracting bbox from CCS element: {e}")
            return None
    
    def _extract_text_from_ccs_element(self, element) -> str:
        """CCS要素からテキストを抽出"""
        try:
            # 方法1: text属性
            if hasattr(element, 'text') and element.text:
                return clean_docling_text(str(element.text).strip())

            # 方法2: content属性
            if hasattr(element, 'content') and element.content:
                return clean_docling_text(str(element.content).strip())

            # 方法3: prov経由
            if hasattr(element, 'prov') and element.prov:
                text_parts = []
                for prov_item in element.prov:
                    if hasattr(prov_item, 'text') and prov_item.text:
                        text_parts.append(clean_docling_text(str(prov_item.text).strip()))
                if text_parts:
                    return " ".join(text_parts)

            return ""

        except Exception as e:
            logger.warning(f"Error extracting text from CCS element: {e}")
            return ""
    
    def _determine_layout_type(self, element_type_name: str) -> str:
        """要素タイプ名からレイアウトタイプを決定"""
        element_type_name = element_type_name.lower()
        
        if 'figure' in element_type_name or 'image' in element_type_name or 'picture' in element_type_name:
            return "figure"
        elif 'table' in element_type_name:
            return "table" 
        elif 'title' in element_type_name or 'heading' in element_type_name:
            return "title"
        else:
            return "text"
    
    def _is_element_on_page(self, element, target_page: int) -> bool:
        """要素が指定されたページにあるかチェック"""
        try:
            # prov情報からページ番号を取得
            if hasattr(element, 'prov') and element.prov:
                for prov_item in element.prov:
                    if hasattr(prov_item, 'page') and prov_item.page == target_page:
                        return True
            return False
        except Exception as e:
            logger.warning(f"Error checking page for element: {e}")
            return False