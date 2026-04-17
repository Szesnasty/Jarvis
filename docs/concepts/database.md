---
title: Database Layer
status: active
type: concept
sources:
  - backend/models/database.py
  - backend/models/schemas.py
  - backend/main.py
depends_on: []
last_reviewed: 2026-04-17
last_updated: 2026-04-17
---

# Database Layer

## Summary

Jarvis uses SQLite as an operational index and cache over the user's local Markdown files. It exists to make search and retrieval fast — not to own user data. The canonical source of truth is always the Markdown files in `Jarvis/memory/`. If the database file (`jarvis.db`) is deleted, it can be fully rebuilt by re-indexing those files. Nothing is stored exclusively in SQLite.

## How It Works

### The Source-of-Truth Rule

Every write to user knowledge ends with a Markdown file on disk. SQLite is populated as a side effect of that write, not before it. If the database and the Markdown files ever diverge, the Markdown files win. This means services never query SQLite for the content of a note and trust it unconditionally — the Markdown file is always the authoritative version.

### Schema and Full-Text Search

The main table is `notes`, which stores indexed metadata for each Markdown file: its path, title, folder, tags, frontmatter, a content preview, the full body text, word count, and timestamps. The `path` column is unique — it is the stable identifier linking a SQLite row to its corresponding file on disk.

On top of `notes`, the schema creates an FTS5 virtual table (`notes_fts`) that indexes the `title`, `body`, and `tags` columns. SQLite triggers (`notes_ai`, `notes_au`, `notes_ad`) keep the FTS index in sync automatically after every insert, update, or delete on `notes`. This means full-text search is always up to date without any manual sync step.

The same initialization path also provisions operational tables for Jira ingest and local enrichment (`issues`, related Jira join tables, `enrichments`, and `enrichment_queue`). These tables are indexes and caches over Markdown sources, not canonical user data stores.

### Initialization

The database is initialized on server startup via a FastAPI `lifespan` handler in `main.py`, before any request is served. The `init_database(db_path)` function handles both first-time creation and upgrades for existing databases. It creates the `notes` table (idempotently, using `CREATE TABLE IF NOT EXISTS`), then checks for the `body` column separately and adds it via `ALTER TABLE` if it is absent — this is a forward-compatibility migration for databases created before the `body` column was introduced.

After ensuring the schema is correct, `init_database` checks whether the existing FTS table already indexes the `body` column. If it does not (an older FTS schema), it drops the FTS table and all three triggers before recreating them. This ensures the FTS index always covers the full note body and does not silently remain on an outdated schema.

### Pydantic Schemas

`schemas.py` defines all request and response models used across the API. These are pure data-transfer objects — they do not map directly to database rows. Serialization and deserialization between SQLite rows, Markdown files, and API responses is handled by individual services, not by the schema models.

## Key Files

- `backend/models/database.py` — Defines the SQLite schema, FTS virtual table, sync triggers, and the `init_database` async function that creates or migrates the database on first use.
- `backend/models/schemas.py` — Pydantic models for all API request and response bodies across every router.
- `backend/main.py` — FastAPI application factory and lifespan hook; initializes the database on startup and starts background workers that depend on DB state.
- `backend/services/memory_service.py` — The primary caller of `init_database`; triggers database creation the first time notes are read or indexed.

## API / Interface

### `init_database(db_path: Path) -> None`

Async function. Creates the database file and all schema objects if they do not exist, and runs forward-compatibility migrations if they do. Must be awaited before any query against `jarvis.db`.

### Core Database Table: `notes`

| Column            | Type    | Notes                                              |
|-------------------|---------|----------------------------------------------------|
| `id`              | INTEGER | Auto-increment primary key                         |
| `path`            | TEXT    | Unique. Relative path from workspace root to file  |
| `title`           | TEXT    | Extracted from frontmatter or first heading        |
| `folder`          | TEXT    | Subfolder within `memory/` (e.g. `projects`)       |
| `content_preview` | TEXT    | Short excerpt for list views                       |
| `body`            | TEXT    | Full note text, used by FTS                        |
| `tags`            | TEXT    | JSON-encoded list of tag strings                   |
| `frontmatter`     | TEXT    | JSON-encoded frontmatter key-value pairs           |
| `created_at`      | TEXT    | ISO 8601 timestamp from file or frontmatter        |
| `updated_at`      | TEXT    | ISO 8601 timestamp from file or frontmatter        |
| `word_count`      | INTEGER | Character count of body                            |
| `indexed_at`      | TEXT    | When the row was last written by the indexer       |

Indexed columns: `folder`, `updated_at`.

### Key Pydantic Schemas

```python
# Memory
class NoteMetadataResponse(BaseModel):
    path: str
    title: str
    folder: str
    tags: list
    updated_at: str
    word_count: int

class NoteDetailResponse(BaseModel):
    path: str
    title: str
    content: str        # full Markdown content read from disk
    frontmatter: dict
    updated_at: str

# Chat
class ChatMessage(BaseModel):
    type: str = "message"
    content: str
    session_id: Optional[str] = None

class ChatEvent(BaseModel):
    type: str
    content: Optional[str] = None
    name: Optional[str] = None
    input: Optional[dict] = None
    session_id: Optional[str] = None

# Sessions
class SessionMetadataResponse(BaseModel):
    session_id: str
    title: str
    created_at: str
    message_count: int

# Graph
class GraphResponse(BaseModel):
    nodes: list
    edges: list
```

## Gotchas

**The database now initializes on server startup via a lifespan handler in `main.py`.** The database is created before any request is served. If you write a new service that queries `jarvis.db` directly, you can rely on it being present after server boot. If using `init_database` in tests or scripts outside the normal startup path, you still need to await it explicitly.

**FTS triggers use the `content=` optimization.** The `notes_fts` table is a content-backed FTS5 table pointing at `notes`. This means FTS rows do not store their own copy of the text — they reference the `notes` table. If a row is deleted from `notes` without the corresponding trigger firing (e.g., from direct SQL manipulation outside the normal service layer), the FTS index will contain stale entries that point to nothing. Always use the service layer to mutate `notes`, not raw SQL.

**Schema migration is additive only.** The `body` column migration in `init_database` uses `ALTER TABLE ADD COLUMN`. SQLite does not support dropping or renaming columns in older versions. Any future schema changes should follow the same additive pattern, using `_column_exists` checks before attempting `ALTER TABLE`.

**`tags` and `frontmatter` are stored as JSON strings, not as normalized rows.** Filtering by a specific tag requires either a `LIKE` query on the JSON string or parsing the field in Python after retrieval. There is no tags join table.

## Known Issues

### Critical

**FIXED: `SpecialistCreateRequest` silently drops five fields due to an indentation error in `schemas.py` (lines 127–151).** The class definition has been corrected and all fields (`style`, `rules`, `tools`, `examples`, `icon`) are now properly placed inside `SpecialistCreateRequest`. Both `SpecialistCreateRequest` and `UrlIngestRequest` now have their correct field sets.

### High

**FIXED: FTS and trigger creation failures are silently swallowed (`database.py:84–91`).** The bare `except Exception: pass` blocks have been replaced with logging so that FTS5 or trigger failures are recorded rather than discarded silently.

**FIXED: FTS rebuild is not atomic (`database.py:76–82`).** The drop and recreate steps are now combined into a single `executescript` call, so both the `FTS_SQL` and `TRIGGER_SQL` blocks execute atomically. An interrupted rebuild can no longer leave the database without an FTS table and triggers.

### Medium

**FIXED: No startup database init (`main.py:55`).** `main.py` now has a FastAPI `lifespan` handler that calls `init_database` on server startup, eliminating the ordering dependency where non-memory services could fail if they queried `jarvis.db` before the memory service had run.

**FIXED: Untyped collection fields in `schemas.py`.** All `list` and `dict` fields now carry element types (e.g., `list[str]`, `list[GraphNodeResponse]`, `dict[str, str]`), enabling Pydantic to validate and document their contents.

**FIXED: f-string interpolation in PRAGMA query (`database.py:53`).** The `table` argument to `_column_exists` is now validated against an allowlist of known table names before being interpolated, removing the risk of unexpected SQL from untrusted input.

**FIXED: `WorkspaceInitRequest.api_key` accepts whitespace-only strings (`schemas.py:12`).** A `@field_validator` now strips whitespace and rejects blank values, surfacing the problem at the API boundary rather than deeper in the service layer.
