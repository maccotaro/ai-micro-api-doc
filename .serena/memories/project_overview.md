# ai-micro-api-doc プロジェクト概要

## 目的

ドキュメント処理（OCR、レイアウト解析、階層構造変換、チャンク分割）に特化したマイクロサービス。
`ai-micro-api-admin` から分離されたドキュメント処理機能を提供。

## 技術スタック

| カテゴリ | 技術 |
|---------|------|
| フレームワーク | FastAPI |
| 言語 | Python 3.11+ |
| パッケージ管理 | Poetry |
| データベース | PostgreSQL (docdb) |
| タスクキュー | Celery + Redis |
| ドキュメント処理 | Docling 2.x |
| OCR | EasyOCR, Tesseract |
| 日本語処理 | MeCab |
| Embedding | LangChain + BGE-M3 |
| GPU | NVIDIA CUDA / Apple MPS |
| ポート | 8011 |

## ディレクトリ構造

```
ai-micro-api-doc/
├── app/
│   ├── main.py                      # FastAPIエントリーポイント
│   ├── core/
│   │   ├── config.py                # 設定（pydantic-settings）
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
├── tests/                           # テスト
├── models/                          # MLモデル（キャッシュ）
│   ├── docling/                     # Doclingモデル
│   └── easyocr/                     # EasyOCRモデル
├── Dockerfile                       # NVIDIA GPU版
├── Dockerfile.mac                   # M3 Mac CPU版
├── docker-compose.yml               # Docker設定
├── pyproject.toml                   # Poetry設定
└── CLAUDE.md                        # ドキュメント
```

## 主要API

| エンドポイント | 説明 |
|---------------|------|
| `POST /api/doc/process` | 同期ドキュメント処理 |
| `POST /api/doc/process/async` | 非同期処理（Celery） |
| `GET /api/doc/process/status/{task_id}` | タスクステータス確認 |
| `POST /api/doc/chunk` | テキストチャンク分割 |
| `POST /api/doc/ocr/crop` | 画像領域クロッピング |
| `POST /api/doc/ocr/ocr-region` | 特定領域OCR |

## 関連サービス

- **ai-micro-api-admin**: KB/Collection/Document管理
- **ai-micro-celery-doc**: Celeryワーカー（ドキュメント処理）
- **ai-micro-postgres**: PostgreSQL (docdb)
- **ai-micro-redis**: Redis (キャッシュ/タスクキュー)

## 最終更新: 2026-01-14
