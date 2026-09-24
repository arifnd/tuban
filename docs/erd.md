# ERD

Entity relationship diagram (MermaidJS).

```mermaid
erDiagram
    users {
        uuid id PK
        string google_id UK
        string email UK
        string name
        string avatar
        string role
        boolean is_active
        datetime last_login
        datetime created_at
        datetime updated_at
    }

    kb_categories {
        uuid id PK
        string name
        string slug UK
        text description
        int position
    }
    kb_articles {
        uuid id PK
        string title
        string slug UK
        text summary
        text body
        uuid category_id FK
        uuid author_id FK
        string status
        string visibility
        int view_count
        datetime published_at
    }
    kb_article_revisions {
        uuid id PK
        uuid article_id FK
        uuid editor_id FK
        string title
        text body
        int revision_no
    }
    kb_tags {
        uuid id PK
        string name
        string slug UK
    }
    kb_article_tags {
        uuid article_id FK
        uuid tag_id FK
    }
    kb_attachments {
        uuid id PK
        uuid article_id FK
        string file_name
        string file_path
        string mime_type
        int size_bytes
        uuid uploaded_by FK
    }
    kb_article_feedback {
        uuid id PK
        uuid article_id FK
        uuid user_id FK
        boolean is_helpful
        text comment
    }

    ticket_categories {
        uuid id PK
        string name
        string slug UK
        int position
    }
    ticket_number_seq {
        int id PK
        int value
    }
    tickets {
        uuid id PK
        string ticket_number UK
        string subject
        text description
        uuid requester_id FK
        uuid assignee_id FK
        uuid category_id FK
        string status
        string priority
        string source
        datetime sla_due_at
        datetime resolved_at
        datetime closed_at
    }
    ticket_comments {
        uuid id PK
        uuid ticket_id FK
        uuid author_id FK
        text body
        boolean is_internal
    }
    ticket_attachments {
        uuid id PK
        uuid ticket_id FK
        uuid comment_id FK
        string file_name
        string file_path
        string mime_type
        int size_bytes
        uuid uploaded_by FK
    }

    notifications {
        uuid id PK
        uuid user_id FK
        string type
        string title
        text body
        string link
        boolean is_read
        datetime read_at
        datetime created_at
    }
    activity_logs {
        uuid id PK
        uuid user_id FK
        uuid ticket_id FK
        string action
        string entity_type
        uuid entity_id
        json old_data
        json new_data
        datetime created_at
    }

    users ||--o{ kb_articles : "authors"
    kb_categories ||--o{ kb_articles : "groups"
    kb_articles ||--o{ kb_article_revisions : "revises"
    kb_articles ||--o{ kb_attachments : "has"
    kb_articles ||--o{ kb_article_feedback : "rated"
    kb_articles ||--o{ kb_article_tags : "tagged"
    kb_tags ||--o{ kb_article_tags : "labels"

    users ||--o{ tickets : "requests"
    users ||--o{ tickets : "assigned"
    ticket_categories ||--o{ tickets : "classifies"
    tickets ||--o{ ticket_comments : "has"
    tickets ||--o{ ticket_attachments : "has"
    ticket_comments ||--o{ ticket_attachments : "has"
    users ||--o{ notifications : "receives"
    users ||--o{ activity_logs : "acts"
    tickets ||--o{ activity_logs : "activity"
```

## Notes

- UUID primary keys, PostgreSQL naming conventions; `created_at`/`updated_at` on most tables.
- Enums are stored as `VARCHAR` with check constraints (`native_enum=False`) for SQLite/Postgres parity.
- `activity_logs.entity_type` + `entity_id` reference any record (loose, not a hard FK).
- `ticket_number_seq` is a single-row counter for `TKT-000123` numbers.
- Indexes: tickets `(status, updated_at)`, `(assignee_id, status)`, `(sla_due_at)`;
  notifications `(user_id, is_read, created_at)`; activity `(entity_type, entity_id)`, `(created_at)`.
