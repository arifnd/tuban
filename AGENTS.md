# AGENTS.md

Tuban: server-rendered FastAPI + SQLAlchemy 2.0 async + Jinja2/HTMX/Alpine app. Python 3.12, `uv` for Python, `npm` for frontend assets.

## Commands

- `make help` — list all targets.
- `make check` — CI-style: `ruff format --check` + `ruff check` + `pytest -n auto` (no coverage).
- `make coverage` — `pytest --cov -n auto` then `coverage report -m`.
- `make dev` — `uvicorn src.main:app --reload`.
- `uv run pytest tests/kb/test_articles.py::test_name -q` — single test (no `-n` needed).
- Always run `uv run`, not bare `python`/`pytest` (deps live in `.venv`).

## CI (`.github/workflows/test.yml`)

Exact order: `uv sync --extra dev` → `ruff format --check src tests alembic` → `ruff check src tests alembic` → `pytest --cov -n auto`. Coverage gate is `fail_under = 90` in `pyproject.toml`; a green test run can still fail CI on coverage. Ruff is line-length 160, double quotes.

## Testing

- Tests use a **real** SQLite DB (no mocks) via `httpx2.AsyncClient` + `ASGITransport`; suite runs under pytest-xdist (`-n auto`).
- `tests/conftest.py` sets `DATABASE_URL` to a **per-worker** file (`instance/test_gw<N>.db`) before importing `src`. Do not move imports above that env setup or workers share one DB file and produce `table ... already exists` / `no such table` races.
- `_db` fixture creates/drops all tables per test; `client` and `db` fixtures are the usual entrypoints.
- Helpers: `tests/tickets/helpers.py` (`login`, `make_user`, `make_ticket`, `csrf`) and `tests/kb/helpers.py`.
- CSRF is enforced on all non-GET requests. Tests read the token from the signed session cookie via `csrf(client.cookies)`; pass it as form field `_csrf`.

## Frontend assets (committed build output)

`static/css/app.css`, `static/js/app.min.js`, and `templates/partials/{sprite,icons}.html` are generated but tracked. After changing CSS, JS, or Tailwind classes in templates, run `npm run build:assets` (or `make assets`) and commit the regenerated files.

- New icon: add the project name → Lucide file mapping in `scripts/icons.config.mjs`, then `npm run build:icons`. Templates call `icon("name")`; the sprite/macro are generated.
- Classes chosen dynamically at runtime must be added to `safelist` in `tailwind.config.js`.
- Brand color is theme-driven: `--brand-*` CSS vars emitted in `base.html` from `src/settings/theme.py`; `tailwind.config.js` maps `brand-*` to them. `btn-primary` follows the active theme (default palette `green`).

## i18n

User-facing strings go through `t("key")` (`src/templating.py`). Default language is **`id`**. Add every new key to **both** `static/i18n/en.json` and `static/i18n/id.json`; missing keys silently fall back to the key itself.

## Architecture

- Domain packages under `src/{domain}/` (auth, users, kb, tickets, notifications, activity, dashboard, search, reports, settings, storage). Each has `router`/`service`/`models`; services query SQLAlchemy directly — no repository layer.
- Wiring: `src/main.py` (routers, `SecurityHeadersMiddleware`, lifespan loads runtime settings), `src/database.py` (engine/session), `src/templating.py` (Jinja env, global `t()`, `md`, `highlight`, `dtf` filters), `src/models.py` (`Base`, mixins, `enum_col`).
- Auth: Google OAuth2 in production; email dev-login is available **only** when `ENVIRONMENT=local` (test/local). `INITIAL_ADMIN_EMAIL` is granted admin on first login.
- Settings are DB-backed at runtime (`src/settings/service.py`); tests reset its cache via an autouse fixture.
- Dev-login and tests rely on `AUTH_SESSION_SECRET`; `src/config.py` loads `.env` and environment variables at import time.

## Database / migrations

- Dev default `sqlite+aiosqlite:///./instance/tuban.db`; PostgreSQL supported via `DATABASE_URL=postgresql+asyncpg://...`.
- `make migrate` (upgrade head), `make revision m="..."` (autogenerate), `make downgrade`.
- Keep schema portable across SQLite/Postgres: use `native_enum=False`, `Uuid`, `JSON`; Alembic runs in batch mode on SQLite (`render_as_batch`). Migrations must be static and reversible.

## Ignore

`example/` (symlink to an unrelated checkout), `tasks/`, `instance/`, and `media/` are local only.
