import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class HierarchicalExtractor:
    """階層構造とメタデータ拡張機能を提供するクラス"""
    
    def __init__(self):
        pass
    
    def create_extended_metadata(
        self, 
        document, 
        output_dir: Path, 
        original_metadata: Dict[str, Any],
        original_filename: str,
        single_page: Optional[int] = None
    ) -> Dict[str, Any]:
        """metadata_ext.jsonを作成"""
        logger.info("Creating extended metadata with hierarchical structure")
        
        try:
            # 1. 基本情報をコピー
            extended_metadata = {
                "document_name": original_filename,
                "processing_timestamp": original_metadata.get("processing_timestamp"),
                "total_pages": original_metadata.get("total_pages", 0),
                "total_elements": original_metadata.get("total_elements", 0),
                "processing_mode": original_metadata.get("processing_mode", "docling"),
                
                # 2. 拡張情報
                "extended_features": {
                    "hierarchical_structure": True,
                    "complete_image_paths": True,
                    "spatial_relationships": True,
                    "logical_ordering": True
                },
                
                # 3. 完全な画像パス情報
                "image_collections": self._collect_all_image_paths(output_dir),
                
                # 4. 階層構造化されたページデータ
                "pages_hierarchical": [],
                
                # 5. 文書全体の階層構造分析
                "document_structure": self._analyze_document_structure(document, original_metadata),
                
                # 6. 要素間関係マップ
                "element_relationships": {}
            }
            
            # 各ページの階層構造を構築（single_pageが指定された場合は該当ページのみ）
            pages_to_process = original_metadata.get("pages", [])
            if single_page is not None:
                # single_pageが指定された場合は該当ページのみ処理
                pages_to_process = [page_data for page_data in pages_to_process 
                                  if page_data.get("page_number") == single_page + 1]
                logger.info(f"Processing single page: {single_page + 1}")
            
            for page_data in pages_to_process:
                page_num = page_data.get("page_number", 1)
                hierarchical_page = self._create_hierarchical_page_data(
                    document, page_data, page_num, output_dir
                )
                extended_metadata["pages_hierarchical"].append(hierarchical_page)
            
            # 要素間関係を分析
            extended_metadata["element_relationships"] = self._analyze_element_relationships(
                extended_metadata["pages_hierarchical"]
            )
            
            logger.info(f"Extended metadata created with {len(extended_metadata['pages_hierarchical'])} hierarchical pages")
            return extended_metadata
            
        except Exception as e:
            logger.error(f"Failed to create extended metadata: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
    
    def _collect_all_image_paths(self, output_dir: Path) -> Dict[str, Any]:
        """画像ディレクトリから全画像パスを収集"""
        try:
            images_dir = output_dir / "images"
            if not images_dir.exists():
                logger.warning(f"Images directory not found: {images_dir}")
                return {"total_images": 0, "by_page": {}, "by_type": {}}
            
            image_files = list(images_dir.glob("*.png")) + list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.jpeg"))
            
            # ページ別に分類
            by_page = {}
            by_type = {"full": [], "annotated": [], "other": []}
            
            for image_file in image_files:
                relative_path = f"images/{image_file.name}"
                
                # ページ番号を抽出
                if "page_" in image_file.name:
                    try:
                        page_part = image_file.name.split("page_")[1]
                        page_num = int(page_part.split("_")[0])
                        
                        if page_num not in by_page:
                            by_page[page_num] = {"full": None, "annotated": None, "other": []}
                        
                        if "annotated" in image_file.name:
                            by_page[page_num]["annotated"] = relative_path
                            by_type["annotated"].append(relative_path)
                        elif "full" in image_file.name:
                            by_page[page_num]["full"] = relative_path
                            by_type["full"].append(relative_path)
                        else:
                            by_page[page_num]["other"].append(relative_path)
                            by_type["other"].append(relative_path)
                    except (ValueError, IndexError):
                        by_type["other"].append(relative_path)
                else:
                    by_type["other"].append(relative_path)
            
            return {
                "total_images": len(image_files),
                "by_page": by_page,
                "by_type": by_type,
                "all_paths": [f"images/{f.name}" for f in image_files]
            }
            
        except Exception as e:
            logger.error(f"Failed to collect image paths: {e}")
            return {"total_images": 0, "by_page": {}, "by_type": {}, "error": str(e)}
    
    def _analyze_document_structure(self, document, original_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """文書全体の構造を分析"""
        try:
            structure_analysis = {
                "total_pages": original_metadata.get("total_pages", 0),
                "element_type_distribution": {},
                "page_complexity": [],
                "logical_flow": [],
                "sections_detected": []
            }
            
            # 要素タイプの分布を計算
            all_elements = []
            for page_data in original_metadata.get("pages", []):
                page_elements = page_data.get("elements", [])
                all_elements.extend(page_elements)
                
                # ページ複雑度を計算
                page_complexity = {
                    "page_number": page_data.get("page_number"),
                    "element_count": len(page_elements),
                    "element_types": list(set(el.get("type") for el in page_elements)),
                    "has_tables": any(el.get("type") == "table" for el in page_elements),
                    "has_figures": any(el.get("type") == "figure" for el in page_elements)
                }
                structure_analysis["page_complexity"].append(page_complexity)
            
            # 要素タイプ分布
            for element in all_elements:
                element_type = element.get("type", "unknown")
                structure_analysis["element_type_distribution"][element_type] = \
                    structure_analysis["element_type_distribution"].get(element_type, 0) + 1
            
            # 論理的フローの推定（見出し要素を基に）
            heading_elements = [el for el in all_elements if el.get("type") in ["title", "heading"]]
            structure_analysis["logical_flow"] = self._extract_logical_flow(heading_elements)
            
            return structure_analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze document structure: {e}")
            return {"error": str(e)}
    
    def _extract_logical_flow(self, heading_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """見出し要素から論理的フローを抽出"""
        try:
            logical_flow = []
            
            for i, heading in enumerate(heading_elements):
                flow_item = {
                    "sequence": i + 1,
                    "type": heading.get("type"),
                    "text": heading.get("text", ""),
                    "position": heading.get("bbox", {}),
                    "estimated_level": self._estimate_heading_level(heading)
                }
                logical_flow.append(flow_item)
            
            return logical_flow
            
        except Exception as e:
            logger.error(f"Failed to extract logical flow: {e}")
            return []
    
    def _estimate_heading_level(self, heading: Dict[str, Any]) -> int:
        """見出しのレベルを推定"""
        # フォントサイズや位置から見出しレベルを推定
        # 簡単な実装例
        if heading.get("type") == "title":
            return 1
        elif heading.get("type") == "heading":
            return 2
        else:
            return 3
    
    def _create_hierarchical_page_data(
        self, 
        document, 
        page_data: Dict[str, Any], 
        page_num: int, 
        output_dir: Path
    ) -> Dict[str, Any]:
        """ページデータの階層構造版を作成"""
        try:
            page_number = page_data.get("page_number", page_num)
            elements = page_data.get("elements", [])
            
            hierarchical_page = {
                "page_number": page_number,
                
                # 基本ファイル情報
                "files": {
                    "layout": page_data.get("layout_file"),
                    "text": page_data.get("text_file"),
                    "images": self._get_page_image_info(page_number, output_dir)
                },
                
                # テキスト情報
                "text_content": page_data.get("text_content", ""),
                
                # 1. Doclingの論理的順序を活用
                "logical_ordering": self._extract_logical_ordering(elements),
                
                # 2. 空間的位置関係から階層を推定
                "spatial_hierarchy": self._infer_spatial_hierarchy(elements),
                
                # 3. 要素タイプから意味的階層を構築
                "semantic_hierarchy": self._build_semantic_hierarchy(elements),
                
                # 元の要素データ（参照用）
                "original_elements": elements,
                
                # ページ統計
                "page_statistics": {
                    "total_elements": len(elements),
                    "element_types": list(set(el.get("type") for el in elements)),
                    "spatial_bounds": self._calculate_page_bounds(elements)
                }
            }
            
            return hierarchical_page
            
        except Exception as e:
            logger.error(f"Failed to create hierarchical page data for page {page_num}: {e}")
            return {
                "page_number": page_num,
                "error": str(e),
                "files": {"layout": None, "text": None, "images": {}},
                "logical_ordering": [],
                "spatial_hierarchy": [],
                "semantic_hierarchy": [],
                "original_elements": []
            }
    
    def _get_page_image_info(self, page_number: int, output_dir: Path) -> Dict[str, Any]:
        """ページの画像情報を取得"""
        try:
            images_dir = output_dir / "images"
            image_info = {
                "full_image": None,
                "annotated_image": None,
                "thumbnails": [],
                "other": []
            }
            
            if images_dir.exists():
                # ページ番号に対応する画像を検索
                for image_file in images_dir.glob(f"page_{page_number}_*.png"):
                    relative_path = f"images/{image_file.name}"
                    
                    if "annotated" in image_file.name:
                        image_info["annotated_image"] = relative_path
                    elif "full" in image_file.name:
                        image_info["full_image"] = relative_path
                    elif "thumb" in image_file.name:
                        image_info["thumbnails"].append(relative_path)
                    else:
                        image_info["other"].append(relative_path)
            
            return image_info
            
        except Exception as e:
            logger.error(f"Failed to get page image info for page {page_number}: {e}")
            return {"error": str(e)}
    
    def _extract_logical_ordering(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Doclingの論理的順序を活用"""
        try:
            logical_elements = []
            
            for i, element in enumerate(elements):
                logical_element = {
                    "logical_index": i,
                    "element_id": element.get("element_id"),
                    "type": element.get("type"),
                    "text": element.get("text", ""),
                    "reading_order": i + 1,  # 読み順
                    "bbox": element.get("bbox", {}),
                    "confidence": self._calculate_reading_order_confidence(element, elements)
                }
                logical_elements.append(logical_element)
            
            return logical_elements
            
        except Exception as e:
            logger.error(f"Failed to extract logical ordering: {e}")
            return []
    
    def _infer_spatial_hierarchy(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """空間的位置関係から階層を推定"""
        try:
            spatial_hierarchy = []
            
            for element in elements:
                bbox = element.get("bbox", {})
                if not bbox:
                    continue
                
                # 空間的に含まれる子要素を検索
                children = self._find_spatially_contained_elements(element, elements)
                
                # 空間的な親要素を検索
                parent = self._find_spatial_parent(element, elements)
                
                spatial_element = {
                    "element_id": element.get("element_id"),
                    "type": element.get("type"),
                    "bbox": bbox,
                    "spatial_parent": parent.get("element_id") if parent else None,
                    "spatial_children": [child.get("element_id") for child in children],
                    "spatial_level": self._calculate_spatial_level(element, elements),
                    "position_metrics": {
                        "area": self._calculate_bbox_area(bbox),
                        "center": self._calculate_bbox_center(bbox),
                        "aspect_ratio": self._calculate_aspect_ratio(bbox)
                    }
                }
                spatial_hierarchy.append(spatial_element)
            
            return spatial_hierarchy
            
        except Exception as e:
            logger.error(f"Failed to infer spatial hierarchy: {e}")
            return []
    
    def _build_semantic_hierarchy(self, elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """要素タイプから意味的階層を構築"""
        try:
            # 要素タイプの重要度マッピング
            type_hierarchy = {
                "title": 1,
                "heading": 2,
                "text": 3,
                "list": 3,
                "table": 2,
                "figure": 2,
                "table_cell": 4
            }
            
            semantic_hierarchy = []
            
            for element in elements:
                element_type = element.get("type", "unknown")
                semantic_level = type_hierarchy.get(element_type, 5)
                
                semantic_element = {
                    "element_id": element.get("element_id"),
                    "type": element_type,
                    "semantic_level": semantic_level,
                    "semantic_role": self._determine_semantic_role(element),
                    "context_elements": self._find_context_elements(element, elements),
                    "importance_score": self._calculate_importance_score(element, elements)
                }
                semantic_hierarchy.append(semantic_element)
            
            # 意味的レベルでソート
            semantic_hierarchy.sort(key=lambda x: (x["semantic_level"], x["element_id"]))
            
            return semantic_hierarchy
            
        except Exception as e:
            logger.error(f"Failed to build semantic hierarchy: {e}")
            return []
    
    def _find_spatially_contained_elements(self, parent_element: Dict[str, Any], all_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """空間的に含まれる子要素を検索"""
        try:
            parent_bbox = parent_element.get("bbox", {})
            if not parent_bbox:
                return []
            
            children = []
            for element in all_elements:
                if element.get("element_id") == parent_element.get("element_id"):
                    continue
                
                element_bbox = element.get("bbox", {})
                if not element_bbox:
                    continue
                
                # 含有関係をチェック
                if self._is_bbox_contained(element_bbox, parent_bbox):
                    children.append(element)
            
            return children
            
        except Exception as e:
            logger.error(f"Failed to find spatially contained elements: {e}")
            return []
    
    def _find_spatial_parent(self, child_element: Dict[str, Any], all_elements: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """空間的な親要素を検索"""
        try:
            child_bbox = child_element.get("bbox", {})
            if not child_bbox:
                return None
            
            potential_parents = []
            for element in all_elements:
                if element.get("element_id") == child_element.get("element_id"):
                    continue
                
                element_bbox = element.get("bbox", {})
                if not element_bbox:
                    continue
                
                # 含有関係をチェック
                if self._is_bbox_contained(child_bbox, element_bbox):
                    potential_parents.append(element)
            
            # 最小の親要素を選択（最も小さい包含要素）
            if potential_parents:
                return min(potential_parents, key=lambda x: self._calculate_bbox_area(x.get("bbox", {})))
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to find spatial parent: {e}")
            return None
    
    def _is_bbox_contained(self, inner_bbox: Dict[str, Any], outer_bbox: Dict[str, Any]) -> bool:
        """bboxが他のbboxに含まれているかチェック"""
        try:
            return (
                inner_bbox.get("x1", 0) >= outer_bbox.get("x1", 0) and
                inner_bbox.get("y1", 0) >= outer_bbox.get("y1", 0) and
                inner_bbox.get("x2", 0) <= outer_bbox.get("x2", 0) and
                inner_bbox.get("y2", 0) <= outer_bbox.get("y2", 0)
            )
        except:
            return False
    
    def _calculate_bbox_area(self, bbox: Dict[str, Any]) -> float:
        """bboxの面積を計算"""
        try:
            width = bbox.get("x2", 0) - bbox.get("x1", 0)
            height = bbox.get("y2", 0) - bbox.get("y1", 0)
            return max(0, width * height)
        except:
            return 0
    
    def _calculate_bbox_center(self, bbox: Dict[str, Any]) -> Tuple[float, float]:
        """bboxの中心座標を計算"""
        try:
            center_x = (bbox.get("x1", 0) + bbox.get("x2", 0)) / 2
            center_y = (bbox.get("y1", 0) + bbox.get("y2", 0)) / 2
            return (center_x, center_y)
        except:
            return (0, 0)
    
    def _calculate_aspect_ratio(self, bbox: Dict[str, Any]) -> float:
        """bboxのアスペクト比を計算"""
        try:
            width = bbox.get("x2", 0) - bbox.get("x1", 0)
            height = bbox.get("y2", 0) - bbox.get("y1", 0)
            return width / height if height > 0 else 0
        except:
            return 0
    
    def _calculate_spatial_level(self, element: Dict[str, Any], all_elements: List[Dict[str, Any]]) -> int:
        """空間的レベル（入れ子の深さ）を計算"""
        try:
            level = 0
            current_element = element
            
            while True:
                parent = self._find_spatial_parent(current_element, all_elements)
                if not parent:
                    break
                level += 1
                current_element = parent
                
                # 無限ループ防止
                if level > 10:
                    break
            
            return level
            
        except Exception as e:
            logger.error(f"Failed to calculate spatial level: {e}")
            return 0
    
    def _calculate_reading_order_confidence(self, element: Dict[str, Any], all_elements: List[Dict[str, Any]]) -> float:
        """読み順の信頼度を計算"""
        # 簡単な実装例
        return 0.8  # 固定値（実際にはより複雑な計算）
    
    def _determine_semantic_role(self, element: Dict[str, Any]) -> str:
        """要素の意味的役割を決定"""
        element_type = element.get("type", "unknown")
        text = element.get("text", "").lower()
        
        if element_type == "title":
            return "document_title"
        elif element_type == "heading":
            if any(keyword in text for keyword in ["章", "第", "section"]):
                return "section_heading"
            else:
                return "subsection_heading"
        elif element_type == "table":
            return "data_table"
        elif element_type == "figure":
            return "illustration"
        else:
            return "content"
    
    def _find_context_elements(self, element: Dict[str, Any], all_elements: List[Dict[str, Any]]) -> List[int]:
        """関連する文脈要素を検索"""
        # 近接する要素のIDを返す（簡単な実装）
        try:
            element_id = element.get("element_id", -1)
            context_ids = []
            
            for other in all_elements:
                other_id = other.get("element_id", -1)
                if abs(other_id - element_id) <= 2 and other_id != element_id:
                    context_ids.append(other_id)
            
            return context_ids
        except:
            return []
    
    def _calculate_importance_score(self, element: Dict[str, Any], all_elements: List[Dict[str, Any]]) -> float:
        """要素の重要度スコアを計算"""
        try:
            score = 0.0
            element_type = element.get("type", "")
            
            # タイプベースのスコア
            type_scores = {
                "title": 1.0,
                "heading": 0.8,
                "table": 0.7,
                "figure": 0.6,
                "text": 0.4,
                "list": 0.5
            }
            score += type_scores.get(element_type, 0.2)
            
            # サイズベースのスコア
            bbox = element.get("bbox", {})
            if bbox:
                area = self._calculate_bbox_area(bbox)
                # 正規化（仮の最大面積で割る）
                normalized_area = min(area / 100000, 1.0)
                score += normalized_area * 0.3
            
            return min(score, 1.0)
            
        except Exception as e:
            logger.error(f"Failed to calculate importance score: {e}")
            return 0.5
    
    def _calculate_page_bounds(self, elements: List[Dict[str, Any]]) -> Dict[str, float]:
        """ページ内の要素の境界を計算"""
        try:
            if not elements:
                return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0}
            
            min_x = min_y = float('inf')
            max_x = max_y = float('-inf')
            
            for element in elements:
                bbox = element.get("bbox", {})
                if bbox:
                    min_x = min(min_x, bbox.get("x1", 0))
                    min_y = min(min_y, bbox.get("y1", 0))
                    max_x = max(max_x, bbox.get("x2", 0))
                    max_y = max(max_y, bbox.get("y2", 0))
            
            return {
                "min_x": min_x if min_x != float('inf') else 0,
                "min_y": min_y if min_y != float('inf') else 0,
                "max_x": max_x if max_x != float('-inf') else 0,
                "max_y": max_y if max_y != float('-inf') else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate page bounds: {e}")
            return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0}
    
    def _analyze_element_relationships(self, hierarchical_pages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """要素間の関係を分析"""
        try:
            relationships = {
                "spatial_containment": {},
                "semantic_flow": {},
                "cross_page_references": {},
                "element_clusters": []
            }
            
            all_elements = []
            for page in hierarchical_pages:
                page_elements = page.get("original_elements", [])
                for element in page_elements:
                    element["page_number"] = page.get("page_number")
                    all_elements.append(element)
            
            # 空間的包含関係
            for element in all_elements:
                element_id = element.get("element_id")
                spatial_children = []
                
                for other in all_elements:
                    if (other.get("page_number") == element.get("page_number") and 
                        other.get("element_id") != element_id):
                        if self._is_bbox_contained(other.get("bbox", {}), element.get("bbox", {})):
                            spatial_children.append(other.get("element_id"))
                
                if spatial_children:
                    relationships["spatial_containment"][str(element_id)] = spatial_children
            
            return relationships
            
        except Exception as e:
            logger.error(f"Failed to analyze element relationships: {e}")
            return {"error": str(e)}