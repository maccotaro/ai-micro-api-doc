"""
Image processing utilities for document processing.
Handles page image generation, annotation creation, and drawing operations.
"""

from pathlib import Path
from typing import Dict, List, Any
import logging

try:
    import pypdfium2 as pdfium
    PYPDFIUM2_AVAILABLE = True
except ImportError:
    PYPDFIUM2_AVAILABLE = False

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Image processing for document analysis operations"""
    
    def __init__(self):
        pass
    
    def create_page_image(self, page_num: int, images_dir: Path, document=None, page_obj=None) -> List[Dict[str, Any]]:
        """ページ画像を作成（original と annotated の両方）"""
        page_image_filename = f"page_{page_num + 1}_full.png"
        page_image_path = images_dir / page_image_filename
        annotated_image_filename = f"page_{page_num + 1}_full_annotated.png"
        annotated_image_path = images_dir / annotated_image_filename
        
        image_created = False
        annotated_image_created = False
        width, height = 800, 1000  # デフォルトサイズ
        
        try:
            # pypdfium2を使用して高品質画像を生成
            if document and hasattr(document, '_original_pdf_path') and PYPDFIUM2_AVAILABLE:
                logger.info(f"Creating page image using pypdfium2 for page {page_num + 1}")
                
                pdf_doc = pdfium.PdfDocument(document._original_pdf_path)
                if page_num < len(pdf_doc):
                    page = pdf_doc[page_num]
                    # 高品質画像を生成（2倍スケール、約150 DPI）
                    image = page.render(scale=2.0)
                    pil_image = image.to_pil()
                    width, height = pil_image.size
                    pil_image.save(page_image_path, 'PNG', quality=95)
                    image_created = True
                    logger.info(f"High-quality page image created: {page_image_filename} ({width}x{height})")
                    
                    # 注釈画像も作成（レイアウトデータがある場合）
                    if document and hasattr(document, 'pages') and page_num < len(document.pages):
                        try:
                            # Doclingからレイアウト情報を取得
                            page_layout = document.pages[page_num]
                            if hasattr(page_layout, '_layout') and page_layout._layout:
                                layout_data = {"elements": []}
                                # レイアウト要素をDocLayNet標準形式に変換
                                for element in page_layout._layout:
                                    if hasattr(element, 'bbox'):
                                        bbox = element.bbox
                                        # DocLayNet標準タイプに変換
                                        from .utils import get_element_type
                                        element_type = get_element_type(element)
                                        layout_data["elements"].append({
                                            "type": element_type,
                                            "bbox": {
                                                "x1": bbox.l,
                                                "y1": bbox.t, 
                                                "x2": bbox.r,
                                                "y2": bbox.b
                                            },
                                            "text": getattr(element, 'text', '')
                                        })
                                
                                if layout_data["elements"]:
                                    annotated_image_created = self.create_annotated_image(
                                        page_image_path, layout_data, annotated_image_path, scale_factor=2.0
                                    )
                        except Exception as e:
                            logger.warning(f"Failed to create annotated image from Docling layout: {e}")
                    
                pdf_doc.close()
            
            else:
                logger.warning(f"pypdfium2 not available or document path missing for page {page_num + 1}")
                
        except Exception as e:
            logger.error(f"Failed to create page image for page {page_num + 1}: {e}")
        
        # 結果を返す
        result_images = []
        if image_created:
            result_images.append({
                "type": "full_page",
                "file": page_image_filename,
                "width": width,
                "height": height
            })
        
        if annotated_image_created:
            result_images.append({
                "type": "annotated",
                "file": annotated_image_filename,
                "width": width,
                "height": height
            })
        
        return result_images
    
    def create_annotated_image(self, original_image_path: Path, layout_data: Dict, output_path: Path, scale_factor: float = 2.0) -> bool:
        """バウンディングボックス付きの注釈画像を作成（ラベル付き版）"""
        try:
            # 元画像を開く
            with Image.open(original_image_path) as img:
                # 注釈用のコピーを作成
                annotated_img = img.copy()
                draw = ImageDraw.Draw(annotated_img)
                
                logger.info(f"Creating annotated image: scale={scale_factor}, image_size={img.size}")
                
                # DocLayNet標準11タイプのカラーマップ
                color_map = {
                    'text': '#0066CC',           # Blue
                    'title': '#FF6600',          # Orange
                    'list_item': '#009900',      # Green
                    'table': '#CC0099',          # Magenta
                    'figure': '#990099',         # Purple
                    'caption': '#666666',        # Gray
                    'formula': '#FF3366',        # Pink
                    'page_header': '#3399CC',    # Light Blue
                    'page_footer': '#3399CC',    # Light Blue
                    'footnote': '#996633',       # Brown
                }
                
                # デフォルト色
                default_color = '#0066CC'
                
                # フォントサイズの設定（スケールに応じて調整、読みやすさを向上）
                try:
                    font_size = max(10, min(16, int(10 * scale_factor)))  # サイズ調整
                    # 日本語対応フォントを試行
                    try:
                        from PIL import ImageFont
                        font = ImageFont.truetype("/System/Library/Fonts/Arial Unicode MS.ttf", font_size)
                    except:
                        try:
                            font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", font_size)
                        except:
                            try:
                                # UbuntuなどのLinux環境での代替フォント
                                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
                            except:
                                # デフォルトフォント
                                font = ImageFont.load_default()
                except Exception as e:
                    logger.warning(f"Font loading failed: {e}, using default font")
                    font = None
                
                # 各要素にバウンディングボックスを描画
                elements = layout_data.get('elements', [])
                for element in elements:
                    bbox = element.get('bbox', {})
                    if not bbox:
                        continue
                        
                    element_type = element.get('type', 'text').lower()
                    color = color_map.get(element_type, default_color)
                    
                    # スケーリング適用（PDF/画像座標 → 表示画像座標）
                    pdf_height = layout_data.get('height', 842.4)  # A4のデフォルト高さ
                    
                    x1 = bbox.get('x1', 0) * scale_factor
                    x2 = bbox.get('x2', bbox.get('x1', 0) + 100) * scale_factor
                    
                    y1_input = bbox.get('y1', 0)
                    y2_input = bbox.get('y2', y1_input + 20)
                    
                    # すべての要素をPDF座標系（左下原点）として扱い、画像座標系（左上原点）に変換
                    y1 = (pdf_height - y2_input) * scale_factor  # PDFのy2が画像のy1になる
                    y2 = (pdf_height - y1_input) * scale_factor  # PDFのy1が画像のy2になる
                    logger.info(f"Converting PDF coordinates to image coordinates for {element_type}: PDF({y1_input:.1f}-{y2_input:.1f}) → Image({y1:.1f}-{y2:.1f})")
                    
                    logger.debug(f"Drawing {element_type} bbox: Input({bbox.get('x1', 0):.1f}, {y1_input:.1f}-{y2_input:.1f}) → Image({x1:.1f}, {y1:.1f}-{y2:.1f})")
                    
                    # バウンディングボックスを描画（1pt = scale_factor * 1）
                    line_width = max(1, int(1 * scale_factor))  # 1pt相当の線幅
                    draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=line_width)
                    
                    # ラベル生成（読みやすさを重視した順序）
                    label_parts = []
                    
                    # リスト項目の場合はネスト情報を表示
                    if element_type == 'list_item' and 'list_info' in element:
                        list_info = element['list_info']
                        indent_level = list_info.get('indent_level', 0)
                        is_nested = list_info.get('is_nested', False)
                        
                        if is_nested:
                            label_parts.append(f"L{indent_level}")  # L1, L2等でレベル表示
                        else:
                            label_parts.append("LIST")
                    
                    # テーブルセルの場合は詳細情報を最初に
                    elif element_type == 'table_cell' and 'table_info' in element:
                        table_info = element['table_info']
                        row = table_info.get('row', '')
                        col = table_info.get('col', '')
                        cell_type = table_info.get('cell_type', '')
                        is_header = table_info.get('is_header', False)
                        
                        # 行列情報を最初に（最も重要）
                        if row != '' and col != '':
                            label_parts.append(f"[{row},{col}]")
                        
                        # ヘッダー情報（重要）
                        if is_header:
                            label_parts.append("HDR")
                        elif cell_type == 'col_header':
                            label_parts.append("COL")
                        elif cell_type == 'row_header':
                            label_parts.append("ROW") 
                        elif cell_type:
                            # その他のセルタイプは短縮形
                            short_type = cell_type.replace('_header', '').replace('body', 'BODY')[:4].upper()
                            if short_type not in ['HDR', 'COL', 'ROW']:
                                label_parts.append(short_type)
                        
                        # 基本タイプは省略（table_cellは自明）
                    else:
                        # 非テーブル要素の場合は基本タイプを表示
                        label_parts.append(element_type.upper())
                    
                    # 要素ID（常に最後）
                    if 'element_id' in element:
                        label_parts.append(f"#{element['element_id']}")
                    
                    # ラベルテキスト作成
                    label_text = " ".join(label_parts)
                    
                    # ラベル描画位置計算（矩形の上部左側）
                    label_x = x1
                    label_y = max(0, y1 - font_size - 2) if font else max(0, y1 - 15)
                    
                    # 背景矩形のサイズ計算
                    if font:
                        try:
                            text_bbox = draw.textbbox((0, 0), label_text, font=font)
                            text_width = text_bbox[2] - text_bbox[0]
                            text_height = text_bbox[3] - text_bbox[1]
                        except:
                            text_width = len(label_text) * (font_size // 2)
                            text_height = font_size
                    else:
                        text_width = len(label_text) * 6
                        text_height = 11
                    
                    # ラベル背景を描画（半透明の白）
                    bg_x1 = label_x - 2
                    bg_y1 = label_y - 2
                    bg_x2 = label_x + text_width + 4
                    bg_y2 = label_y + text_height + 2
                    
                    # 背景矩形
                    draw.rectangle([(bg_x1, bg_y1), (bg_x2, bg_y2)], fill='white', outline=color, width=1)
                    
                    # ラベルテキスト描画
                    if font:
                        draw.text((label_x, label_y), label_text, fill=color, font=font)
                    else:
                        draw.text((label_x, label_y), label_text, fill=color)
                
                # 注釈画像を保存
                annotated_img.save(output_path, 'PNG', optimize=True)
                logger.info(f"Created annotated image with {len(elements)} labeled bounding boxes: {output_path}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to create annotated image: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def draw_layout_bboxes_on_image(self, image_path: str, layout_elements: List[Dict], images_dir: Path) -> str:
        """画像上にレイアウト要素のバウンディングボックスを描画"""
        try:
            import os
            
            # 元の画像を読み込み
            original_image = Image.open(image_path)
            annotated_image = original_image.copy()
            draw = ImageDraw.Draw(annotated_image)
            
            # 要素タイプごとの色を定義（Doclingの実際の要素タイプに対応）
            element_colors = {
                # 主要な要素タイプ
                "text": "#0066CC",           # 青（通常のテキスト）
                "Text": "#0066CC",           # 青（通常のテキスト）
                "title": "#FF6600",          # オレンジ（タイトル）
                "Title": "#FF6600",          # オレンジ（タイトル）
                "list_item": "#009900",      # 緑（リスト項目）
                "List": "#009900",           # 緑（リスト）
                "Table": "#CC0099",          # マゼンタ（テーブル）
                "table": "#CC0099",          # マゼンタ（テーブル）
                "figure": "#990099",         # 紫（図・画像）
                "Figure": "#990099",         # 紫（図・画像）
                "caption": "#666666",        # グレー（キャプション）
                "Caption": "#666666",        # グレー（キャプション）
                "formula": "#FF3366",        # 赤ピンク（数式）
                "Formula": "#FF3366",        # 赤ピンク（数式）
                "footnote": "#996633",       # 茶色（脚注）
                "Footnote": "#996633",       # 茶色（脚注）
                "page_header": "#3399CC",    # 水色（ページヘッダー）
                "Page-header": "#3399CC",    # 水色（ページヘッダー）
                "page_footer": "#3399CC",    # 水色（ページフッター）
                "Page-footer": "#3399CC",    # 水色（ページフッター）
                # 非DocLayNet標準タイプ（必要に応じて保持）
                "table_header": "#FF0099",   # 濃いピンク（テーブルヘッダー）
                "table_cell": "#CC66CC",     # 薄い紫（テーブルセル）
                # デフォルト
                "DefaultElement": "#808080",  # グレー
                "Unknown": "#808080",        # グレー
            }
            
            # デフォルトカラー
            default_color = "#FF0000"
            
            # フォントを準備（可能な場合）
            try:
                font = ImageFont.load_default()
            except:
                font = None
            
            logger.info(f"Drawing {len(layout_elements)} bounding boxes on image")
            
            for i, element in enumerate(layout_elements):
                try:
                    bbox = element.get("bbox", {})
                    element_type = element.get("type", "Unknown")
                    
                    if not bbox:
                        logger.warning(f"Element {i} has no bbox, skipping")
                        continue
                    
                    # 座標を取得
                    x1 = bbox.get("x1", 0)
                    y1 = bbox.get("y1", 0)
                    x2 = bbox.get("x2", x1)
                    y2 = bbox.get("y2", y1)
                    
                    # 座標の妥当性をチェック
                    if x1 >= x2 or y1 >= y2:
                        logger.warning(f"Invalid bbox for element {i}: {bbox}")
                        continue
                    
                    # 要素タイプに基づいて色を選択
                    color = element_colors.get(element_type, default_color)
                    
                    # バウンディングボックスを描画
                    line_width = 2  # 1pt相当（画像は通常2x解像度）
                    draw.rectangle([x1, y1, x2, y2], outline=color, width=line_width)
                    
                    # テーブルの場合、追加でセル描画
                    if element_type.lower() in ['table', 'Table'] and 'table_data' in element:
                        self.draw_table_cells(draw, element['table_data'], 1.0, element_colors, font)
                    
                    # 要素ID/タイプをラベルとして描画（オプション）
                    element_id = element.get("element_id", i)
                    label_text = f"{element_type}:{element_id}"
                    
                    if font:
                        try:
                            text_x = x1 + 2
                            text_y = y1 - 15 if y1 > 15 else y1 + 2
                            draw.text((text_x, text_y), label_text, fill=color, font=font)
                        except:
                            pass  # フォント描画に失敗しても続行
                    
                    logger.debug(f"Drew bbox for element {i} ({element_type}): ({x1},{y1})-({x2},{y2})")
                    
                except Exception as e:
                    logger.warning(f"Failed to draw bbox for element {i}: {e}")
                    continue
            
            # 注釈付き画像を保存
            annotated_filename = f"page_{Path(image_path).stem.split('_')[-1]}_full_annotated.png"
            annotated_path = images_dir / annotated_filename
            annotated_image.save(annotated_path, 'PNG', optimize=True)
            
            logger.info(f"Created annotated image with layout bboxes: {annotated_filename}")
            return annotated_filename
            
        except Exception as e:
            logger.error(f"Failed to create annotated image: {e}")
            return ""
    
    def draw_table_cells(self, draw, table_data, scale_factor, element_colors, font):
        """テーブルの個別セルを描画"""
        try:
            cells = table_data.get('cells', [])
            logger.info(f"Drawing {len(cells)} table cells")
            
            for cell_idx, cell in enumerate(cells):
                cell_bbox = cell.get('bbox')
                if not cell_bbox:
                    continue
                
                # セル座標をスケーリング
                cell_x1 = int(cell_bbox["x1"] * scale_factor)
                cell_y1 = int(cell_bbox["y1"] * scale_factor)
                cell_x2 = int(cell_bbox["x2"] * scale_factor)
                cell_y2 = int(cell_bbox["y2"] * scale_factor)
                
                # ヘッダーセルとデータセルで色を変える
                if cell.get('is_header', False):
                    cell_color = element_colors.get('table_header', '#FF0099')
                    cell_type = 'header'
                else:
                    cell_color = element_colors.get('table_cell', '#CC66CC')
                    cell_type = 'cell'
                
                # セルの境界線を描画（1pt相当）
                cell_line_width = 1  # より細い1pt未満の線
                draw.rectangle([cell_x1, cell_y1, cell_x2, cell_y2], 
                             outline=cell_color, width=cell_line_width)
                
                # セル内のテキストを描画（小さいフォント）
                cell_text = cell.get('text', '')[:10]  # 10文字に制限
                if cell_text and font:
                    text_x = cell_x1 + 2
                    text_y = cell_y1 + 2
                    try:
                        draw.text((text_x, text_y), cell_text, fill=cell_color, font=font)
                    except:
                        pass  # フォント描画に失敗しても続行
                
                logger.debug(f"Drew table {cell_type} cell {cell_idx}: ({cell_x1},{cell_y1})-({cell_x2},{cell_y2})")
            
        except Exception as e:
            logger.warning(f"Failed to draw table cells: {e}")