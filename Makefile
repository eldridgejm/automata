.PHONY: lint typecheck test coverage checks

checks: lint typecheck test coverage

lint:
	uv run ruff check

typecheck:
	uv run mypy src

test:
	uv run pytest

coverage:
	uv run pytest --cov=src --cov-report=term-missing
