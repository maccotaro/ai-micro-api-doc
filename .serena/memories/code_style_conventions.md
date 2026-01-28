# ai-micro-api-doc コードスタイル・規約

## Pythonスタイル

### フォーマッター・リンター
- Black, Ruff, MyPy

### 命名規則
- クラス: PascalCase
- 関数/変数: snake_case
- 定数: UPPER_SNAKE_CASE

## Celeryタスク呼び出しパターン

```python
from app.tasks.celery_app import celery_app

# celery-docにタスク送信
result = celery_app.send_task(
    "app.tasks.document_tasks.process_document_task",
    args=[file_path, filename, callback_url, user_id],
)

# 結果を待機
task_result = result.get(timeout=300)
```

## 軽量処理パターン

```python
from app.services.processor import ImageCropper, RegionOCRProcessor

# 画像クロッピング
cropper = ImageCropper(image_path)
cropped = cropper.crop(x1, y1, x2, y2)

# 領域OCR
processor = RegionOCRProcessor()
text = processor.ocr_region(image_path, bbox)
```

## エラーハンドリング
- HTTPExceptionで適切なステータスコード
- タスクタイムアウト時のフォールバック
