"""
Hierarchy Converter Module
semantic_hierarchyをフロントエンド用の階層構造に変換
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def clean_docling_text(text: str) -> str:
    """Doclingが生成する非標準テキストをクリーンアップ"""
    if not text:
        return ""
    text = re.sub(r'<non-compliant-utf8-text>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


class HierarchyConverter:
    """semantic_hierarchyをフロントエンド用の階層構造に変換"""
    
    def __init__(self):
        self.logger = logger
        self.global_element_counter = 0  # 文書全体での通し番号カウンター
    
    def convert_to_frontend_hierarchy(
        self, 
        metadata_ext: Dict[str, Any],
        metadata: Dict[str, Any],
        docling_document=None
    ) -> Dict[str, Any]:
        """
        metadata_ext.jsonのsemantic_hierarchyを
        フロントエンド用の階層構造に変換
        
        Args:
            metadata_ext: 拡張メタデータ
            metadata: 基本メタデータ
            
        Returns:
            フロントエンド用の階層構造を含むメタデータ
        """
        try:
            # 文書処理開始時にカウンターをリセット
            self.global_element_counter = 0
            
            # 基本メタデータをコピー
            hierarchy_metadata = metadata.copy()
            
            # ページごとの階層構造を構築
            if "pages" in hierarchy_metadata:
                for page_idx, page_data in enumerate(hierarchy_metadata["pages"]):
                    if "elements" in page_data:
                        # semantic_hierarchyから階層関係を取得
                        semantic_hierarchy = self._get_page_semantic_hierarchy(
                            metadata_ext, 
                            page_idx + 1
                        )
                        
                        # PDF高さを取得（座標変換用）- metadataから正しい高さを取得
                        page_height = None
                        
                        # 1. 基本metadataから高さを取得（最優先）
                        if "dimensions" in metadata and "pdf_page" in metadata["dimensions"]:
                            page_height = metadata["dimensions"]["pdf_page"].get("height")
                        
                        # 2. 拡張metadataから取得（フォールバック）
                        if page_height is None and "dimensions" in metadata_ext and "pdf_page" in metadata_ext["dimensions"]:
                            page_height = metadata_ext["dimensions"]["pdf_page"].get("height")
                        
                        # 3. デフォルト値（最後の手段）
                        if page_height is None:
                            page_height = 842.4
                            logger.warning(f"Could not find PDF height in metadata, using default {page_height}")
                        else:
                            logger.info(f"Using PDF height: {page_height} for coordinate transformation")
                        
                        # フロントエンド用の階層構造に変換
                        hierarchical_elements = self._build_hierarchical_structure(
                            page_data["elements"],
                            semantic_hierarchy,
                            page_idx + 1,
                            page_height,
                            docling_document,
                            page_idx
                        )
                        
                        # 階層構造を追加し、従来のelementsを削除（データの重複回避）
                        page_data["hierarchical_elements"] = hierarchical_elements
                        page_data["has_hierarchy"] = True
                        
                        # elementsは不要なので削除（hierarchical_elementsに包含されている）
                        if "elements" in page_data:
                            del page_data["elements"]
            
            # 文書全体の階層サマリーを追加
            hierarchy_metadata["document_hierarchy"] = {
                "version": "1.0",
                "source": "semantic_hierarchy",
                "total_elements": len(metadata.get("pages", [{}])[0].get("elements", [])) if metadata.get("pages") else 0,
                "hierarchy_levels": self._count_hierarchy_levels(metadata_ext),
                "has_semantic_structure": True
            }
            
            return hierarchy_metadata
            
        except Exception as e:
            logger.error(f"Failed to convert hierarchy: {e}")
            return metadata
    
    def convert_page_to_hierarchy(
        self,
        page_layout: Dict[str, Any],
        page_number: int,
        metadata_ext: Dict[str, Any],
        docling_document=None
    ) -> Dict[str, Any]:
        """単一ページのelementsをhierarchical_elementsに変換"""
        try:
            logger.info(f"Converting page {page_number} elements to hierarchical structure")
            
            elements = page_layout.get("elements", [])
            if not elements:
                logger.warning(f"No elements found for page {page_number}")
                return page_layout
            
            # elementsをelement_idでインデックス化（table_infoを取得するため）
            elements_by_element_id = {}
            for elem in elements:
                element_id = elem.get("element_id")
                if element_id is not None:
                    elements_by_element_id[element_id] = elem
            
            # Semantic hierarchyを取得
            semantic_hierarchy = self._get_page_semantic_hierarchy(metadata_ext, page_number)
            
            # PDF高さを取得（座標変換用）- metadata_extから正しい高さを取得
            page_height = None
            
            # metadata_extから高さを取得
            if "dimensions" in metadata_ext and "pdf_page" in metadata_ext["dimensions"]:
                page_height = metadata_ext["dimensions"]["pdf_page"].get("height")
            
            # デフォルト値（最後の手段）
            if page_height is None:
                page_height = 842.4
                logger.warning(f"Could not find PDF height in metadata_ext, using default {page_height}")
            else:
                logger.info(f"Using PDF height: {page_height} for page {page_number} coordinate transformation")
            
            # 階層構造を構築
            page_idx = page_number - 1  # 0-indexed
            hierarchical_elements = self._build_hierarchical_structure(
                elements, semantic_hierarchy, page_number, page_height, docling_document, page_idx, elements_by_element_id
            )
            
            # 結果をpage_layoutに追加
            page_layout["hierarchical_elements"] = hierarchical_elements
            logger.info(f"Created {len(hierarchical_elements)} hierarchical elements for page {page_number}")
            
            return page_layout
            
        except Exception as e:
            logger.error(f"Failed to convert page {page_number} to hierarchy: {e}")
            return page_layout
    
    def _get_page_semantic_hierarchy(
        self, 
        metadata_ext: Dict[str, Any], 
        page_number: int
    ) -> List[Dict[str, Any]]:
        """特定ページのsemantic_hierarchyを取得"""
        try:
            pages_data = metadata_ext.get("pages_hierarchical", [])
            
            for page_data in pages_data:
                if page_data.get("page_number") == page_number:
                    return page_data.get("semantic_hierarchy", [])
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get semantic hierarchy for page {page_number}: {e}")
            return []
    
    def _build_hierarchical_structure(
        self,
        elements: List[Dict[str, Any]],
        semantic_hierarchy: List[Dict[str, Any]],
        page_number: int,
        page_height: float = 842.4,
        docling_document=None,
        page_idx: int = 0,
        elements_by_element_id: Dict[int, Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """要素を階層構造に変換"""
        try:
            # Docling生データから要素を取得（annotated.pngと同じ座標を使用）
            raw_docling_elements = []
            if docling_document and hasattr(docling_document, 'pages') and page_idx < len(docling_document.pages):
                try:
                    page_layout = docling_document.pages[page_idx]
                    if hasattr(page_layout, '_layout') and page_layout._layout:
                        logger.info(f"Using raw Docling layout data with {len(page_layout._layout)} elements")
                        for element in page_layout._layout:
                            if hasattr(element, 'bbox'):
                                bbox = element.bbox
                                from .utils import get_element_type
                                element_type = get_element_type(element)
                                raw_element = {
                                    "type": element_type,
                                    "bbox": {
                                        "x1": bbox.l,
                                        "y1": bbox.t,
                                        "x2": bbox.r,
                                        "y2": bbox.b
                                    },
                                    "text": clean_docling_text(getattr(element, 'text', '')),
                                    "is_raw_docling": True
                                }
                                raw_docling_elements.append(raw_element)
                                logger.debug(f"Raw Docling element: {element_type} at ({bbox.l:.1f}, {bbox.t:.1f})")
                except Exception as e:
                    logger.warning(f"Failed to extract raw Docling elements: {e}")
            
            # Raw Docling要素を優先使用、フォールバックとして処理済み要素を使用
            elements_to_process = raw_docling_elements if raw_docling_elements else elements
            logger.info(f"Processing {len(elements_to_process)} elements ({'raw Docling' if raw_docling_elements else 'processed metadata'})")
            
            # 要素をIDでインデックス化（ID衝突を避けるため、type付きの複合キーを使用）
            elements_by_id = {}
            element_id_map = {}  # 元のIDから新しいIDへのマッピング
            
            for idx, elem in enumerate(elements_to_process):
                element_id = elem.get("element_id", idx)
                element_type = elem.get("type", "unknown")
                
                # グローバルカウンターをインクリメント
                self.global_element_counter += 1
                
                # 統一ID形式（ID-番号）
                simple_id = f"ID-{self.global_element_counter}"
                
                elements_by_id[simple_id] = elem
                element_id_map[element_id] = element_id_map.get(element_id, [])
                element_id_map[element_id].append(simple_id)
            
            # semantic_hierarchyから親子関係を構築
            logger.info(f"Building parent-child relationships from {len(semantic_hierarchy)} semantic hierarchy items")
            logger.info(f"Available elements: {list(elements_by_id.keys())}")
            
            parent_child_map = self._build_parent_child_relationships(
                semantic_hierarchy,
                elements_by_id,
                element_id_map
            )
            
            logger.info(f"Parent-child map after semantic processing: {dict(parent_child_map)}")
            logger.info(f"Parents with children: {len([p for p, c in parent_child_map.items() if c])}")
            
            # 空間的な包含関係も考慮（bbox情報を使用）
            self._add_spatial_relationships(parent_child_map, elements_by_id)
            
            logger.info(f"Parent-child map after spatial processing: {dict(parent_child_map)}")
            logger.info(f"Final parents with children: {len([p for p, c in parent_child_map.items() if c])}")
            
            # フロントエンド用の階層構造を構築
            hierarchical_elements = []
            processed = set()
            
            for simple_id, element in elements_by_id.items():
                if simple_id in processed:
                    continue
                    
                # ルート要素を探す（親がない要素）
                if simple_id not in [child for children in parent_child_map.values() for child in children]:
                    tree_element = self._build_tree_element(
                        element,
                        simple_id,
                        parent_child_map,
                        elements_by_id,
                        processed,
                        page_number,
                        page_height,
                        elements_by_element_id
                    )
                    hierarchical_elements.append(tree_element)
            
            # 処理されなかった要素を追加（フラットな構造として）
            for simple_id, element in elements_by_id.items():
                if simple_id not in processed:
                    tree_element = self._convert_to_tree_element(
                        element, simple_id, page_number, None, page_height, elements_by_element_id
                    )
                    hierarchical_elements.append(tree_element)
                    processed.add(simple_id)
            
            return hierarchical_elements
            
        except Exception as e:
            logger.error(f"Failed to build hierarchical structure: {e}")
            # エラー時は元の要素をフラットな構造で返す
            return [
                self._convert_to_tree_element(elem, idx, page_number, None, 842.4, elements_by_element_id)
                for idx, elem in enumerate(elements)
            ]
    
    def _build_parent_child_relationships(
        self,
        semantic_hierarchy: List[Dict[str, Any]],
        elements_by_id: Dict[str, Dict[str, Any]],
        element_id_map: Dict[int, List[str]]
    ) -> Dict[str, List[str]]:
        """semantic_hierarchyから親子関係を構築"""
        parent_child_map = {}
        
        try:
            logger.info(f"Building parent-child from {len(semantic_hierarchy)} semantic items")
            if semantic_hierarchy:
                logger.info(f"First semantic item: {semantic_hierarchy[0]}")
            
            # semantic_levelに基づいて親子関係を推定
            sorted_hierarchy = sorted(
                semantic_hierarchy, 
                key=lambda x: (x.get("semantic_level", 999), x.get("element_id", 0))
            )
            
            logger.info(f"Sorted hierarchy levels: {[(item.get('element_id'), item.get('semantic_level')) for item in sorted_hierarchy[:5]]}")
            
            for i, item in enumerate(sorted_hierarchy):
                elem_id = item.get("element_id")
                if elem_id is None:
                    continue
                
                # semantic_hierarchyのelement_idに対応する複合キーを取得
                parent_keys = element_id_map.get(elem_id, [])
                if not parent_keys:
                    continue
                
                # 複数の要素が同じIDを持つ場合は、typeに基づいて適切な要素を選択
                element_type = item.get("type")
                parent_key = None
                for key in parent_keys:
                    if element_type and key.startswith(f"{element_type}_"):
                        parent_key = key
                        break
                if not parent_key and parent_keys:
                    parent_key = parent_keys[0]  # フォールバック
                
                if not parent_key:
                    continue
                
                level = item.get("semantic_level", 999)
                children = []
                
                # 次のレベルの要素を子要素として追加
                for j in range(i + 1, len(sorted_hierarchy)):
                    next_item = sorted_hierarchy[j]
                    next_level = next_item.get("semantic_level", 999)
                    next_id = next_item.get("element_id")
                    
                    if next_level > level:
                        # より深いレベルの要素は子要素候補
                        if next_level == level + 1:
                            # 直接の子要素の複合キーを取得
                            child_keys = element_id_map.get(next_id, [])
                            child_type = next_item.get("type")
                            child_key = None
                            for key in child_keys:
                                if child_type and key.startswith(f"{child_type}_"):
                                    child_key = key
                                    break
                            if not child_key and child_keys:
                                child_key = child_keys[0]
                            
                            if child_key:
                                children.append(child_key)
                    elif next_level <= level:
                        # 同じまたは上のレベルに戻ったら終了
                        break
                
                if children:
                    parent_child_map[parent_key] = children
            
            return parent_child_map
            
        except Exception as e:
            logger.error(f"Failed to build parent-child relationships: {e}")
            return {}
    
    def _add_spatial_relationships(
        self,
        parent_child_map: Dict[str, List[str]],
        elements_by_id: Dict[str, Dict[str, Any]]
    ):
        """空間的な包含関係を追加"""
        try:
            table_count = len([e for e in elements_by_id.values() if e.get("type") == "table"])
            table_cell_count = len([e for e in elements_by_id.values() if e.get("type") == "table_cell"])
            logger.info(f"Spatial relationship check: {table_count} tables, {table_cell_count} table_cells")
            
            for parent_key, parent_elem in elements_by_id.items():
                parent_bbox = parent_elem.get("bbox", {})
                if not parent_bbox:
                    continue
                
                # tableやlistの場合、空間的に含まれる要素を子要素とする
                if parent_elem.get("type") in ["table", "list"]:
                    logger.info(f"Processing spatial relationships for {parent_elem.get('type')} element {parent_key}")
                    children = parent_child_map.get(parent_key, [])
                    
                    for child_key, child_elem in elements_by_id.items():
                        if child_key == parent_key:
                            continue
                        
                        child_bbox = child_elem.get("bbox", {})
                        if not child_bbox:
                            continue
                        
                        # 空間的に含まれているかチェック
                        if self._is_contained(parent_bbox, child_bbox):
                            if child_elem.get("type") in ["table_cell", "list_item"]:
                                if child_key not in children:
                                    children.append(child_key)
                                    logger.info(f"Added spatial child: {child_elem.get('type')} {child_key} to {parent_elem.get('type')} {parent_key}")
                                    
                                    # 他の親からこの子要素を削除（空間的な関係を優先）
                                    for other_parent, other_children in parent_child_map.items():
                                        if other_parent != parent_key and child_key in other_children:
                                            other_children.remove(child_key)
                                            logger.info(f"Removed spatial child: {child_elem.get('type')} {child_key} from incorrect parent {other_parent}")
                            else:
                                logger.debug(f"Spatial child {child_key} ({child_elem.get('type')}) not eligible for {parent_key}")
                        else:
                            if child_elem.get("type") == "table_cell":
                                logger.debug(f"table_cell {child_key} not spatially contained in table {parent_key}")
                    
                    if children:
                        parent_child_map[parent_key] = children
                        
        except Exception as e:
            logger.error(f"Failed to add spatial relationships: {e}")
    
    def _is_contained(self, parent_bbox: Dict, child_bbox: Dict) -> bool:
        """子要素が親要素に空間的に含まれているかチェック"""
        try:
            p_x1 = parent_bbox.get("x1", parent_bbox.get("x", 0))
            p_y1 = parent_bbox.get("y1", parent_bbox.get("y", 0))
            p_x2 = parent_bbox.get("x2", p_x1 + parent_bbox.get("width", 0))
            p_y2 = parent_bbox.get("y2", p_y1 + parent_bbox.get("height", 0))
            
            c_x1 = child_bbox.get("x1", child_bbox.get("x", 0))
            c_y1 = child_bbox.get("y1", child_bbox.get("y", 0))
            c_x2 = child_bbox.get("x2", c_x1 + child_bbox.get("width", 0))
            c_y2 = child_bbox.get("y2", c_y1 + child_bbox.get("height", 0))
            
            # 許容誤差を考慮（5ピクセル）
            margin = 5
            return (
                c_x1 >= p_x1 - margin and
                c_y1 >= p_y1 - margin and
                c_x2 <= p_x2 + margin and
                c_y2 <= p_y2 + margin
            )
            
        except:
            return False
    
    def _build_tree_element(
        self,
        element: Dict[str, Any],
        simple_id: str,
        parent_child_map: Dict[str, List[str]],
        elements_by_id: Dict[str, Dict[str, Any]],
        processed: set,
        page_number: int,
        page_height: float = 842.4,
        elements_by_element_id: Dict[int, Dict[str, Any]] = None,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """ツリー要素を再帰的に構築"""
        
        # フロントエンド用の要素を作成
        tree_element = self._convert_to_tree_element(
            element, simple_id, page_number, parent_id, page_height, elements_by_element_id
        )
        processed.add(simple_id)
        
        # 子要素を追加
        children_keys = parent_child_map.get(simple_id, [])
        children = []
        
        for child_key in children_keys:
            if child_key in elements_by_id and child_key not in processed:
                child_element = self._build_tree_element(
                    elements_by_id[child_key],
                    child_key,
                    parent_child_map,
                    elements_by_id,
                    processed,
                    page_number,
                    page_height,
                    elements_by_element_id,
                    tree_element["id"]  # 親IDを設定
                )
                children.append(child_element)
        
        tree_element["children"] = children
        
        return tree_element
    
    def _convert_to_tree_element(
        self,
        element: Dict[str, Any],
        simple_id: str,
        page_number: int,
        parent_id: Optional[str] = None,
        page_height: float = 842.4,
        elements_by_element_id: Dict[int, Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """要素をフロントエンドのツリー形式に変換"""
        
        bbox = element.get("bbox", {})
        element_type = element.get("type", "unknown")
        
        logger.info(f"Converting element {simple_id} ({element_type}) with page_height={page_height}")
        
        # 座標変換（annotated.pngと同じ変換を使用）
        x1 = bbox.get("x1", bbox.get("x", 0))
        y1_input = bbox.get("y1", bbox.get("y", 0))
        x2 = bbox.get("x2", x1 + bbox.get("width", 100))
        y2_input = bbox.get("y2", y1_input + bbox.get("height", 20))
        
        # 要素タイプに応じた座標変換
        
        if element_type == "figure":
            # Figure要素は元のy1座標を直接使用（変換不要）
            y1_image = y1_input
            y2_image = y2_input
            logger.debug(f"Figure direct coordinates: y1={y1_input:.1f}, y2={y2_input:.1f} (no conversion)")
        else:
            # その他の要素はPDF→画像座標変換を適用
            y1_image = page_height - y2_input  # PDFのy2が画像のy1になる
            y2_image = page_height - y1_input  # PDFのy1が画像のy2になる
            logger.debug(f"Standard conversion for {element_type}: PDF({y1_input:.1f}-{y2_input:.1f}) → Image({y1_image:.1f}-{y2_image:.1f}) using page_height={page_height}")
        
        # フロントエンド用のIDはシンプルIDをそのまま使用
        frontend_id = simple_id
        
        tree_element = {
            "id": frontend_id,
            "type": element.get("type", "text"),
            "x": x1,
            "y": y1_image,
            "width": x2 - x1,
            "height": y2_image - y1_image,
            "bbox": {
                "x1": x1,
                "y1": y1_image,
                "x2": x2,
                "y2": y2_image
            },
            "children": []
        }
        
        # 親IDがある場合は設定
        if parent_id:
            tree_element["parent_id"] = parent_id
        
        # テキスト情報も含める（オプション）
        if "text" in element:
            tree_element["text"] = element["text"]
        
        # table_cell要素の場合、元のelementsからtable_infoを取得
        if element_type == "table_cell" and elements_by_element_id:
            # 元のelement_idを取得（raw Doclingの場合はmappingが必要）
            original_element_id = element.get("element_id")
            if original_element_id is not None and original_element_id in elements_by_element_id:
                original_element = elements_by_element_id[original_element_id]
                table_info = original_element.get("table_info")
                if table_info:
                    tree_element["table_info"] = table_info
                    logger.info(f"Added table_info to table_cell {simple_id}: {table_info}")
        
        return tree_element
    
    def _count_hierarchy_levels(self, metadata_ext: Dict[str, Any]) -> int:
        """階層の深さをカウント"""
        try:
            max_level = 0
            
            for page_data in metadata_ext.get("pages_hierarchical", []):
                for item in page_data.get("semantic_hierarchy", []):
                    level = item.get("semantic_level", 0)
                    max_level = max(max_level, level)
            
            return max_level
            
        except:
            return 0
    
    def save_hierarchy_metadata(
        self,
        hierarchy_metadata: Dict[str, Any],
        output_dir: Path
    ) -> Path:
        """階層構造メタデータをファイルに保存"""
        try:
            output_file = output_dir / "metadata_hierarchy.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(hierarchy_metadata, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved hierarchy metadata to {output_file}")
            return output_file
            
        except Exception as e:
            logger.error(f"Failed to save hierarchy metadata: {e}")
            raise