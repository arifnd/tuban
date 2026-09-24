# Tuban

A knowledge base + ticketing application: **FastAPI + SQLAlchemy 2.0 async + Jinja2 /
HTMX / Alpine**, with Alembic migrations, Google (Gmail) OAuth2 SSO, and a pluggable
storage layer. Runs on **SQLite (default)** or **PostgreSQL** via one `DATABASE_URL`.

## Features

- **Knowledge base** — categories, Markdown articles with revision history and restore,
  tags, full-text search, attachments, and reader feedback.
- **Tickets** — categories, SLA-tracked tickets, threaded comments with internal notes,
  assignment, and a guarded status workflow.
- **Notifications & audit** — in-app notification bell and an admin activity log.
- **Dashboard, global search, and reports** (CSV / Excel / PDF) for agents and admins.
- **Auth** — Google SSO in production; email dev-login in local/test only.

## Quickstart

```shell
cp .env.example .env
uv sync --extra dev
npm install && npm run build:assets     # build CSS/JS/icon sprite
make migrate                            # alembic upgrade head
make seed                               # optional demo data
make dev                                # http://localhost:8000
```

Local environments show an email dev-login on `/auth/login`. Production uses Google SSO
(`AUTH_GOOGLE_CLIENT_ID` / `AUTH_GOOGLE_CLIENT_SECRET`).

## Commands

`make help` lists everything. Common targets:

| Target | Purpose |
|--------|---------|
| `make install` | `uv sync` + `npm install` |
| `make assets` | Build icons, CSS, and JS |
| `make dev` | Run the app with autoreload |
| `make migrate` / `make revision m="..."` / `make downgrade` | Migrations |
| `make seed` / `make seed-reset` | Demo data |
| `make lint` / `make format` / `make check` | ruff + tests |
| `make test` / `make coverage` | pytest |
| `make up` / `make down` / `make logs` | Docker Compose |

## Database

- **Dev default**: `sqlite+aiosqlite:///./instance/tuban.db`
- **Production**: SQLite (mounted `instance/` volume) **or** PostgreSQL
  (`postgresql+asyncpg://…`) — set `DATABASE_URL`. The schema uses portable types
  (`native_enum=False`, `Uuid`, `JSON`) and migrations run in batch mode on SQLite.

## Deployment

```shell
# SQLite (default)
docker compose -f docker/docker-compose.yml up -d

# PostgreSQL
DATABASE_URL=postgresql+asyncpg://tuban:tuban@db:5432/tuban \
  docker compose -f docker/docker-compose.yml --profile postgres up -d
```

The container runs `alembic upgrade head` before starting uvicorn, behind nginx, with
`instance/` and `media/` on named volumes. Upgrade path: migrate before swapping the
image.

## Documentation

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/erd.md`](docs/erd.md)
- [`docs/api-endpoints.md`](docs/api-endpoints.md)
- [`docs/project-structure.md`](docs/project-structure.md)
- [`docs/rbac.md`](docs/rbac.md)
