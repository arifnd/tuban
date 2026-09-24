# Batik Helpdesk

A knowledge base + ticketing application: FastAPI + SQLAlchemy 2.0 async + Jinja2 /
HTMX / Alpine, Alembic migrations, Google (Gmail) OAuth2 SSO. SQLite by default, with
PostgreSQL supported in production via a single `DATABASE_URL`.

## Quickstart

```shell
cp .env.example .env
uv sync --extra dev
make migrate
make dev          # http://localhost:8000
```

Local environments show an email dev-login on `/auth/login`; production uses Google
SSO (`AUTH_GOOGLE_CLIENT_ID` / `AUTH_GOOGLE_CLIENT_SECRET`).

## Commands

`make dev` · `make migrate` · `make seed` · `make lint` · `make format` · `make test`
· `make coverage` · `make up` · `make down`

## Database

- Dev default: `sqlite+aiosqlite:///./instance/batik.db`
- Production: SQLite (mounted `instance/` volume) **or** PostgreSQL
  (`postgresql+asyncpg://…`) — set `DATABASE_URL`.
