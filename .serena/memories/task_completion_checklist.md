# タスク完了時のチェックリスト

## コード変更後

### 1. 型チェック

```bash
poetry run mypy app/
```

### 2. リント

```bash
poetry run ruff check .
```

エラーがある場合：

```bash
poetry run ruff check . --fix
```

### 3. フォーマット

```bash
poetry run black app/
```

### 4. テスト実行

```bash
poetry run pytest
```

## ファイル追加・変更時

### ファイルサイズ確認

- 500行を超えないことを確認
- 超える場合はリファクタリングを実施

### import整理

Ruffが自動で行うが、手動確認も可能：

```bash
poetry run ruff check . --select I --fix
```

## Docker関連の変更後

### 再ビルド

```bash
docker compose build
docker compose up -d
```

### ログ確認

```bash
docker logs ai-micro-api-doc -f
```

### ヘルスチェック

```bash
curl http://localhost:8011/health
```

## Git操作前

### 変更確認

```bash
git status
git diff
```

### コミット形式

Conventional Commits形式：

- `feat:` - 新機能
- `fix:` - バグ修正
- `docs:` - ドキュメント
- `style:` - フォーマット
- `refactor:` - リファクタリング
- `test:` - テスト
- `chore:` - その他

## CLAUDE.md更新

以下の変更時はCLAUDE.mdも更新：

- [ ] 新しいAPIエンドポイント追加
- [ ] 新しいディレクトリ/ファイル追加
- [ ] 環境変数の追加/変更
- [ ] 技術スタック変更
- [ ] 重要なアーキテクチャ変更
