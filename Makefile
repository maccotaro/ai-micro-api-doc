.PHONY: test test-unit test-cov lint format type-check

# Run all tests
test:
	poetry run pytest

# Run unit tests only
test-unit:
	poetry run pytest tests/unit -v

# Run tests with coverage
test-cov:
	poetry run pytest --cov=app --cov-report=html --cov-report=term

# Run linting
lint:
	poetry run ruff check .

# Run formatter
format:
	poetry run black .
	poetry run ruff check --fix .

# Run type checking
type-check:
	poetry run mypy app/
