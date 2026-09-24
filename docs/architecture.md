# Architecture

Tuban Helpdesk is a knowledge base and ticketing application. It is server-rendered
(FastAPI + Jinja2 + HTMX + Alpine) with an async SQLAlchemy 2.0 data layer that runs on
SQLite or PostgreSQL unchanged.

## Stack

| Layer         | Technology                                                        |
|---------------|-------------------------------------------------------------------|
| Language      | Python 3.12+                                                      |
| Web framework | FastAPI (>=0.115)                                                 |
| Templates     | Jinja2, server-rendered, HTMX + Alpine.js                         |
| ORM           | SQLAlchemy 2.0 async (`AsyncSession`)                             |
| Migrations    | Alembic (async template, batch mode for SQLite)                   |
| Database      | SQLite (`aiosqlite`, dev/prod) **or** PostgreSQL (`asyncpg`)      |
| Auth          | Google OAuth2 (authlib) + email dev-login; PyJWT session cookie   |
| Markdown      | `markdown-it-py` rendered, `nh3` sanitized                        |
| Files         | Pluggable local disk / S3-compatible (boto3) storage              |
| Reports       | `openpyxl` (XLSX), `reportlab` (PDF), CSV                         |
| Lint/format   | ruff                                                              |
| Tests         | pytest + pytest-asyncio, `httpx2` `ASGITransport`                 |
| Frontend      | Tailwind CSS + esbuild, self-hosted Lucide icon sprite            |

## Runtime flow

1. `uvicorn src.main:app` loads `src/main.py`, registers domain routers and the
   `SecurityHeadersMiddleware`.
2. The middleware decodes the signed session JWT into `request.state`, enforces
   double-submit CSRF on non-GET requests, rejects oversized bodies, and sets security
   headers (CSP, X-Frame-Options, nosniff, HSTS in production).
3. Routes depend on `CurrentUser` / `OptionalUser` / role dependencies
   (`src/auth/dependencies.py`, `src/users/dependencies.py`), which load the user and
   compute `unread_notifications`.
4. Handlers call domain services against an `AsyncSession` from `src/database.py`.
5. `src/templating.py` renders Jinja templates; its context processor exposes
   `current_user`, `csrf`, `is_admin`, and `unread_notifications` everywhere.

## Domain boundaries

```
src/auth          Google OAuth2 login, sessions, CSRF
src/users         Accounts, roles (user/agent/admin), profile
src/kb            Knowledge base: categories, articles, revisions, tags, attachments, feedback
src/tickets       Tickets: categories, tickets, comments, attachments, workflow, SLA
src/notifications In-app notifications (navbar bell + list page)
src/activity      Activity log / audit trail
src/dashboard     Role-scoped stats and charts
src/search        Cross-domain search (KB + tickets)
src/reports       Operational reports + CSV/XLSX/PDF export
src/storage       Pluggable local/S3 file storage and private media serving
```

Services query SQLAlchemy directly (no repository layer). Cross-domain imports use the
module name (`from src.tickets import service as ticket_service`).

## Data model

Full ERD in [`erd.md`](erd.md). Tables: `users`, `kb_categories`, `kb_articles`,
`kb_article_revisions`, `kb_tags`, `kb_article_tags`, `kb_attachments`,
`kb_article_feedback`, `ticket_categories`, `tickets`, `ticket_comments`,
`ticket_attachments`, `ticket_number_seq`, `notifications`, `activity_logs`.

## Async decisions

- All routes are `async def` and use async ORM I/O. Blocking work (boto3, openpyxl,
  reportlab, file writes) runs via `asyncio.to_thread`.
- Notifications and activity rows are flushed with the triggering request and committed
  atomically — no queue/worker.
