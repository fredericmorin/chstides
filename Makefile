.PHONY: dev test lint format

dev:
	@bash scripts/dev_instance.sh

test:
	pytest tests/ -v

lint:
	ruff check custom_components/ tests/

format:
	ruff format custom_components/ tests/
