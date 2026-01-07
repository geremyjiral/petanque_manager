.PHONY: help install dev run test lint format typecheck clean lock

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	uv sync

dev: ## Install all dependencies (including dev)
	uv sync --all-extras

run: ## Run the Streamlit application
	uv run streamlit run app.py

test: ## Run tests
	uv run pytest

test-cov: ## Run tests with coverage
	uv run pytest --cov=src --cov-report=html --cov-report=term-missing

lint: ## Run linting checks
	uv run ruff check .

format: ## Format code
	uv run ruff format .

format-check: ## Check code formatting
	uv run ruff format --check .

typecheck: ## Run type checking
	uv run mypy src/ app.py pages/ --ignore-missing-imports

check: lint format-check typecheck test ## Run all checks (lint, format, typecheck, test)

clean: ## Clean up generated files
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	rm -rf **/__pycache__ **/*.pyc **/*.pyo
	rm -f tournament.db tournament_data.json

lock: ## Update uv.lock file
	uv lock

upgrade: ## Upgrade all dependencies
	uv lock --upgrade
