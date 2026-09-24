# RBAC

Three roles, stored on `users.role`: **user** (requester), **agent**, **admin**.
Dependencies in `src/users/dependencies.py` (`require_role`) and
`src/tickets/dependencies.py` (`TicketEditor`, `TicketMember`) enforce this server-side.

| Capability | user | agent | admin |
|---|:--:|:--:|:--:|
| Browse public, published KB articles | ✓ | ✓ | ✓ |
| Read internal/draft KB articles | — | ✓ | ✓ |
| Search KB (visibility-scoped) | ✓ | ✓ | ✓ |
| Submit KB article feedback | ✓ | ✓ | ✓ |
| Manage KB categories/articles/tags/attachments | — | ✓ | ✓ |
| Create tickets | ✓ | ✓ | ✓ |
| View own/assigned tickets | ✓ | ✓ | ✓ |
| View all tickets | — | ✓ | ✓ |
| Comment on own/assigned tickets | ✓ | ✓ | ✓ |
| Post internal notes | — | ✓ | ✓ |
| Assign / claim / set priority | — | ✓ | ✓ |
| Transition status | close/reopen own | all legal | all legal |
| Attach files to tickets | ✓ (own) | ✓ | ✓ |
| Delete own comments/attachments | ✓ | ✓ | ✓ + others' |
| Notifications (own) | ✓ | ✓ | ✓ |
| Global search | own + public | all | all |
| Reports & exports | — | ✓ | ✓ |
| Activity audit page | — | — | ✓ |
| User management (roles, activation) | — | — | ✓ |

## Access rules

- **KB visibility**: `user` sees only `published` + `public` articles; internal and draft
  content is hidden at the query layer (404, not just hidden in UI).
- **Ticket membership**: a ticket is visible to its requester, its assignee, and any
  agent/admin. Non-members receive 403.
- **Status transitions**: an explicit transition map plus role rules; requesters may only
  confirm resolution (`resolved → closed`) and reopen. Agents/admins may perform any legal
  transition.
- **Private media**: `/media/{path}` authorizes per owning KB article visibility or ticket
  membership — never by login alone.
- **Last admin**: the last active admin cannot be demoted or deactivated.
