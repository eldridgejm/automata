.PHONY: lint typecheck test integration-test coverage checks fix

checks: lint typecheck test coverage

lint:
	uv run ruff check

typecheck:
	uv run mypy src

test:
	uv run pytest

integration-test:
	uv run pytest -m integration

coverage:
	uv run pytest --cov=src --cov-report=term-missing

fix:
	uv run ruff check --fix
