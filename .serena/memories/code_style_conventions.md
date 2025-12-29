# コードスタイル・規約

## Python設定

- **Pythonバージョン**: 3.11+
- **行の最大長**: 120文字
- **ファイル最大行数**: 500行（制限）

## ツール設定

### Ruff（リンター）

```toml
[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "D", "UP", "B", "C4", "SIM"]
ignore = ["D100", "D104", "D107", "D203", "D213"]
```

- **E**: エラー（pycodestyle）
- **F**: Pyflakes
- **W**: 警告（pycodestyle）
- **I**: isort（import順）
- **N**: 命名規則（pep8-naming）
- **D**: Docstrings（pydocstyle）
- **UP**: pyupgrade
- **B**: flake8-bugbear
- **C4**: flake8-comprehensions
- **SIM**: flake8-simplify

### Black（フォーマッター）

デフォルト設定を使用。

### mypy（型チェック）

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_ignores = true
disallow_untyped_defs = true
ignore_missing_imports = true
```

## 命名規則

| 対象 | 規則 | 例 |
|------|------|-----|
| クラス | PascalCase | `DocumentProcessor` |
| 関数/メソッド | snake_case | `process_document()` |
| 変数 | snake_case | `document_id` |
| 定数 | UPPER_SNAKE | `MAX_FILE_SIZE` |
| プライベート | _prefix | `_internal_method()` |
| モジュール | snake_case | `layout_extractor.py` |

## 型ヒント

- **必須**: 全ての関数・メソッドの引数と戻り値に型ヒントを付ける
- ジェネリクスは `list[str]`, `dict[str, Any]` 形式（3.9+スタイル）

```python
def process_document(
    file_path: str,
    options: dict[str, Any] | None = None,
) -> ProcessResult:
    ...
```

## Docstrings

Google Styleを使用：

```python
def process_document(file_path: str, options: dict[str, Any] | None = None) -> ProcessResult:
    """ドキュメントを処理する。

    Args:
        file_path: 処理するファイルのパス
        options: 処理オプション（オプション）

    Returns:
        処理結果

    Raises:
        FileNotFoundError: ファイルが見つからない場合
    """
```

## import順序

isort/Ruffで自動整列。順序：

1. 標準ライブラリ
2. サードパーティ
3. ローカルモジュール

```python
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.services.processor import DocumentProcessor
```

## FastAPIパターン

### ルーター構成

```python
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(
    prefix="/api/doc",
    tags=["Document Processing"],
)

@router.post("/process", response_model=ProcessResponse)
async def process_document(
    file: UploadFile,
    current_user: dict = Depends(get_current_user),
) -> ProcessResponse:
    ...
```

### 例外処理

```python
from fastapi import HTTPException, status

raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Document not found",
)
```

## Pydanticスキーマ

```python
from pydantic import BaseModel, Field

class DocumentRequest(BaseModel):
    file_path: str = Field(..., description="ファイルパス")
    chunk_size: int = Field(default=500, ge=100, le=2000)

    model_config = {"from_attributes": True}
```

## SQLAlchemyモデル

```python
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid

class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
```
