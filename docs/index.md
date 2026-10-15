# Tuban

A **knowledge base + ticketing** application built with a server-rendered stack:
**FastAPI + SQLAlchemy 2.0 async + Jinja2 / HTMX / Alpine**. It ships with Alembic
migrations, Google (Gmail) OAuth2 SSO, and a pluggable storage layer, and runs on
**SQLite (default)** or **PostgreSQL** via a single `DATABASE_URL`.

## Features

- **Knowledge base** — categories, Markdown articles with revision history and restore,
  tags, full-text search, attachments, and reader feedback.
- **Tickets** — categories, SLA-tracked tickets, threaded comments with internal notes,
  assignment, and a guarded status workflow.
- **Notifications & audit** — in-app notification bell and an admin activity log.
- **Dashboard, global search, and reports** (CSV / Excel / PDF) for agents and admins.
- **Auth** — Google SSO in production; email dev-login in local/test only.

## Documentation

- [Architecture](architecture.md) — stack, runtime flow, and domain boundaries.
- [ERD](erd.md) — entity relationship diagram.
- [API Endpoints](api-endpoints.md) — route reference grouped by domain.
- [Project Structure](project-structure.md) — the domain-based directory layout.
- [RBAC](rbac.md) — user / agent / admin access matrix.

## Quickstart

```shell
make env                                # create .env with a generated AUTH_SESSION_SECRET
uv sync --extra dev
npm install && npm run build:assets     # build CSS/JS/icon sprite
make migrate                            # alembic upgrade head
make seed                               # optional demo data
make dev                                # http://localhost:8000
```

## Building these docs

The site is built with [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/):

```shell
uv run --extra docs mkdocs serve --dev-addr 127.0.0.1:8001   # live-reload preview
uv run --extra docs mkdocs build --strict
```

Pushes to `main` that touch `docs/` or `mkdocs.yml` are built and deployed to
GitHub Pages by the `Docs` workflow.
