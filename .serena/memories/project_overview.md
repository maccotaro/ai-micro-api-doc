# ai-micro-api-doc プロジェクト概要

## 目的
ドキュメント処理のAPIゲートウェイ。
重い処理（OCR、レイアウト解析）はcelery-docに委譲し、軽量処理のみローカルで実行。

## 技術スタック
- **言語**: Python 3.11+
- **フレームワーク**: FastAPI
- **タスクキュー**: Celery + Redis
- **軽量処理**: PIL, Tesseract

## アーキテクチャ

```
front-admin → api-admin → api-doc → Redis → celery-doc
                         (Gateway)  (Queue)  (Worker)
```

## 処理の分類

### 軽量処理（api-doc内で同期実行）
| 処理 | クラス |
|------|--------|
| 画像クロッピング | `ImageCropper` |
| 領域OCR | `RegionOCRProcessor` |
| チャンク分割 | langchain |

### 重い処理（celery-docに委譲）
| 処理 | タスク |
|------|--------|
| ドキュメント処理 | `process_document_task` |

## ディレクトリ構造

```
app/
├── main.py
├── core/             # 設定、DB、認証
├── services/
│   └── processor/    # 軽量処理
│       ├── image_cropper.py
│       └── region_ocr_processor.py
├── routers/
│   ├── process.py    # 処理API
│   └── ocr.py        # OCR API
├── schemas/
└── tasks/
    ├── celery_app.py
    └── document_tasks.py
```

## 主要APIエンドポイント

### 処理API
- `POST /api/doc/process` - ドキュメント処理（celery-doc委譲）
- `GET /api/doc/process/status/{task_id}` - タスクステータス
- `GET /api/doc/process/status/{task_id}/stream` - SSE進捗

### OCR API
- `POST /api/doc/ocr/crop` - 画像クロッピング
- `POST /api/doc/ocr/ocr-region` - 領域OCR
- `GET /api/doc/ocr/metadata/{document_id}` - メタデータ取得

## 環境変数
- `REDIS_URL` - Redis接続
- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` - Celery設定
- `JWKS_URL` - 認証
- `STORAGE_BASE_PATH` - ドキュメント保存パス

## celery-docとの関係
- api-doc: APIゲートウェイ、軽量処理
- celery-doc: 重い処理（Docling、OCR、レイアウト解析）
