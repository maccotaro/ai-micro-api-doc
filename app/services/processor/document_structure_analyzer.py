"""
Document Structure Analyzer
文書全体の統合的な階層構造を分析・作成するモジュール
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


def clean_docling_text(text: str) -> str:
    """Doclingが生成する非標準テキストをクリーンアップ"""
    if not text:
        return ""
    text = re.sub(r'<non-compliant-utf8-text>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip()


class DocumentStructureAnalyzer:
    """文書全体の統合的な階層構造を分析するクラス"""
    
    def __init__(self):
        self.heading_keywords = [
            "章", "節", "項", "第", "部", "編", "巻", "号",
            "introduction", "conclusion", "summary", "abstract",
            "background", "method", "result", "discussion"
        ]
        
    def create_unified_document_structure(
        self, 
        document, 
        all_page_layouts: List[Dict[str, Any]],
        original_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """全ページを統合した文書階層構造を作成"""
        logger.info("Creating unified document structure from all pages")
        
        try:
            # 1. 全要素を収集・統合
            all_elements = self._collect_all_elements(all_page_layouts)
            
            # 2. 見出し構造を分析
            heading_structure = self._analyze_heading_hierarchy(all_elements)
            
            # 3. セクション構造を構築
            sections = self._build_section_structure(all_elements, heading_structure)
            
            # 4. 文書の論理構造を作成
            logical_structure = self._create_logical_structure(sections, all_elements)
            
            # 5. 統合階層構造を構築
            unified_structure = {
                "document_overview": {
                    "total_pages": original_metadata.get("total_pages", 0),
                    "total_elements": len(all_elements),
                    "structure_confidence": self._calculate_structure_confidence(heading_structure),
                    "document_type": self._detect_document_type(all_elements)
                },
                
                "hierarchical_outline": logical_structure,
                "sections": sections,
                "cross_page_relationships": self._analyze_cross_page_relationships(all_page_layouts),
                "navigation_map": self._create_navigation_map(sections),
                
                "element_statistics": {
                    "by_type": self._get_element_type_statistics(all_elements),
                    "by_section": self._get_section_statistics(sections),
                    "spatial_distribution": self._analyze_spatial_distribution(all_elements)
                }
            }
            
            return unified_structure
            
        except Exception as e:
            logger.error(f"Failed to create unified document structure: {e}")
            return {"error": str(e), "fallback": True}
    
    def create_unified_structure_from_docling(
        self, 
        document,
        num_pages: int
    ) -> Dict[str, Any]:
        """Doclingオブジェクトから直接統合構造を作成（効率的版）"""
        logger.info("Creating unified structure directly from Docling document")
        
        try:
            # Doclingから全要素を直接収集
            all_elements = self._collect_elements_from_docling(document)
            
            # 見出し構造を分析
            heading_structure = self._analyze_heading_hierarchy(all_elements)
            
            # セクション構造を構築
            sections = self._build_section_structure(all_elements, heading_structure)
            
            # 文書の論理構造を作成
            logical_structure = self._create_logical_structure(sections, all_elements)
            
            # ページ間関係の分析（Doclingオブジェクトから直接）
            cross_page_relationships = self._analyze_docling_relationships(document, num_pages)
            
            # 統合階層構造を構築
            unified_structure = {
                "document_overview": {
                    "total_pages": num_pages,
                    "total_elements": len(all_elements),
                    "structure_confidence": self._calculate_structure_confidence(heading_structure),
                    "document_type": self._detect_document_type(all_elements)
                },
                
                "hierarchical_outline": logical_structure,
                "sections": sections,
                "cross_page_relationships": cross_page_relationships,
                "navigation_map": self._create_navigation_map(sections),
                
                "element_statistics": {
                    "by_type": self._get_element_type_statistics(all_elements),
                    "by_section": self._get_section_statistics(sections),
                    "spatial_distribution": self._analyze_spatial_distribution(all_elements)
                }
            }
            
            return unified_structure
            
        except Exception as e:
            logger.error(f"Failed to create unified structure from Docling: {e}")
            return {"error": str(e), "fallback": True}
    
    def _collect_elements_from_docling(self, document) -> List[Dict[str, Any]]:
        """Doclingオブジェクトから全要素を収集"""
        all_elements = []
        element_id = 0
        
        try:
            # assembled.elementsから収集（レガシー形式）
            if hasattr(document, 'assembled') and document.assembled and hasattr(document.assembled, 'elements'):
                for element in document.assembled.elements:
                    element_dict = self._convert_docling_element(element, element_id)
                    if element_dict:
                        all_elements.append(element_dict)
                        element_id += 1
            
            # ExportedCCSDocument形式から収集
            if hasattr(document, 'main_text') and document.main_text:
                for text_item in document.main_text:
                    element_dict = self._convert_main_text_element(text_item, element_id)
                    if element_dict:
                        all_elements.append(element_dict)
                        element_id += 1
            
            if hasattr(document, 'figures') and document.figures:
                for figure in document.figures:
                    element_dict = self._convert_figure_element(figure, element_id)
                    if element_dict:
                        all_elements.append(element_dict)
                        element_id += 1
            
            if hasattr(document, 'tables') and document.tables:
                for table in document.tables:
                    element_dict = self._convert_table_element(table, element_id)
                    if element_dict:
                        all_elements.append(element_dict)
                        element_id += 1
            
            # 要素をページ順、Y座標順でソート
            all_elements.sort(key=lambda x: (x.get("source_page", 0), x.get("bbox", {}).get("y0", 0)))
            
        except Exception as e:
            logger.error(f"Failed to collect elements from Docling: {e}")
        
        return all_elements
    
    def _convert_docling_element(self, element, element_id: int) -> Optional[Dict[str, Any]]:
        """Docling要素を統一形式に変換"""
        try:
            element_dict = {
                "element_id": element_id,
                "type": self._get_element_type(element),
                "text": self._extract_element_text(element),
                "source_page": self._get_element_page(element),
                "bbox": self._extract_bbox(element),
                "global_id": f"element_{element_id}"
            }
            return element_dict
        except Exception as e:
            logger.warning(f"Failed to convert Docling element: {e}")
            return None
    
    def _convert_main_text_element(self, text_item, element_id: int) -> Optional[Dict[str, Any]]:
        """main_text要素を統一形式に変換"""
        try:
            element_dict = {
                "element_id": element_id,
                "type": "text",
                "text": clean_docling_text(str(text_item.text)) if hasattr(text_item, 'text') else "",
                "source_page": self._get_element_page(text_item),
                "bbox": self._extract_bbox_from_prov(text_item),
                "global_id": f"text_{element_id}"
            }
            
            # タイプの推定（DocLayNet標準11タイプのみ）
            if hasattr(text_item, 'obj_type'):
                obj_type = str(text_item.obj_type).lower()
                # DocLayNet標準タイプに正規化
                if obj_type in ['title', 'heading', 'section_header']:
                    element_dict["type"] = "title"
                elif obj_type in ['text', 'paragraph']:
                    element_dict["type"] = "text"
                elif obj_type in ['list', 'list_item']:
                    element_dict["type"] = "list_item"
                elif obj_type in ['table']:
                    element_dict["type"] = "table"
                elif obj_type in ['figure', 'image']:
                    element_dict["type"] = "figure"
                elif obj_type in ['caption']:
                    element_dict["type"] = "caption"
                elif obj_type in ['formula', 'equation']:
                    element_dict["type"] = "formula"
                elif obj_type in ['footer', 'page_footer']:
                    element_dict["type"] = "page_footer"
                elif obj_type in ['header', 'page_header']:
                    element_dict["type"] = "page_header"
                elif obj_type in ['footnote']:
                    element_dict["type"] = "footnote"
                else:
                    element_dict["type"] = "text"  # デフォルト
            elif hasattr(text_item, 'prov') and text_item.prov:
                if hasattr(text_item.prov[0], 'label'):
                    label = str(text_item.prov[0].label).lower()
                    # DocLayNet標準タイプに正規化
                    if any(keyword in label for keyword in ['title', 'heading', 'section_header']):
                        element_dict["type"] = "title"
                    elif any(keyword in label for keyword in ['text', 'paragraph']):
                        element_dict["type"] = "text"
                    elif any(keyword in label for keyword in ['list']):
                        element_dict["type"] = "list_item"
                    elif any(keyword in label for keyword in ['table']):
                        element_dict["type"] = "table"
                    elif any(keyword in label for keyword in ['figure', 'image']):
                        element_dict["type"] = "figure"
                    elif any(keyword in label for keyword in ['caption']):
                        element_dict["type"] = "caption"
                    elif any(keyword in label for keyword in ['formula', 'equation']):
                        element_dict["type"] = "formula"
                    elif any(keyword in label for keyword in ['footer']):
                        element_dict["type"] = "page_footer"
                    elif any(keyword in label for keyword in ['header']):
                        element_dict["type"] = "page_header"
                    elif any(keyword in label for keyword in ['footnote']):
                        element_dict["type"] = "footnote"
                    else:
                        element_dict["type"] = "text"  # デフォルト
            
            return element_dict
        except Exception as e:
            logger.warning(f"Failed to convert main_text element: {e}")
            return None
    
    def _convert_figure_element(self, figure, element_id: int) -> Optional[Dict[str, Any]]:
        """figure要素を統一形式に変換"""
        try:
            return {
                "element_id": element_id,
                "type": "figure",
                "text": self._extract_element_text(figure),
                "source_page": self._get_element_page(figure),
                "bbox": self._extract_bbox_from_prov(figure),
                "global_id": f"figure_{element_id}"
            }
        except Exception as e:
            logger.warning(f"Failed to convert figure element: {e}")
            return None
    
    def _convert_table_element(self, table, element_id: int) -> Optional[Dict[str, Any]]:
        """table要素を統一形式に変換"""
        try:
            return {
                "element_id": element_id,
                "type": "table",
                "text": self._extract_table_text(table),
                "source_page": self._get_element_page(table),
                "bbox": self._extract_bbox_from_prov(table),
                "global_id": f"table_{element_id}"
            }
        except Exception as e:
            logger.warning(f"Failed to convert table element: {e}")
            return None
    
    def _get_element_type(self, element) -> str:
        """要素タイプを取得（DocLayNet標準11タイプに変換）"""
        # utils.pyのget_element_type関数を使用してDocLayNet標準タイプに変換
        from .utils import get_element_type
        return get_element_type(element)
    
    def _extract_element_text(self, element) -> str:
        """要素からテキストを抽出"""
        if hasattr(element, 'text'):
            return clean_docling_text(str(element.text))
        elif hasattr(element, 'content'):
            return clean_docling_text(str(element.content))
        return ""
    
    def _extract_table_text(self, table) -> str:
        """テーブルからテキストを抽出"""
        try:
            if hasattr(table, 'data') and hasattr(table.data, 'table_cells'):
                cells_text = []
                for cell in table.data.table_cells:
                    if hasattr(cell, 'text'):
                        cells_text.append(clean_docling_text(str(cell.text)))
                return " | ".join(cells_text)
        except:
            pass
        return self._extract_element_text(table)
    
    def _get_element_page(self, element) -> int:
        """要素のページ番号を取得"""
        if hasattr(element, 'prov') and element.prov and len(element.prov) > 0:
            prov_item = element.prov[0]
            if hasattr(prov_item, 'page'):
                return prov_item.page
        return 1
    
    def _extract_bbox(self, element) -> Dict[str, float]:
        """要素からbboxを抽出"""
        if hasattr(element, 'bbox'):
            bbox = element.bbox
            if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                return {"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3]}
        return self._extract_bbox_from_prov(element)
    
    def _extract_bbox_from_prov(self, element) -> Dict[str, float]:
        """prov情報からbboxを抽出"""
        try:
            if hasattr(element, 'prov') and element.prov and len(element.prov) > 0:
                prov_item = element.prov[0]
                if hasattr(prov_item, 'bbox'):
                    bbox = prov_item.bbox
                    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                        return {"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3]}
        except:
            pass
        return {"x0": 0, "y0": 0, "x1": 0, "y1": 0}
    
    def _analyze_docling_relationships(self, document, num_pages: int) -> Dict[str, Any]:
        """Doclingオブジェクトからページ間関係を分析"""
        relationships = {
            "table_continuations": [],
            "figure_references": [],
            "text_flow_breaks": [],
            "section_boundaries": []
        }
        
        try:
            # テーブルの継続を検出（複数ページにまたがるテーブル）
            if hasattr(document, 'tables') and document.tables:
                prev_table_bottom = None
                prev_page = None
                
                for table in document.tables:
                    current_page = self._get_element_page(table)
                    if prev_page and current_page == prev_page + 1:
                        # 連続するページのテーブルを検出
                        relationships["table_continuations"].append({
                            "from_page": prev_page,
                            "to_page": current_page,
                            "confidence": 0.8
                        })
                    prev_page = current_page
            
        except Exception as e:
            logger.warning(f"Failed to analyze Docling relationships: {e}")
        
        return relationships
    
    def _collect_all_elements(self, all_page_layouts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """全ページから全要素を収集し、ページ情報を付与"""
        all_elements = []
        
        for page_layout in all_page_layouts:
            page_num = page_layout.get("page_number", 1)
            elements = page_layout.get("elements", [])
            
            for element in elements:
                # 要素にページ情報を付与
                enhanced_element = element.copy()
                enhanced_element["source_page"] = page_num
                enhanced_element["global_id"] = f"page_{page_num}_element_{element.get('element_id', 0)}"
                all_elements.append(enhanced_element)
        
        # 要素をページ順、Y座標順でソート
        all_elements.sort(key=lambda x: (x.get("source_page", 0), x.get("bbox", {}).get("y0", 0)))
        
        return all_elements
    
    def _analyze_heading_hierarchy(self, all_elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """見出し階層を分析"""
        headings = [el for el in all_elements if el.get("type") in ["title"]]  # DocLayNet標準
        
        if not headings:
            return {"levels": [], "hierarchy": [], "confidence": 0.0}
        
        # 見出しレベルを推定
        heading_levels = []
        for heading in headings:
            level = self._estimate_heading_level_advanced(heading, headings)
            heading_levels.append({
                "element": heading,
                "estimated_level": level,
                "text": heading.get("text", ""),
                "page": heading.get("source_page", 1),
                "confidence": self._calculate_heading_confidence(heading)
            })
        
        # 階層構造を構築
        hierarchy = self._build_heading_hierarchy(heading_levels)
        
        return {
            "levels": heading_levels,
            "hierarchy": hierarchy,
            "confidence": sum(h["confidence"] for h in heading_levels) / len(heading_levels) if heading_levels else 0.0
        }
    
    def _estimate_heading_level_advanced(self, heading: Dict[str, Any], all_headings: List[Dict[str, Any]]) -> int:
        """高度な見出しレベル推定"""
        text = heading.get("text", "").strip()
        
        # 1. キーワードベース判定
        if any(keyword in text.lower() for keyword in ["第", "章", "chapter"]):
            return 1
        elif any(keyword in text.lower() for keyword in ["節", "section", "§"]):
            return 2
        elif any(keyword in text.lower() for keyword in ["項", "subsection"]):
            return 3
        
        # 2. 位置ベース判定（ページの上部ほど高レベル）
        bbox = heading.get("bbox", {})
        y_position = bbox.get("y0", 0)
        page_height = 800  # 仮定
        
        if y_position < page_height * 0.2:  # ページ上部20%
            return 1
        elif y_position < page_height * 0.4:  # ページ上部40%
            return 2
        else:
            return 3
    
    def _build_heading_hierarchy(self, heading_levels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """見出しから階層構造を構築"""
        hierarchy = []
        stack = []  # 現在の階層スタック
        
        for heading_info in heading_levels:
            level = heading_info["estimated_level"]
            
            # スタックを現在のレベルまで調整
            while stack and stack[-1]["level"] >= level:
                stack.pop()
            
            # 階層ノードを作成
            node = {
                "level": level,
                "title": heading_info["text"],
                "page": heading_info["page"],
                "element_id": heading_info["element"].get("global_id"),
                "children": [],
                "content_elements": []
            }
            
            if stack:
                # 親ノードの子として追加
                stack[-1]["children"].append(node)
            else:
                # ルートレベル
                hierarchy.append(node)
            
            stack.append(node)
        
        return hierarchy
    
    def _build_section_structure(
        self, 
        all_elements: List[Dict[str, Any]], 
        heading_structure: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """セクション構造を構築"""
        sections = []
        current_section = None
        
        for element in all_elements:
            element_type = element.get("type", "")
            
            if element_type in ["title"]:  # DocLayNet標準
                # 新しいセクションの開始
                if current_section:
                    sections.append(current_section)
                
                current_section = {
                    "section_id": f"section_{len(sections) + 1}",
                    "title": element.get("text", ""),
                    "start_page": element.get("source_page", 1),
                    "end_page": element.get("source_page", 1),
                    "heading_element": element,
                    "content_elements": [],
                    "subsections": []
                }
            else:
                # 現在のセクションにコンテンツを追加
                if current_section:
                    current_section["content_elements"].append(element)
                    current_section["end_page"] = element.get("source_page", current_section["end_page"])
                else:
                    # 最初のセクション（見出しなし）
                    current_section = {
                        "section_id": "section_1",
                        "title": "Document Start",
                        "start_page": element.get("source_page", 1),
                        "end_page": element.get("source_page", 1),
                        "heading_element": None,
                        "content_elements": [element],
                        "subsections": []
                    }
        
        # 最後のセクションを追加
        if current_section:
            sections.append(current_section)
        
        return sections
    
    def _create_logical_structure(
        self, 
        sections: List[Dict[str, Any]], 
        all_elements: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """論理構造を作成"""
        return {
            "document_flow": [
                {
                    "sequence": i + 1,
                    "section_id": section["section_id"],
                    "title": section["title"],
                    "page_range": f"{section['start_page']}-{section['end_page']}",
                    "content_summary": self._summarize_section_content(section),
                    "element_count": len(section["content_elements"])
                }
                for i, section in enumerate(sections)
            ],
            "reading_order": self._determine_reading_order(sections),
            "information_hierarchy": self._create_information_hierarchy(sections)
        }
    
    def _analyze_cross_page_relationships(self, all_page_layouts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """ページ間の関係性を分析"""
        relationships = {
            "table_continuations": [],
            "figure_references": [],
            "text_flow_breaks": [],
            "section_boundaries": []
        }
        
        for i in range(len(all_page_layouts) - 1):
            current_page = all_page_layouts[i]
            next_page = all_page_layouts[i + 1]
            
            # テーブルの継続を検出
            current_tables = [el for el in current_page.get("elements", []) if el.get("type") == "table"]
            next_tables = [el for el in next_page.get("elements", []) if el.get("type") == "table"]
            
            if current_tables and next_tables:
                # 簡単な継続判定
                relationships["table_continuations"].append({
                    "from_page": current_page.get("page_number"),
                    "to_page": next_page.get("page_number"),
                    "confidence": 0.7  # 実際にはより詳細な分析が必要
                })
        
        return relationships
    
    def _create_navigation_map(self, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """ナビゲーションマップを作成"""
        return {
            "table_of_contents": [
                {
                    "section_id": section["section_id"],
                    "title": section["title"],
                    "page": section["start_page"],
                    "level": 1  # 実際にはより詳細なレベル判定が必要
                }
                for section in sections if section["title"] != "Document Start"
            ],
            "page_index": {
                f"page_{i+1}": [
                    section["section_id"] 
                    for section in sections 
                    if section["start_page"] <= i+1 <= section["end_page"]
                ]
                for i in range(max(section["end_page"] for section in sections) if sections else 0)
            }
        }
    
    def _calculate_structure_confidence(self, heading_structure: Dict[str, Any]) -> float:
        """構造の信頼度を計算"""
        if not heading_structure.get("levels"):
            return 0.0
        
        base_confidence = heading_structure.get("confidence", 0.0)
        level_diversity = len(set(h["estimated_level"] for h in heading_structure["levels"]))
        
        # レベルの多様性が高いほど信頼度が高い
        diversity_bonus = min(level_diversity * 0.2, 0.4)
        
        return min(base_confidence + diversity_bonus, 1.0)
    
    def _detect_document_type(self, all_elements: List[Dict[str, Any]]) -> str:
        """文書タイプを検出"""
        element_types = [el.get("type", "") for el in all_elements]
        text_content = " ".join([el.get("text", "") for el in all_elements[:10]])  # 最初の10要素
        
        if "abstract" in text_content.lower():
            return "academic_paper"
        elif element_types.count("table") > len(all_elements) * 0.3:
            return "data_report"
        elif element_types.count("figure") > len(all_elements) * 0.2:
            return "presentation"
        else:
            return "general_document"
    
    def _get_element_type_statistics(self, all_elements: List[Dict[str, Any]]) -> Dict[str, int]:
        """要素タイプ統計を取得"""
        stats = {}
        for element in all_elements:
            element_type = element.get("type", "unknown")
            stats[element_type] = stats.get(element_type, 0) + 1
        return stats
    
    def _get_section_statistics(self, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """セクション統計を取得"""
        return {
            "total_sections": len(sections),
            "average_elements_per_section": sum(len(s["content_elements"]) for s in sections) / len(sections) if sections else 0,
            "page_distribution": [
                {
                    "section_id": section["section_id"],
                    "page_count": section["end_page"] - section["start_page"] + 1
                }
                for section in sections
            ]
        }
    
    def _analyze_spatial_distribution(self, all_elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """空間分布を分析"""
        page_distribution = {}
        for element in all_elements:
            page = element.get("source_page", 1)
            page_distribution[f"page_{page}"] = page_distribution.get(f"page_{page}", 0) + 1
        
        return {
            "elements_per_page": page_distribution,
            "density_analysis": "uniform"  # 実際にはより詳細な分析が必要
        }
    
    def _calculate_heading_confidence(self, heading: Dict[str, Any]) -> float:
        """見出しの信頼度を計算"""
        text = heading.get("text", "")
        
        # 基本スコア
        confidence = 0.5
        
        # テキストの長さ（短いほど見出しらしい）
        if len(text) < 50:
            confidence += 0.2
        
        # キーワードの存在
        if any(keyword in text.lower() for keyword in self.heading_keywords):
            confidence += 0.3
        
        return min(confidence, 1.0)
    
    def _summarize_section_content(self, section: Dict[str, Any]) -> str:
        """セクションコンテンツを要約"""
        elements = section["content_elements"]
        if not elements:
            return "No content"
        
        element_types = [el.get("type", "") for el in elements]
        type_counts = {}
        for et in element_types:
            type_counts[et] = type_counts.get(et, 0) + 1
        
        summary_parts = []
        for element_type, count in type_counts.items():
            if count > 1:
                summary_parts.append(f"{count} {element_type}s")
            else:
                summary_parts.append(f"1 {element_type}")
        
        return ", ".join(summary_parts)
    
    def _determine_reading_order(self, sections: List[Dict[str, Any]]) -> List[str]:
        """読み順を決定"""
        return [section["section_id"] for section in sorted(sections, key=lambda x: x["start_page"])]
    
    def _create_information_hierarchy(self, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """情報階層を作成"""
        return {
            "primary_sections": [s["section_id"] for s in sections if s["title"] != "Document Start"],
            "content_density": {
                section["section_id"]: len(section["content_elements"])
                for section in sections
            }
        }