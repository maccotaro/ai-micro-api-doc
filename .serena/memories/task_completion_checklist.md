# ai-micro-api-doc タスク完了チェックリスト

## コード変更後
```bash
poetry run ruff check .
poetry run mypy app/
docker compose restart
curl http://localhost:8011/health
```

## 変更タイプ別

### 軽量処理変更
- [ ] ImageCropper/RegionOCRProcessor変更
- [ ] Tesseract/PIL動作確認

### Celeryタスク連携変更
- [ ] タスク名・引数確認
- [ ] celery-docとの連携確認

### API変更
- [ ] Swagger確認
- [ ] api-adminからの呼び出し確認

## 依存サービス確認
- [ ] celery-doc: 重い処理の委譲
- [ ] api-admin: 呼び出し元
- [ ] Redis: タスクキュー
