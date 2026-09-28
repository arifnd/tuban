.DEFAULT_GOAL := help
SHELL := /bin/sh

.PHONY: help install env assets dev dev-css dev-js migrate revision downgrade seed seed-reset lint format check ci assets-check test coverage up down build logs ps restart clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

## Setup
install: ## Install Python (uv) and Node dependencies
	uv sync --extra dev
	npm install

env: ## Create a local .env with a generated secret if missing
	@test -f .env && echo "Using existing .env" || ( \
		cp .env.example .env && \
		uv run python -c "import pathlib, secrets; p = pathlib.Path('.env'); p.write_text(p.read_text().replace('AUTH_SESSION_SECRET=', 'AUTH_SESSION_SECRET=' + secrets.token_urlsafe(64)))" && \
		echo "Created .env with a generated AUTH_SESSION_SECRET" )

assets: ## Build frontend assets (icons + CSS + JS)
	npm run build:assets

## Development
dev: env ## Run the dev server with autoreload
	uv run uvicorn src.main:app --reload

dev-css: ## Rebuild CSS in watch mode
	npm run watch:css

dev-js: ## Rebuild JS in watch mode
	npm run watch:js

## Database
migrate: env ## Apply all migrations (upgrade head)
	uv run alembic upgrade head

revision: env ## Autogenerate a migration: make revision m="add x"
	uv run alembic revision --autogenerate -m "$(m)"

downgrade: env ## Roll back one migration
	uv run alembic downgrade -1

seed: env ## Load demo data
	uv run python -m scripts.seed

seed-reset: env ## Wipe and reseed demo data
	uv run python -m scripts.seed --reset

## Quality
lint: ## Lint src, tests and migrations
	uv run ruff check src tests alembic

format: ## Format and autofix
	uv run ruff format src tests alembic
	uv run ruff check --fix src tests alembic

ci: ## Run the exact CI pipeline locally (format + lint + tests with coverage)
	uv run ruff format --check src tests alembic
	uv run ruff check src tests alembic
	uv run pytest --cov -n auto

check: ci ## CI-style check (alias for `make ci`)

assets-check: ## Verify generated assets are committed and current
	npm run build:assets
	git diff --exit-code -- static/css/app.css static/js/app.min.js templates/partials/sprite.html templates/partials/icons.html

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
