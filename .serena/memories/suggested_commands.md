# 推奨コマンド集

## 開発環境

### 依存関係のインストール

```bash
poetry install
```

### 開発サーバー起動

```bash
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8011 --reload
```

### Celeryワーカー起動

```bash
poetry run celery -A app.tasks worker --loglevel=info
```

## Docker操作

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

### ログ確認

```bash
docker logs ai-micro-api-doc -f
```

### コンテナに入る

```bash
docker exec -it ai-micro-api-doc bash
```

### 再ビルド

```bash
docker compose build --no-cache
docker compose up -d
```

## テスト

### 全テスト実行

```bash
poetry run pytest
```

### カバレッジ付き

```bash
poetry run pytest --cov=app --cov-report=html
```

### 特定テスト

```bash
poetry run pytest tests/unit/test_processor.py -v
```

## コード品質

### リンター（Ruff）

```bash
poetry run ruff check .
poetry run ruff check . --fix  # 自動修正
```

### フォーマッター（Black）

```bash
poetry run black app/
```

### 型チェック（mypy）

```bash
poetry run mypy app/
```

## デバッグ

### GPU確認

```bash
docker exec ai-micro-api-doc python -c "import torch; print(torch.cuda.is_available())"
```

### Doclingキャッシュ確認

```bash
docker exec ai-micro-api-doc ls -la /tmp/.docling_cache/
```

### EasyOCRモデル確認

```bash
docker exec ai-micro-api-doc ls -la /tmp/.easyocr_models/
```

### Tesseract日本語データ確認

```bash
docker exec ai-micro-api-doc tesseract --list-langs
```

## Git操作

```bash
git status
git add .
git commit -m "feat: 機能追加"
git push origin main
```

## ユーティリティ

### ファイル検索

```bash
find . -name "*.py" -type f
```

### パターン検索

```bash
grep -r "pattern" app/
```

### ディレクトリサイズ

```bash
du -sh models/
```
