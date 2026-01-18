"""
Image Cropper Module
指定された矩形エリアの画像を切り出して保存するモジュール
"""

import logging
import os
from pathlib import Path
from typing import Tuple, Optional, Dict, Any
from PIL import Image
import datetime

logger = logging.getLogger(__name__)


class ImageCropper:
    """画像の切り出し処理を行うクラス"""
    
    def __init__(self):
        self.supported_formats = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif'}
    
    def crop_region(
        self,
        page_image_path: str,
        bbox: Dict[str, float],
        output_dir: str,
        element_id: Optional[str] = None,
        element_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        指定された矩形エリアを切り出して保存
        
        Args:
            page_image_path: 元画像のパス
            bbox: 切り出し範囲 {"x": float, "y": float, "width": float, "height": float}
            output_dir: 出力ディレクトリパス
            element_id: 要素ID（ファイル名に使用）
            element_type: 要素タイプ（ディレクトリ分類に使用）
            
        Returns:
            切り出し結果情報を含む辞書
        """
        try:
            # 入力画像の存在確認
            if not os.path.exists(page_image_path):
                raise FileNotFoundError(f"Source image not found: {page_image_path}")
            
            # 画像を開く
            with Image.open(page_image_path) as image:
                img_width, img_height = image.size
                logger.info(f"Source image size: {img_width}x{img_height}")
                
                # BBox座標の検証と調整
                x = max(0, min(bbox['x'], img_width))
                y = max(0, min(bbox['y'], img_height))
                width = max(1, min(bbox['width'], img_width - x))
                height = max(1, min(bbox['height'], img_height - y))
                
                logger.info(f"Crop region: x={x}, y={y}, w={width}, h={height}")
                
                # 切り出し領域を設定
                crop_box = (int(x), int(y), int(x + width), int(y + height))
                
                # 画像を切り出し
                cropped_image = image.crop(crop_box)
                
                # 出力パスを生成
                output_path = self._generate_output_path(
                    output_dir, element_id, element_type
                )
                
                # ディレクトリを作成
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # 切り出し画像を保存
                cropped_image.save(output_path, format='PNG', optimize=True)
                
                # ファイル情報を取得
                file_size = os.path.getsize(output_path)
                cropped_width, cropped_height = cropped_image.size
                
                logger.info(f"Cropped image saved: {output_path}")
                logger.info(f"Cropped size: {cropped_width}x{cropped_height}, {file_size} bytes")
                
                return {
                    "success": True,
                    "image_path": os.path.relpath(output_path, output_dir),
                    "full_path": output_path,
                    "width": cropped_width,
                    "height": cropped_height,
                    "file_size": file_size,
                    "crop_coordinates": {
                        "x": x,
                        "y": y,
                        "width": width,
                        "height": height
                    }
                }
                
        except Exception as e:
            logger.error(f"Image cropping failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "image_path": "",
                "full_path": "",
                "width": 0,
                "height": 0,
                "file_size": 0
            }
    
    def _generate_output_path(
        self,
        output_dir: str,
        element_id: Optional[str] = None,
        element_type: Optional[str] = None
    ) -> str:
        """出力ファイルパスを生成"""
        
        # タイムスタンプを生成
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        
        # ファイル名を構築
        if element_id:
            if element_type:
                filename = f"{element_type}_{element_id}_{timestamp}.png"
            else:
                filename = f"element_{element_id}_{timestamp}.png"
        else:
            filename = f"cropped_{timestamp}.png"
        
        # サブディレクトリを決定
        if element_type and element_type in ['figure', 'picture']:
            subdir = 'figures'
        else:
            subdir = 'cropped'
        
        return os.path.join(output_dir, subdir, filename)
    
    def crop_figure_elements(
        self,
        page_image_path: str,
        figures: list,
        output_dir: str
    ) -> Dict[str, Any]:
        """
        複数のfigure要素を一括で切り出し
        
        Args:
            page_image_path: 元画像パス
            figures: figure要素のリスト
            output_dir: 出力ディレクトリ
            
        Returns:
            処理結果のサマリー
        """
        results = []
        success_count = 0
        
        try:
            for figure in figures:
                # bbox形式の判定と変換
                if 'bbox' in figure and isinstance(figure['bbox'], dict):
                    # bbox形式 (x1,y1,x2,y2) -> (x,y,width,height)
                    elem_bbox = figure['bbox']
                    bbox = {
                        'x': elem_bbox.get('x1', 0),
                        'y': elem_bbox.get('y1', 0),
                        'width': elem_bbox.get('x2', 0) - elem_bbox.get('x1', 0),
                        'height': elem_bbox.get('y2', 0) - elem_bbox.get('y1', 0)
                    }
                elif all(k in figure for k in ['x', 'y', 'width', 'height']):
                    # 既に正しい形式
                    bbox = {
                        'x': figure['x'],
                        'y': figure['y'],
                        'width': figure['width'],
                        'height': figure['height']
                    }
                else:
                    logger.warning(f"Invalid figure bbox format: {figure}")
                    continue
                
                result = self.crop_region(
                    page_image_path,
                    bbox,
                    output_dir,
                    figure.get('id'),
                    'figure'
                )
                
                if result['success']:
                    success_count += 1
                    # 元のfigure要素に画像パス情報を追加
                    figure['cropped_image_path'] = result['image_path']
                    figure['cropped_full_path'] = result['full_path']
                
                results.append(result)
                
        except Exception as e:
            logger.error(f"Batch figure cropping failed: {e}")
        
        return {
            "total_figures": len(figures),
            "success_count": success_count,
            "failed_count": len(figures) - success_count,
            "results": results
        }
    
    def crop_single_element(
        self,
        page_image_path: str,
        element: Dict[str, Any],
        output_dir: str,
        scale_factor: float = 2.0
    ) -> bool:
        """
        単一要素の画像を切り出してelement辞書に結果を設定
        
        Args:
            page_image_path: 元画像パス
            element: 階層要素辞書（結果が直接設定される）
            output_dir: 出力ディレクトリ
            scale_factor: 画像生成時のスケール係数（デフォルト2.0）
            
        Returns:
            切り出し成功フラグ
        """
        try:
            # 画像要素のみ処理
            element_type = element.get('type', '')
            if element_type not in ['picture', 'figure', 'caption', 'table']:
                return False
            
            # bbox座標を取得
            bbox_dict = element.get('bbox')
            if not bbox_dict:
                logger.warning(f"No bbox found for element {element.get('id', 'unknown')}")
                return False
            
            # bbox形式の正規化とスケール適用
            if isinstance(bbox_dict, dict):
                if all(k in bbox_dict for k in ['x1', 'y1', 'x2', 'y2']):
                    # bbox形式 (x1,y1,x2,y2) -> (x,y,width,height) with scale
                    bbox = {
                        'x': bbox_dict['x1'] * scale_factor,
                        'y': bbox_dict['y1'] * scale_factor, 
                        'width': (bbox_dict['x2'] - bbox_dict['x1']) * scale_factor,
                        'height': (bbox_dict['y2'] - bbox_dict['y1']) * scale_factor
                    }
                elif all(k in bbox_dict for k in ['x', 'y', 'width', 'height']):
                    # 既に正しい形式（スケール適用）
                    bbox = {
                        'x': bbox_dict['x'] * scale_factor,
                        'y': bbox_dict['y'] * scale_factor,
                        'width': bbox_dict['width'] * scale_factor,
                        'height': bbox_dict['height'] * scale_factor
                    }
                else:
                    logger.warning(f"Invalid bbox format for element {element.get('id', 'unknown')}: {bbox_dict}")
                    return False
            else:
                logger.warning(f"Invalid bbox type for element {element.get('id', 'unknown')}: {type(bbox_dict)}")
                return False
            
            # 画像を切り出し
            result = self.crop_region(
                page_image_path,
                bbox,
                output_dir,
                element.get('id'),
                element_type
            )
            
            if result['success']:
                # 元のelement辞書に画像パス情報を直接設定
                # フロントエンド用の相対パス形式に統一
                relative_path = result['image_path'].replace('\\', '/')
                element['cropped_image_path'] = relative_path
                element['cropped_full_path'] = result['full_path']
                element['crop_info'] = {
                    'width': result['width'],
                    'height': result['height'],
                    'file_size': result['file_size']
                }
                
                logger.info(f"Successfully cropped element {element.get('id', 'unknown')}: {result['image_path']}")
                return True
            else:
                logger.error(f"Failed to crop element {element.get('id', 'unknown')}: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Exception in crop_single_element for {element.get('id', 'unknown')}: {e}")
            return False