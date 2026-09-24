.DEFAULT_GOAL := help
SHELL := /bin/sh

.PHONY: help install assets dev dev-css dev-js migrate revision downgrade seed seed-reset lint format check test coverage up down build logs ps restart clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

## Setup
install: ## Install Python (uv) and Node dependencies
	uv sync --extra dev
	npm install

assets: ## Build frontend assets (icons + CSS + JS)
	npm run build:assets

## Development
dev: ## Run the dev server with autoreload
	uv run uvicorn src.main:app --reload

dev-css: ## Rebuild CSS in watch mode
	npm run watch:css

dev-js: ## Rebuild JS in watch mode
	npm run watch:js

## Database
migrate: ## Apply all migrations (upgrade head)
	uv run alembic upgrade head

revision: ## Autogenerate a migration: make revision m="add x"
	uv run alembic revision --autogenerate -m "$(m)"

downgrade: ## Roll back one migration
	uv run alembic downgrade -1

seed: ## Load demo data
	uv run python -m scripts.seed

seed-reset: ## Wipe and reseed demo data
	uv run python -m scripts.seed --reset

## Quality
lint: ## Lint src, tests and migrations
	uv run ruff check src tests alembic

format: ## Format and autofix
	uv run ruff format src tests alembic
	uv run ruff check --fix src tests alembic

check: ## CI-style check (format check + lint + tests)
	uv run ruff format --check src tests alembic
	uv run ruff check src tests alembic
	uv run pytest -n auto

test: ## Run the test suite
	uv run pytest -n auto

coverage: ## Run tests with coverage report
	uv run pytest --cov -n auto
	uv run coverage report -m

## Docker
up: ## Start the stack (app + nginx)
	docker compose -f docker/docker-compose.yml up -d

down: ## Stop the stack
	docker compose -f docker/docker-compose.yml down

build: ## Build the application image
	docker compose -f docker/docker-compose.yml build

logs: ## Tail stack logs
	docker compose -f docker/docker-compose.yml logs -f

ps: ## Show running services
	docker compose -f docker/docker-compose.yml ps

restart: down up ## Restart the stack

## Cleanup
clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
