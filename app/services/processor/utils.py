"""
Utility functions for document processing.
Contains helper functions used across different document processing modules.
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def get_element_type(element) -> str:
    """要素タイプを取得（othersystem形式：小文字）"""
    try:
        # 方法1: label属性
        element_type = None
        if hasattr(element, 'label') and element.label:
            element_type = str(element.label)
        
        # 方法2: prov.label属性
        elif hasattr(element, 'prov') and element.prov and hasattr(element.prov, 'label'):
            element_type = str(element.prov.label)
        
        # 方法3: クラス名からタイプを推測
        else:
            class_name = type(element).__name__.lower()
            
            # DocLayNet標準11タイプ + table-cell（12クラス体系）
            type_mapping = {
                'text': 'text',
                'paragraph': 'text',
                'title': 'title',
                'heading': 'section-header',
                'section_header': 'section-header',
                'section-header': 'section-header',
                'list': 'list-item',
                'list_item': 'list-item',
                'list-item': 'list-item',
                'table': 'table',
                'table_cell': 'table-cell',
                'table-cell': 'table-cell',
                'figure': 'picture',
                'image': 'picture',
                'picture': 'picture',
                'caption': 'caption',
                'formula': 'formula',
                'equation': 'formula',
                'footer': 'page-footer',
                'header': 'page-header',
                'page_header': 'page-header',
                'page-header': 'page-header',
                'page_footer': 'page-footer',
                'page-footer': 'page-footer',
                'footnote': 'footnote'
            }
            
            for pattern, mapped_type in type_mapping.items():
                if pattern in class_name:
                    return mapped_type
            
            logger.warning(f"Unknown element type from class: {class_name}")
            return 'text'  # デフォルトはtext
        
        # element_typeが取得できた場合の正規化
        if element_type:
            element_type_lower = element_type.lower()
            
            # DocLayNet標準11タイプ + table-cell（12クラス体系）
            doclaynets_mapping = {
                'title': 'title',
                'heading': 'section-header',
                'section_header': 'section-header',
                'section-header': 'section-header',
                'text': 'text',
                'paragraph': 'text',
                'list': 'list-item',
                'list_item': 'list-item',
                'list-item': 'list-item',
                'table': 'table',
                'table_cell': 'table-cell',
                'table-cell': 'table-cell',
                'figure': 'picture',
                'image': 'picture',
                'picture': 'picture',
                'caption': 'caption',
                'formula': 'formula',
                'equation': 'formula',
                'footer': 'page-footer',
                'header': 'page-header',
                'page_header': 'page-header',
                'page-header': 'page-header',
                'page_footer': 'page-footer',
                'page-footer': 'page-footer',
                'footnote': 'footnote'
            }
            
            return doclaynets_mapping.get(element_type_lower, 'text')
        
        logger.warning(f"Could not determine element type for {type(element).__name__}")
        return 'text'
        
    except Exception as e:
        logger.error(f"Error determining element type: {e}")
        return 'text'


def get_docling_element_type(item) -> str:
    """Docling要素から真の要素タイプを取得"""
    # 複数の方法でラベルを取得
    if hasattr(item, 'label') and item.label:
        return str(item.label)
    elif hasattr(item, 'prov') and hasattr(item.prov, 'label') and item.prov.label:
        return str(item.prov.label)
    elif hasattr(item, '__class__'):
        class_name = item.__class__.__name__
        # Docling完全要素タイプマッピング（DocLayNet標準 + 拡張）
        docling_types = {
            # DocLayNet標準11要素タイプ
            'title': 'Title',
            'heading': 'Title',
            'text': 'Text', 
            'paragraph': 'Text',
            'list': 'List',
            'table': 'Table',
            'figure': 'Figure',
            'caption': 'Caption',
            'formula': 'Formula',
            'footer': 'Footer',
            'header': 'Header',
            
            # Docling拡張要素タイプ
            'textelement': 'Text',
            'paragraphelement': 'Text',
            'titleelement': 'Title',
            'sectionheaderelement': 'Title',
            'tableelement': 'Table',
            'figureelement': 'Figure',
            'imageelement': 'Figure',
            'listelement': 'List',
            'captionelement': 'Caption',
            'formulaelement': 'Formula',
            'equationelement': 'Formula',
            'footerelement': 'Footer',
            'headerelement': 'Header',
            'referenceelement': 'Reference',
            'footnoteelement': 'Footnote',
            
            # 特殊Docling要素
            'pageheaderelement': 'Header',
            'pagefooterelement': 'Footer',
            'pageelement': 'Page',
            'documentelement': 'Document',
            'unknownelement': 'Unknown'
        }
        
        class_lower = class_name.lower()
        for pattern, docling_type in docling_types.items():
            if pattern in class_lower:
                return docling_type
        
        logger.warning(f"Unknown Docling element type: {class_name}")
        return class_name
    
    return 'Unknown'


def extract_bbox(item) -> Dict[str, float]:
    """アイテムからバウンディングボックスを抽出"""
    try:
        # 方法1: 直接bbox属性
        if hasattr(item, 'bbox') and item.bbox:
            bbox = item.bbox
            if hasattr(bbox, 'l') and hasattr(bbox, 't') and hasattr(bbox, 'r') and hasattr(bbox, 'b'):
                return {"x1": float(bbox.l), "y1": float(bbox.t), "x2": float(bbox.r), "y2": float(bbox.b)}
            elif hasattr(bbox, 'x') and hasattr(bbox, 'y') and hasattr(bbox, 'w') and hasattr(bbox, 'h'):
                return {"x1": float(bbox.x), "y1": float(bbox.y), "x2": float(bbox.x + bbox.w), "y2": float(bbox.y + bbox.h)}
        
        # 方法2: prov.bbox属性
        elif hasattr(item, 'prov') and hasattr(item.prov, 'bbox') and item.prov.bbox:
            bbox = item.prov.bbox
            if hasattr(bbox, 'l') and hasattr(bbox, 't') and hasattr(bbox, 'r') and hasattr(bbox, 'b'):
                return {"x1": float(bbox.l), "y1": float(bbox.t), "x2": float(bbox.r), "y2": float(bbox.b)}
        
        # 方法3: prov.bbox が辞書形式の場合
        elif hasattr(item, 'prov') and hasattr(item.prov, 'bbox') and isinstance(item.prov.bbox, dict):
            bbox = item.prov.bbox
            if all(key in bbox for key in ['l', 't', 'r', 'b']):
                return {"x1": float(bbox['l']), "y1": float(bbox['t']), "x2": float(bbox['r']), "y2": float(bbox['b'])}
        
        logger.warning(f"Could not extract bbox from {type(item).__name__}")
        return {"x1": 0.0, "y1": 0.0, "x2": 0.0, "y2": 0.0}
        
    except Exception as e:
        logger.error(f"Error extracting bbox: {e}")
        return {"x1": 0.0, "y1": 0.0, "x2": 0.0, "y2": 0.0}


def is_item_on_page(item, target_page: int) -> bool:
    """アイテムが指定されたページにあるかチェック（修正版）"""
    try:
        # アイテムがタプルの場合、実際のアイテムを取得（修正）
        actual_item = item[0] if isinstance(item, tuple) and len(item) >= 1 else item
        
        # 方法1: prov[0].page_no (修正版)
        if hasattr(actual_item, 'prov') and actual_item.prov and len(actual_item.prov) > 0:
            if hasattr(actual_item.prov[0], 'page_no'):
                page_found = actual_item.prov[0].page_no == target_page
                if page_found:
                    logger.debug(f"Found item on page {target_page} via prov[0].page_no")
                return page_found
            elif hasattr(actual_item.prov[0], 'page'):
                page_found = actual_item.prov[0].page == target_page
                if page_found:
                    logger.debug(f"Found item on page {target_page} via prov[0].page")
                return page_found
        
        # 方法3: 直接page属性
        if hasattr(actual_item, 'page_no'):
            page_found = actual_item.page_no == target_page
            if page_found:
                logger.debug(f"Found item on page {target_page} via direct page_no")
            return page_found
        elif hasattr(actual_item, 'page'):
            page_found = actual_item.page == target_page
            if page_found:
                logger.debug(f"Found item on page {target_page} via direct page")
            return page_found
        
        logger.debug(f"Could not determine page for item {type(actual_item).__name__}")
        return False
        
    except Exception as e:
        logger.error(f"Error checking page for item: {e}")
        return False


def get_pdf_page_size(document, page_num: int) -> tuple[float, float]:
    """PDFの実際のページサイズを取得（ExportedCCSDocument対応版）"""
    try:
        # ExportedCCSDocumentの場合はpage_dimensionsを使用
        from docling_core.types.doc.document import ExportedCCSDocument
        if isinstance(document, ExportedCCSDocument):
            if hasattr(document, 'page_dimensions') and document.page_dimensions:
                for page_dim in document.page_dimensions:
                    if page_dim.page == page_num + 1:  # 1-indexedページ番号
                        width, height = float(page_dim.width), float(page_dim.height)
                        logger.info(f"ExportedCCSDocument page {page_num + 1} size: {width}x{height} points")
                        return width, height
                
                # 最初のページのサイズを使用（フォールバック）
                if document.page_dimensions:
                    page_dim = document.page_dimensions[0]
                    width, height = float(page_dim.width), float(page_dim.height)
                    logger.info(f"ExportedCCSDocument using first page size: {width}x{height} points")
                    return width, height
        
        # pypdfium2を使って実際のページサイズを取得
        if hasattr(document, '_original_pdf_path'):
            import pypdfium2 as pdfium
            pdf_doc = pdfium.PdfDocument(document._original_pdf_path)
            if page_num < len(pdf_doc):
                page = pdf_doc[page_num]
                # ページのサイズをポイント単位で取得
                page_size = page.get_size()
                width, height = page_size
                pdf_doc.close()
                logger.info(f"PDF page {page_num + 1} size: {width}x{height} points")
                return float(width), float(height)
            pdf_doc.close()
    except Exception as e:
        logger.warning(f"Failed to get PDF page size: {e}")
    
    # フォールバック: A4サイズ
    logger.warning(f"Using default A4 size for page {page_num + 1}")
    return 595.32, 841.92  # A4サイズ（ポイント単位）