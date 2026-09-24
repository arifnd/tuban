# Project Structure

Domain-based layout: one `src/{domain}/` package per bounded context.

```
tuban/
├── pyproject.toml            # deps + ruff/pytest/coverage config
├── uv.lock                   # lockfile (uv)
├── package.json              # Tailwind + esbuild + icon sprite scripts
├── tailwind.config.js
├── Makefile                  # dev / migrate / seed / lint / test / up / down
├── alembic.ini
├── logging.ini
├── .env.example
│
├── src/
│   ├── main.py               # app factory, routers, exception handlers, /health, /
│   ├── config.py             # global Settings (DATABASE_URL, APP_NAME, ...)
│   ├── database.py           # async engine + session factory + get_db
│   ├── models.py             # Base, mixins, enum_col
│   ├── exceptions.py         # global HTTP exceptions
│   ├── pagination.py         # clamp_per_page, paginate
│   ├── templating.py         # Jinja env, context processor, filters (t, md, highlight, dtf)
│   ├── middleware.py         # session decode, CSRF, headers, size guard
│   ├── logging_filters.py    # redact OAuth code/state/token in logs
│   ├── version.py
│   │
│   ├── auth/                 # router, service, dependencies, utils, config, constants, schemas, exceptions
│   ├── users/                # router, service, models, schemas, dependencies, constants, exceptions
│   ├── kb/                   # router, service, models, schemas, dependencies, markdown, utils, constants, exceptions
│   ├── tickets/              # router, service, models, schemas, dependencies, utils, constants, exceptions
│   ├── notifications/        # router, service, models, constants
│   ├── activity/             # router, service, models
│   ├── dashboard/            # router, service, schemas, utils
│   ├── search/               # router, service, schemas
│   ├── reports/              # router, service, schemas, exporters
│   └── storage/              # config, client, service, router
│
├── templates/
│   ├── base.html
│   ├── index.html            # public landing
│   ├── auth/login.html
│   ├── dashboard/            # index + partials/
│   ├── kb/                   # home, categories/, articles/, tags/, partials/
│   ├── tickets/              # list, form, detail, categories/, partials/
│   ├── notifications/        # index
│   ├── activity/             # list
│   ├── reports/              # index + partials/
│   ├── search/               # results
│   ├── errors/               # 404, 500
│   └── partials/             # navbar, footer, macros, pagination, icons, sprite, notifications/, dashboard/, search...
│
├── static/
│   ├── css/app.css           # built
│   ├── js/app.min.js         # built
│   └── i18n/en.json
├── resources/
│   ├── css/input.css         # Tailwind source
│   └── js/{main,app,charts,datepicker}.js
├── scripts/
│   ├── seed.py
│   ├── build-icons.mjs
│   └── icons.config.mjs
│
├── alembic/
│   ├── env.py                # async, render_as_batch for SQLite
│   ├── script.py.mako
│   └── versions/             # date-time-prefixed migrations
│
├── tests/                    # mirrors src/ + conftest.py
├── docker/                   # Dockerfile, docker-compose.yml, nginx/
├── docs/                     # architecture, erd, api-endpoints, project-structure, rbac
├── instance/                 # SQLite DB (mounted volume)
└── media/                    # uploaded files (mounted volume)
```

## Conventions

- **Domain packages** under `src/`; no repository layer (services query SQLAlchemy directly).
- **SQLite in dev**, PostgreSQL supported in prod — one `DATABASE_URL`.
- **Server-rendered** templates + HTMX + Alpine; no SPA build step.
- **Migrations**: static, reversible, `YYYYMMDD_HHMMSS_slug.py`.
- **Tests**: `httpx2.AsyncClient` + `ASGITransport` against a real database.
- Rebuild assets (`npm run build:assets`) after any CSS/JS/template-class change.
