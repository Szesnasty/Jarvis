# Step 04 — Memory Service + SQLite Index

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 03 — Onboarding](step-03-onboarding-workspace.md) | **Next**: [Step 05 — Claude Integration](step-05-claude-integration.md) | **Index**: [step-00-index.md](step-00-index.md)

---

## Goal

Jarvis can read, write, search, and list Markdown notes in `Jarvis/memory/`. A SQLite index accelerates search. The frontend has a memory browser view.

---

## Files to Create / Modify

### Backend
```
backend/
├── routers/
│   └── memory.py              # NEW — CRUD endpoints for notes
├── services/
│   ├── memory_service.py      # NEW — read/write/search/list notes
│   └── workspace_service.py   # MODIFY — init DB schema on workspace create
├── models/
│   ├── database.py            # NEW — SQLite setup + tables
│   └── schemas.py             # MODIFY — add Note schemas
└── utils/
    └── markdown.py            # NEW — frontmatter parsing
```

### Frontend
```
frontend/src/
├── views/
│   └── MemoryView.vue         # NEW — browse + view notes
├── components/
│   ├── NoteList.vue           # NEW — list of notes (sidebar/panel)
│   └── NoteViewer.vue         # NEW — display single note content
├── router/
│   └── index.ts               # MODIFY — add /memory route
├── services/
│   └── api.ts                 # MODIFY — add memory API calls
└── types/
    └── index.ts               # MODIFY — add Note types
```

---

## Specification

### SQLite Schema (`database.py`)

```sql
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,          -- relative to memory/, e.g. "projects/jarvis.md"
    title TEXT NOT NULL DEFAULT '',
    folder TEXT NOT NULL DEFAULT '',    -- "projects", "daily", "inbox", etc.
    content_preview TEXT DEFAULT '',    -- first 200 chars
    tags TEXT DEFAULT '[]',            -- JSON array of strings
    frontmatter TEXT DEFAULT '{}',     -- JSON of full frontmatter
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    word_count INTEGER DEFAULT 0,
    indexed_at TEXT NOT NULL           -- when this row was last synced with disk
);

CREATE INDEX IF NOT EXISTS idx_notes_folder ON notes(folder);
CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at);

-- Full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    title, content_preview, tags,
    content='notes',
    content_rowid='id'
);
```

- **Reminder**: SQLite is an index/cache. Markdown files are the source of truth. If SQLite is deleted, a full reindex from disk must restore it.

### Database Lifecycle

- `init_database(db_path)` — creates tables if not exist
- `reindex_all(memory_path, db)` — scans all .md files, updates SQLite
- Called on workspace init (step 03) and optionally on startup if index is stale

### Memory Service API

#### `GET /api/memory/notes?folder=&search=&limit=50`

Returns list of note metadata (not full content):
```json
[
  {
    "path": "projects/jarvis.md",
    "title": "Jarvis Project",
    "folder": "projects",
    "tags": ["project", "ai"],
    "updated_at": "2026-04-12T10:30:00",
    "word_count": 342
  }
]
```

- `folder` filter: only notes in that subfolder
- `search` filter: FTS5 search across title + content + tags
- `limit`: max results, default 50

#### `GET /api/memory/notes/{path:path}`

Returns full note content:
```json
{
  "path": "projects/jarvis.md",
  "title": "Jarvis Project",
  "content": "---\ntitle: Jarvis Project\ntags: [project, ai]\n---\n\n# Jarvis\n...",
  "frontmatter": {"title": "Jarvis Project", "tags": ["project", "ai"]},
  "updated_at": "2026-04-12T10:30:00"
}
```

#### `POST /api/memory/notes/{path:path}`

Create or overwrite a note:
```json
{
  "content": "---\ntitle: My Note\ntags: [idea]\n---\n\nContent here..."
}
```

- Parses frontmatter
- Writes .md file to disk
- Updates SQLite index
- Returns the updated note metadata

#### `PATCH /api/memory/notes/{path:path}`

Append to existing note:
```json
{
  "append": "\n\n## New Section\nMore content..."
}
```

#### `DELETE /api/memory/notes/{path:path}`

Moves to a `.trash/` folder (soft delete), removes from index.

### Frontmatter Parsing (`utils/markdown.py`)

Parse YAML frontmatter from Markdown files:

```python
def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Returns (frontmatter_dict, body_without_frontmatter)."""
    ...

def add_frontmatter(body: str, metadata: dict) -> str:
    """Wraps body with YAML frontmatter."""
    ...
```

- Use `PyYAML` or simple regex — no heavy dependency
- Handle missing frontmatter gracefully (return empty dict)

---

### Frontend

#### `MemoryView.vue`

Two-panel layout:
- Left: `NoteList` — folder tree + note list
- Right: `NoteViewer` — rendered note content (Markdown as HTML or raw text)

#### `NoteList.vue`

- Shows folder buttons at top (inbox, daily, projects, people, etc.)
- Clicking a folder loads notes from that folder
- Search input with debounce (300ms)
- Each note shows: title, tags, date

#### `NoteViewer.vue`

- Shows selected note content
- Renders Markdown as formatted text (use a simple Markdown renderer or just `<pre>` for MVP)
- Shows frontmatter as metadata header

---

## Key Decisions

- SQLite FTS5 for search — fast, built-in, no extra infrastructure
- Frontmatter follows Obsidian convention: YAML between `---` delimiters
- Soft delete to prevent data loss
- Index rebuilt from disk files on demand — SQLite is never the authoritative store
- Add `PyYAML` to `requirements.txt`

---

## Acceptance Criteria

- [ ] Creating a note via API creates a `.md` file on disk with frontmatter
- [ ] Listing notes returns metadata from SQLite
- [ ] Search returns relevant notes via FTS5
- [ ] Frontend memory browser shows folders and notes
- [ ] Clicking a note shows its content
- [ ] Deleting a note moves it to `.trash/`, not permanent delete
- [ ] Deleting SQLite and calling reindex restores the full index from disk
