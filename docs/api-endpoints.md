# API Endpoints

Server-rendered routes. Mutating routes require a valid CSRF token (`_csrf` form field
or `X-CSRF-Token` header). Roles: **user** < **agent** < **admin**.

## Auth (`/auth`)

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| GET | `/auth/login` | public | Login page; `?google=1` starts OAuth |
| GET | `/auth/callback` | public | Google OAuth callback |
| POST | `/auth/dev-login` | local/test | Email dev-login |
| POST | `/auth/logout` | any | Clear session |

## Users (`/users`, `/profile`)

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| GET | `/users` | admin | List/search/filter users |
| GET | `/users/{id}` | admin | User detail |
| POST | `/users/{id}/role` | admin | Change role |
| POST | `/users/{id}/active` | admin | Activate/deactivate |
| GET/POST | `/profile` | any | Self-service name |

## Knowledge base (`/kb`)

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| GET | `/kb` | any | KB home (categories, recent, popular) |
| GET | `/kb/categories` | agent/admin | Category management |
| POST | `/kb/categories` | agent/admin | Create category |
| POST | `/kb/categories/{id}` | agent/admin | Update category |
| POST | `/kb/categories/{id}/delete` | agent/admin | Delete category (blocked if articles) |
| GET | `/kb/categories/{slug}` | any | Articles in category |
| GET | `/kb/articles` | any | List with filters |
| GET | `/kb/articles/new` | agent/admin | Create form |
| POST | `/kb/articles` | agent/admin | Create article |
| GET | `/kb/articles/{slug}` | any (visibility) | Article detail |
| GET | `/kb/articles/{slug}/edit` | agent/admin | Edit form |
| POST | `/kb/articles/{slug}` | agent/admin | Update article |
| POST | `/kb/articles/{slug}/status` | agent/admin | Publish/archive/draft |
| GET | `/kb/articles/{slug}/history` | agent/admin | Revision list |
| POST | `/kb/articles/{slug}/restore/{revision_id}` | agent/admin | Restore revision |
| POST | `/kb/articles/{slug}/attachments` | agent/admin | Upload attachment |
| POST | `/kb/articles/{slug}/attachments/{id}/delete` | agent/admin | Delete attachment |
| POST | `/kb/articles/{slug}/feedback` | any | Submit helpful/not-helpful |
| GET | `/kb/search` | any | KB search |
| GET | `/kb/tags` | agent/admin | Tag management |
| GET | `/kb/tags/{slug}` | any | Articles by tag |
| POST | `/kb/tags/{id}/delete` | agent/admin | Delete tag |

## Tickets (`/tickets`)

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| GET | `/tickets` | any | List (scoped by role) |
| GET | `/tickets/partials/list` | any | HTMX list fragment |
| GET | `/tickets/new` | any | Create form |
| POST | `/tickets` | any | Create ticket |
| GET | `/tickets/categories` | agent/admin | Category management |
| POST | `/tickets/categories` | agent/admin | Create category |
| POST | `/tickets/categories/{id}` | agent/admin | Update category |
| POST | `/tickets/categories/{id}/delete` | agent/admin | Delete category |
| GET | `/tickets/agents` | agent/admin | Agent list (JSON) |
| GET | `/tickets/{id}` | member | Ticket detail + timeline |
| POST | `/tickets/{id}/comments` | member | Reply / internal note |
| POST | `/tickets/{id}/comments/{cid}/delete` | author/staff | Delete comment |
| POST | `/tickets/{id}/assign` | agent/admin | Assign/unassign |
| POST | `/tickets/{id}/claim` | agent/admin | Self-assign |
| POST | `/tickets/{id}/status` | member (rules) | Transition status |
| POST | `/tickets/{id}/priority` | agent/admin | Change priority |
| POST | `/tickets/{id}/close` | member (rules) | Close |
| POST | `/tickets/{id}/reopen` | member (rules) | Reopen |
| POST | `/tickets/{id}/attachments` | member | Upload attachment |
| POST | `/tickets/{id}/attachments/{aid}/delete` | uploader/staff | Delete attachment |

## Notifications (`/notifications`)

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| GET | `/notifications` | any | List page |
| GET | `/notifications/partial` | any | Bell dropdown fragment |
| GET | `/notifications/api` | any | JSON (typeahead) |
| POST | `/notifications/read-many` | any | Mark selected read |
| POST | `/notifications/read-all` | any | Mark all read |
| POST | `/notifications/{id}/read` | any | Mark one read |
| GET | `/notifications/{id}/open` | any | Mark read + redirect to link |

## Activity, Search, Reports, Media

| Method | Path | Access | Purpose |
|--------|------|--------|---------|
| GET | `/activity` | admin | Audit log with filters |
| GET | `/search` | any | Global results page |
| GET | `/search/partials/dropdown` | any | Global search dropdown |
| GET | `/search/api` | any | Global search JSON |
| GET | `/reports` | agent/admin | Report index |
| GET | `/reports/partials/{report}` | agent/admin | Report table fragment |
| GET | `/reports/export` | agent/admin | CSV / XLSX / PDF download |
| GET | `/media/{path}` | authorized | Private file serving |
| GET | `/health` | public | Health check |
