# ai-micro-api-doc - ドキュメント処理ゲートウェイ

## 概要

このサービスは、ドキュメント処理のAPIゲートウェイとして機能するマイクロサービスです。
重い処理（OCR、レイアウト解析、階層構造変換）は`celery-doc`ワーカーに委譲し、軽量な処理（画像クロッピング、領域OCR）のみローカルで実行します。

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ゲートウェイアーキテクチャ                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  api-doc (このサービス)                                                     │
│  ├── APIゲートウェイ: リクエスト受付・ルーティング                          │
│  ├── 軽量処理（同期）:                                                      │
│  │   ├── ImageCropper: 画像クロッピング                                     │
│  │   └── RegionOCRProcessor: 特定領域のOCR                                 │
│  └── 重い処理（非同期）: celery-docにタスク送信                             │
│                                                                             │
│  celery-doc (別サービス)                                                    │
│  ├── Doclingレイアウト解析                                                  │
│  ├── 階層構造変換                                                           │
│  ├── フルページOCR処理                                                      │
│  └── 画像生成・アノテーション                                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### サービス間通信

```
front-admin → api-admin → api-doc → Redis → celery-doc
                         (Gateway)  (Queue)  (Worker)
```

## 技術スタック

- **フレームワーク**: FastAPI
- **言語**: Python 3.11+
- **タスクキュー**: Celery + Redis
- **軽量処理**: PIL, Tesseract（領域OCR用）

## ディレクトリ構造

```
ai-micro-api-doc/
├── app/
│   ├── main.py                      # FastAPIエントリーポイント
│   ├── core/
│   │   ├── config.py                # 設定
│   │   ├── database.py              # DB接続
│   │   └── security.py              # JWT認証
│   ├── services/
│   │   └── processor/               # 軽量処理モジュール
│   │       ├── __init__.py          # エクスポート定義
│   │       ├── image_cropper.py     # 画像クロッピング
│   │       └── region_ocr_processor.py # 領域OCR
│   ├── routers/
│   │   ├── process.py               # 処理API（celery-docへ委譲）
│   │   └── ocr.py                   # OCR API（軽量処理）
│   ├── schemas/                     # Pydanticスキーマ
│   └── tasks/                       # Celeryタスク
│       ├── celery_app.py            # Celeryアプリ（クライアント）
│       └── document_tasks.py        # 軽量タスク（chunk, ocr_region）
├── Dockerfile                       # NVIDIA GPU版
├── Dockerfile.mac                   # M3 Mac CPU版
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## API エンドポイント

### 処理API (`/api/doc`)

```
GET  /api/doc/status
  - celery-docワーカーのステータス確認

POST /api/doc/process
  - ドキュメント処理（celery-docに委譲）
  - wait=true: 完了まで待機（デフォルト）
  - wait=false: 即座にtask_id返却
  - リクエスト: multipart/form-data (file)
  - レスポンス: DocumentProcessResponse

POST /api/doc/process/async
  - ドキュメント処理（非同期・celery-doc）
  - リクエスト: multipart/form-data (file, callback_url)
  - レスポンス: task_id

GET  /api/doc/process/status/{task_id}
  - 非同期タスクのステータス確認

GET  /api/doc/process/status/{task_id}/stream
  - SSEによるリアルタイム進捗ストリーミング

POST /api/doc/chunk
  - テキストのチャンク分割（同期・軽量）
  - リクエスト: text, chunk_size, chunk_overlap
  - レスポンス: chunks[]
```

### OCR API (`/api/doc/ocr`)

```
POST /api/doc/ocr/crop
  - 画像領域のクロッピング（同期・軽量）

GET  /api/doc/ocr/images/{document_id}/{path}
  - 処理済み画像の取得

GET  /api/doc/ocr/metadata/{document_id}
  - OCRメタデータの取得

PUT  /api/doc/ocr/metadata/{document_id}
  - OCRメタデータの更新

POST /api/doc/ocr/save-cropped-image
  - クロップ画像の永続保存

POST /api/doc/ocr/ocr-region
  - 特定領域のOCR実行（同期・軽量）
```

## 処理の分類

### 軽量処理（api-doc内で同期実行）

| 処理 | クラス | 用途 |
|------|--------|------|
| 画像クロッピング | `ImageCropper` | 矩形領域の切り出し |
| 領域OCR | `RegionOCRProcessor` | 特定領域のテキスト認識 |
| チャンク分割 | langchain | テキスト分割 |

### 重い処理（celery-docに委譲）

| 処理 | タスク | 用途 |
|------|--------|------|
| ドキュメント処理 | `process_document_task` | OCR、レイアウト解析、階層構造変換 |

## 環境変数

| 変数 | 説明 | デフォルト |
|------|------|-----------|
| `REDIS_URL` | Redis接続URL | `redis://:password@localhost:6379/1` |
| `CELERY_BROKER_URL` | Celeryブローカー | `redis://:password@localhost:6379/1` |
| `CELERY_RESULT_BACKEND` | Celery結果バックエンド | `redis://:password@localhost:6379/2` |
| `JWKS_URL` | 認証サービスJWKS URL | - |
| `STORAGE_BASE_PATH` | ドキュメント保存パス | `/data/documents` |

## Docker実行

### WSL2 + NVIDIA GPU

```bash
cd ai-micro-api-doc
docker compose up -d
```

### M3 Mac (CPU版)

```bash
cd ai-micro-api-doc
docker compose -f docker-compose.mac.yml up -d
```

## celery-docとの関係

```
api-doc                          celery-doc
├── APIエンドポイント            ├── Celeryワーカー
├── リクエスト受付               ├── 重い処理実行
├── ファイル保存                 │   ├── Docling
├── タスク送信                   │   ├── OCR
│   (send_task)                  │   ├── レイアウト解析
└── 結果取得                     │   └── 階層構造変換
                                 └── 結果返却
```

### タスク呼び出し方法

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

## トラブルシューティング

### celery-docワーカーが見つからない

```bash
# ワーカーステータス確認
docker exec ai-micro-api-doc python -c "
from app.tasks.celery_app import celery_app
inspect = celery_app.control.inspect()
print(inspect.active())
"

# celery-docが起動しているか確認
docker ps | grep celery-doc
```

### タスクがタイムアウトする

```bash
# Redis接続確認
docker exec ai-micro-api-doc redis-cli -h host.docker.internal -p 6379 -a <password> ping

# タスクキュー確認
docker exec ai-micro-api-doc redis-cli -h host.docker.internal -p 6379 -a <password> llen celery
```

### 軽量処理のエラー

```bash
# Tesseractインストール確認
docker exec ai-micro-api-doc tesseract --version

# PILインストール確認
docker exec ai-micro-api-doc python -c "from PIL import Image; print('OK')"
```

---

**作成日**: 2025-12-23
**更新日**: 2026-01-03
**ステータス**: ゲートウェイモードに移行完了
