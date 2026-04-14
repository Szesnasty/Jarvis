---
title: Database Layer
status: active
type: concept
sources:
  - backend/models/database.py
  - backend/models/schemas.py
  - backend/main.py
depends_on: []
last_reviewed: 2026-04-14
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

### Initialization

The database is initialized lazily by `memory_service.py` the first time it is needed — there is no startup hook in `main.py` that creates the database on server boot. The `init_database(db_path)` function handles both first-time creation and upgrades for existing databases. It creates the `notes` table (idempotently, using `CREATE TABLE IF NOT EXISTS`), then checks for the `body` column separately and adds it via `ALTER TABLE` if it is absent — this is a forward-compatibility migration for databases created before the `body` column was introduced.

After ensuring the schema is correct, `init_database` checks whether the existing FTS table already indexes the `body` column. If it does not (an older FTS schema), it drops the FTS table and all three triggers before recreating them. This ensures the FTS index always covers the full note body and does not silently remain on an outdated schema.

### Pydantic Schemas

`schemas.py` defines all request and response models used across the API. These are pure data-transfer objects — they do not map directly to database rows. Serialization and deserialization between SQLite rows, Markdown files, and API responses is handled by individual services, not by the schema models.

## Key Files

- `backend/models/database.py` — Defines the SQLite schema, FTS virtual table, sync triggers, and the `init_database` async function that creates or migrates the database on first use.
- `backend/models/schemas.py` — Pydantic models for all API request and response bodies across every router.
- `backend/main.py` — FastAPI application factory; registers all routers but does not initialize the database directly — that happens lazily via the memory service.
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

**The database does not initialize on server startup.** `main.py` has no lifespan hook that calls `init_database`. The database is created on the first call into `memory_service.py`. If you write a new service that queries `jarvis.db` directly before memory_service has run, it will find no database file and fail. Call `init_database(db_path)` explicitly at the start of any new service that needs it.

**FTS triggers use the `content=` optimization.** The `notes_fts` table is a content-backed FTS5 table pointing at `notes`. This means FTS rows do not store their own copy of the text — they reference the `notes` table. If a row is deleted from `notes` without the corresponding trigger firing (e.g., from direct SQL manipulation outside the normal service layer), the FTS index will contain stale entries that point to nothing. Always use the service layer to mutate `notes`, not raw SQL.

**Schema migration is additive only.** The `body` column migration in `init_database` uses `ALTER TABLE ADD COLUMN`. SQLite does not support dropping or renaming columns in older versions. Any future schema changes should follow the same additive pattern, using `_column_exists` checks before attempting `ALTER TABLE`.

**`tags` and `frontmatter` are stored as JSON strings, not as normalized rows.** Filtering by a specific tag requires either a `LIKE` query on the JSON string or parsing the field in Python after retrieval. There is no tags join table.

## Known Issues

### Critical

**`SpecialistCreateRequest` silently drops five fields due to an indentation error in `schemas.py` (lines 127–151).** The fields `style`, `rules`, `tools`, `examples`, and `icon` are physically placed inside the `UrlIngestRequest` class body — they appear after its `@field_validator` method without a dedent, so Python assigns them to `UrlIngestRequest`, not `SpecialistCreateRequest`. As a result, `SpecialistCreateRequest` only exposes `name`, `role`, and `sources`. Any specialist created via the API loses its style, rules, tools, examples, and icon at the request boundary — those values are never received by the backend. `UrlIngestRequest` gains five spurious fields it should not have. Both models are wrong.

### High

**FTS and trigger creation failures are silently swallowed (`database.py:84–91`).** The `try/except Exception: pass` blocks around `db.executescript(FTS_SQL)` and `db.executescript(TRIGGER_SQL)` discard all errors without logging. If either call fails — for example because the SQLite version does not support FTS5, or because a trigger already exists with an incompatible definition — the database will start up appearing healthy while full-text search is completely non-functional. There is no indication to the user or operator that anything went wrong.

**FTS rebuild is not atomic (`database.py:76–82`).** When an outdated FTS schema is detected, the code drops the existing triggers and FTS table via `executescript`, then recreates them in a separate `try` block. If the process crashes or the connection drops between the drop and the recreate, the database is left without an FTS table or any of the sync triggers. Subsequent writes to `notes` will succeed but will never be reflected in search results. The fix is to wrap the drop and recreate in a single transaction or at minimum a single `executescript` call.

### Medium — No Startup Database Init (`main.py:55`)

`create_app()` in `main.py` registers all routers but never calls `init_database`. The database is only created the first time `memory_service.py` is invoked. Routes that belong to other services (e.g. `sessions`, `graph`, `specialists`) will fail with SQLite "no such table" errors if they query `jarvis.db` before any memory operation has run in the same server process. A FastAPI `lifespan` handler that calls `init_database` at startup would eliminate this ordering dependency entirely.

**Untyped collection fields in `schemas.py`.** Several models use bare `list` or `dict` with no element types: `NoteMetadataResponse.tags`, `NoteDetailResponse.frontmatter`, `SessionDetailResponse.messages`, `SessionDetailResponse.tools_used`, `GraphResponse.nodes`, `GraphResponse.edges`, and `GraphStatsResponse.top_connected`. Pydantic cannot validate, coerce, or document the contents of these fields. Malformed payloads pass through silently. Prefer typed annotations such as `list[str]`, `list[GraphNodeResponse]`, or `dict[str, str]` where the element shape is known.

**f-string interpolation in PRAGMA query (`database.py:53`).** `_column_exists` builds the query as `f"PRAGMA table_info({table})"` using direct string interpolation. PRAGMA does not support parameterized queries in SQLite, so this is the only practical option, but it means a caller passing an untrusted `table` string could produce unexpected SQL. The function is only called internally today with literal strings, so the risk is low — but it is fragile if the call sites change.

**`WorkspaceInitRequest.api_key` accepts whitespace-only strings (`schemas.py:12`).** The field has no `strip_whitespace=True` or `min_length` constraint. A user submitting a blank or spaces-only API key will pass Pydantic validation and reach the backend service, where it will fail later with a less informative error. Adding a `@field_validator` that strips and checks for non-empty content would surface the problem at the API boundary.
