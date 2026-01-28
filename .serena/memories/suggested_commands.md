# ai-micro-api-doc 開発コマンド

## 開発環境
```bash
poetry install
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8011 --reload
```

## コード品質
```bash
poetry run ruff check .
poetry run mypy app/
poetry run pytest
```

## Docker操作
```bash
# WSL2 + NVIDIA GPU
docker compose up -d

# M3 Mac
docker compose -f docker-compose.mac.yml up -d

# ログ
docker compose logs -f

# 再起動
docker compose restart
```

## API確認
- Swagger: http://localhost:8011/docs
- ヘルス: `curl http://localhost:8011/health`

## celery-doc確認
```bash
# ワーカーステータス
docker exec ai-micro-api-doc python -c "
from app.tasks.celery_app import celery_app
print(celery_app.control.inspect().active())
"

# celery-docが起動しているか
docker ps | grep celery-doc
```

## トラブルシューティング
```bash
# Tesseract確認
docker exec ai-micro-api-doc tesseract --version

# Redis接続確認
docker exec ai-micro-api-doc redis-cli -h host.docker.internal ping
```
