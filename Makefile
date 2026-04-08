.PHONY: dev test lint format

dev:
	@bash scripts/dev_instance.sh

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check

format:
	uv run ruff format
	uv run ruff check --fix
