# ai-micro-api-doc - ドキュメント処理サービス

## 概要

このサービスは、ドキュメント処理（OCR、レイアウト解析、階層構造変換、チャンク分割）に特化したマイクロサービスです。
`ai-micro-api-admin`から分離されたドキュメント処理機能を提供します。

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ドキュメント処理パイプライン                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Step 1: ファイルアップロード                                                │
│     └── ファイル保存・バリデーション                                         │
│                                                                             │
│  Step 2: Doclingレイアウト解析                                               │
│     └── ページ構造・要素検出                                                 │
│                                                                             │
│  Step 3: 階層構造変換                                                        │
│     ├── LOGICAL_ORDERING（論理的読み順序）                                   │
│     ├── SPATIAL_HIERARCHY（空間的階層構造）                                  │
│     └── SEMANTIC_HIERARCHY（意味的階層構造）                                 │
│                                                                             │
│  Step 4: OCR処理                                                             │
│     ├── EasyOCR（日本語・英語）                                              │
│     └── Tesseract（フォールバック）                                          │
│                                                                             │
│  Step 5: 画像処理                                                            │
│     ├── ページ画像生成（144 DPI）                                            │
│     ├── 図表クロッピング                                                     │
│     └── アノテーション描画                                                   │
│                                                                             │
│  Step 6: チャンク分割                                                        │
│     └── RecursiveCharacterTextSplitter                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 技術スタック

- **フレームワーク**: FastAPI
- **言語**: Python 3.11+
- **データベース**: PostgreSQL（docdb）
- **タスクキュー**: Celery + Redis
- **ドキュメント処理**: Docling 2.15+
- **OCR**: EasyOCR, Tesseract
- **日本語処理**: MeCab

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
│   │   └── processor/               # ドキュメント処理モジュール
│   │       ├── base.py              # メインプロセッサ
│   │       ├── docling_processor.py # Docling処理
│   │       ├── layout_extractor.py  # レイアウト抽出
│   │       ├── hierarchy_converter.py # 階層構造変換
│   │       ├── image_processor.py   # 画像処理
│   │       ├── image_cropper.py     # 画像クロッピング
│   │       ├── text_extractor.py    # テキスト抽出
│   │       └── region_ocr_processor.py # 領域OCR
│   ├── routers/
│   │   ├── process.py               # 処理API
│   │   └── ocr.py                   # OCR API
│   ├── schemas/                     # Pydanticスキーマ
│   ├── models/                      # SQLAlchemyモデル
│   └── tasks/                       # Celeryタスク
│       ├── celery_app.py            # Celeryアプリ
│       └── document_tasks.py        # ドキュメント処理タスク
├── tests/
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
  - 処理サービスのステータス確認

POST /api/doc/process
  - ドキュメント処理（同期）
  - リクエスト: multipart/form-data (file)
  - レスポンス: DocumentProcessResponse

POST /api/doc/process/async
  - ドキュメント処理（非同期・Celery）
  - リクエスト: multipart/form-data (file, callback_url)
  - レスポンス: task_id

GET  /api/doc/process/status/{task_id}
  - 非同期タスクのステータス確認

POST /api/doc/chunk
  - テキストのチャンク分割
  - リクエスト: text, chunk_size, chunk_overlap
  - レスポンス: chunks[]
```

### OCR API (`/api/doc/ocr`)

```
POST /api/doc/ocr/crop
  - 画像領域のクロッピング

GET  /api/doc/ocr/images/{document_id}/{path}
  - 処理済み画像の取得

GET  /api/doc/ocr/metadata/{document_id}
  - OCRメタデータの取得

PUT  /api/doc/ocr/metadata/{document_id}
  - OCRメタデータの更新

POST /api/doc/ocr/save-cropped-image
  - クロップ画像の永続保存

POST /api/doc/ocr/ocr-region
  - 特定領域のOCR実行
```

## 環境変数

| 変数 | 説明 | デフォルト |
|------|------|-----------|
| `DATABASE_URL` | PostgreSQL接続URL | `postgresql://postgres:password@localhost:5432/docdb` |
| `REDIS_URL` | Redis接続URL | `redis://:password@localhost:6379/1` |
| `CELERY_BROKER_URL` | Celeryブローカー | `redis://:password@localhost:6379/1` |
| `CELERY_RESULT_BACKEND` | Celery結果バックエンド | `redis://:password@localhost:6379/2` |
| `JWKS_URL` | 認証サービスJWKS URL | - |
| `DOCLING_DEVICE` | Docling処理デバイス | `cuda` |
| `OCR_GPU_ENABLED` | GPU OCR有効化 | `true` |
| `STORAGE_BASE_PATH` | ドキュメント保存パス | `/data/documents` |
| `ADMIN_SERVICE_URL` | api-adminコールバック用URL | `http://localhost:8003` |

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

## 開発

```bash
# 依存関係インストール
poetry install

# 開発サーバー起動
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8011 --reload

# Celeryワーカー起動
poetry run celery -A app.tasks worker --loglevel=info

# テスト実行
poetry run pytest

# 型チェック
poetry run mypy app/
```

## api-adminとの関係

このサービスは`ai-micro-api-admin`のドキュメント処理機能を分離したものです：

- **api-admin**: KB/Collection/Document管理、CRUD操作
- **api-doc**: ドキュメント処理、OCR、レイアウト解析（このサービス）

api-adminは内部的にこのサービスを呼び出し、既存APIの互換性を維持します。

```
front-admin → api-admin → api-doc
              (プロキシ)   (実処理)
```

## 出力ディレクトリ構造

ドキュメント処理後の出力:

```
{document_id}/
├── original/                 # 元ドキュメント
├── images/                   # ページ画像
│   ├── page_001.png
│   ├── page_002.png
│   └── ...
├── layout/                   # レイアウトJSON
│   ├── page_001_layout.json
│   └── ...
├── text/                     # 抽出テキスト
│   ├── page_001.txt
│   └── ...
├── figures/                  # クロップ済み図表
│   ├── figure_001.png
│   └── ...
├── cropped/                  # ユーザークロップ画像
│   └── text/
│       └── {element_id}.png
├── metadata.json             # 処理メタデータ
└── metadata_hierarchy.json   # 階層構造メタデータ
```

## Celeryタスク

| タスク | 説明 | キュー |
|--------|------|--------|
| `process_document_task` | ドキュメント全体の処理 | default |
| `chunk_document_task` | テキストチャンク分割 | default |
| `ocr_region_task` | 特定領域のOCR | default |

## トラブルシューティング

### Doclingが起動しない

```bash
# Doclingキャッシュを確認
docker exec ai-micro-api-doc ls -la /tmp/.docling_cache/

# GPUが認識されているか確認
docker exec ai-micro-api-doc python -c "import torch; print(torch.cuda.is_available())"
```

### OCRエラー

```bash
# Tesseractインストール確認
docker exec ai-micro-api-doc tesseract --version

# 日本語データ確認
docker exec ai-micro-api-doc ls /usr/share/tesseract-ocr/5/tessdata/jpn*
```

### メモリエラー

```bash
# docker-compose.ymlのメモリ制限を増加
deploy:
  resources:
    limits:
      memory: 16G
```

---

**作成日**: 2025-12-23
**ステータス**: 初期実装完了
