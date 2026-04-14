---
title: Memory System
status: active
type: feature
sources:
  - backend/routers/memory.py
  - backend/services/memory_service.py
  - backend/services/ingest.py
  - backend/services/url_ingest.py
  - backend/utils/markdown.py
  - frontend/app/pages/memory.vue
  - frontend/app/components/NoteList.vue
  - frontend/app/components/NoteViewer.vue
  - frontend/app/components/ImportDialog.vue
  - frontend/app/components/LinkIngestDialog.vue
depends_on: [database]
last_reviewed: 2026-04-14
last_updated: 2026-04-14
---

## Summary

The memory system is Jarvis's core storage layer. Every piece of user knowledge lives as a Markdown file under `Jarvis/memory/`, with SQLite acting as a queryable index on top of those files. The browser UI provides note browsing, full-text search, folder filtering, and two ingest paths — local file upload and URL import — that each produce a new Markdown note automatically indexed into SQLite.

## How It Works

### Storage model

Markdown files in `Jarvis/memory/` are the single source of truth. SQLite is rebuilt from those files at any time via the `/api/memory/reindex` endpoint. The folder hierarchy (`inbox/`, `knowledge/`, `projects/`, etc.) is encoded in the file path rather than as database metadata, which keeps notes portable and Obsidian-compatible.

Every note carries a YAML frontmatter block with `title`, `created_at`, `updated_at`, and `tags`. When `memory_service` creates or updates a note it always rewrites the frontmatter before writing the file, then calls `_index_note` to upsert the record in SQLite using an `INSERT ... ON CONFLICT DO UPDATE` so reindex is always idempotent.

### Search

`list_notes` queries SQLite directly. When a search string is present, the service tokenizes it into individual words (stripping punctuation to avoid FTS5 syntax errors) and constructs a prefix-match query like `word1* word2*` against the `notes_fts` virtual table. Without a search string it falls back to a plain ordered scan. The result set is capped at a configurable `limit` (default 50, max 200).

### Deletion (soft)

`delete_note` moves the Markdown file to `Jarvis/.trash/{relative-path}` rather than deleting it outright, then removes the SQLite record. This means the note is recoverable from the filesystem even after deletion via the UI.

### Ingest pipeline — files

`fast_ingest` accepts `.md`, `.txt`, and `.pdf` files. The core logic:

1. Text extraction: `.md` files are used as-is (frontmatter added if missing); `.txt` files are wrapped in generated frontmatter and saved as `.md`; `.pdf` files are parsed by `pdfplumber` and also wrapped before saving.
2. The resulting `.md` file is written to `memory/{target_folder}/` using a slug-based filename.
3. If a filename already exists at the target path a numeric suffix (`-1`, `-2`, ...) is appended rather than overwriting.
4. The new note is indexed in SQLite, then a graph rebuild is attempted. A failed graph rebuild logs a warning but does not roll back the ingest.

The file is received by the router as a multipart upload, written to a temporary file, passed to `fast_ingest`, and the temporary file is always deleted in a `finally` block regardless of outcome.

### Ingest pipeline — URLs

`url_ingest.ingest_url` handles two cases detected by regex pattern matching:

- **YouTube**: Fetches video metadata via the oEmbed API (no API key needed) and the transcript via `youtube-transcript-api` (prefers Polish, falls back to English, then any available language). If no transcript is available the note is saved with a placeholder. Transcripts longer than 50,000 characters are truncated.
- **Web articles**: Downloads the page with `requests` (retries once without SSL verification if the first attempt fails with a certificate error), extracts the main content with `trafilatura` in HTML mode, and converts it to Markdown with `markdownify`. Articles are capped at 100,000 characters.

Both paths strip tracking parameters from the URL before storing it in the note's `source` frontmatter field.

An optional `summarize` flag triggers `smart_enrich` after ingest, which calls Claude to add a 1–2 sentence summary and keyword tags to the note's frontmatter. This is the only part of the ingest pipeline that requires an API key and makes external API calls.

### AI enrichment

`smart_enrich` in `ingest.py` sends the first 3,000 characters of a note to Claude with a prompt requesting JSON containing `summary` and `tags`. If Claude returns malformed JSON, the raw response text is stored as the summary and tags are left empty. New tags are merged with any existing tags in the frontmatter (deduplication via `set`).

Note that `smart_enrich` rebuilds the frontmatter block manually using an f-string loop rather than going through `utils/markdown.py`'s `add_frontmatter` (which uses `yaml.dump`). Similarly, `url_ingest._build_frontmatter` constructs YAML with f-strings. `add_frontmatter` is only used by `memory_service` for standard note CRUD. This means title or author strings containing YAML special characters (colons, quotes, newlines) can produce malformed frontmatter in ingested notes.

### Frontend

The memory page is a two-panel layout: a sidebar with `NoteList` for browsing/searching, and a main area with `NoteViewer` for reading the selected note.

`NoteViewer` strips the YAML frontmatter from the raw note content before rendering, parses the remaining Markdown with `marked`, and sanitizes the HTML output with `DOMPurify` before injecting it into the DOM. Frontmatter fields are displayed separately as labeled tags above the body.

`NoteList` derives the folder list from the current notes array in the parent component — it does not fetch folders independently. Clicking an already-active folder deactivates it (toggles off), returning to the unfiltered view.

`ImportDialog` uses a drag-and-drop zone backed by a hidden `<input type="file">` and submits via `multipart/form-data` using Nuxt's `$fetch`. `LinkIngestDialog` uses `v-model` for open/close state and performs client-side URL type detection with the same regex patterns used on the backend, giving the user immediate visual feedback before submitting.

## Key Files

- `backend/routers/memory.py` — HTTP endpoints for note CRUD, file ingest, URL ingest, reindex, and AI enrichment
- `backend/services/memory_service.py` — Core note operations: create, read, list, append, delete, reindex; manages Markdown files and SQLite index together
- `backend/services/ingest.py` — File ingest pipeline for `.md`, `.txt`, `.pdf`; AI enrichment via `smart_enrich`
- `backend/services/url_ingest.py` — URL ingest for YouTube videos (transcript + oEmbed metadata) and general web articles (trafilatura + markdownify)
- `backend/utils/markdown.py` — YAML frontmatter parsing (`parse_frontmatter`) and serialization (`add_frontmatter`) used throughout the backend
- `frontend/app/pages/memory.vue` — Memory page: sidebar/viewer layout, note selection state, folder/search coordination, and import dialog orchestration
- `frontend/app/components/NoteList.vue` — Sidebar list with FTS search input, folder filter pills, and per-note delete with confirmation
- `frontend/app/components/NoteViewer.vue` — Right-panel note reader; renders Markdown via `marked` + `DOMPurify` after stripping frontmatter
- `frontend/app/components/ImportDialog.vue` — Drag-and-drop file upload modal; submits to `/api/memory/ingest` as multipart
- `frontend/app/components/LinkIngestDialog.vue` — URL import modal with client-side YouTube/article detection, folder selection, and optional AI summary toggle

## API / Interface

All endpoints are prefixed with `/api/memory`.

```
GET    /notes
  Query params: folder?: string, search?: string, limit?: number (1–200, default 50)
  Returns: NoteMetadataResponse[]

GET    /notes/{note_path}
  Returns: NoteDetailResponse  { path, title, content, frontmatter, updated_at }
  Errors: 404 if not found

POST   /notes/{note_path}                         Status: 201
  Body: { content: string }
  Returns: NoteMetadataResponse
  Errors: 409 if note already exists, 400 on invalid path

PATCH  /notes/{note_path}
  Body: { append: string }
  Returns: NoteMetadataResponse
  Errors: 404 if not found

DELETE /notes/{note_path}
  Returns: { status: "deleted", path: string }
  Errors: 404 if not found

POST   /reindex
  Returns: ReindexResponse  { indexed: number }

POST   /ingest                                    multipart/form-data
  Fields: file (UploadFile), folder?: string (default "knowledge")
  Returns: { path, title, folder, source, size }
  Errors: 400 for unsupported file type or extraction failure

POST   /ingest-url
  Body: { url: string, folder?: string, summarize?: boolean }
  Returns: { path, title, type, source, word_count, summary? }
  Errors: 400 for invalid URL, inaccessible page, or missing API key when summarize=true

POST   /enrich/{note_path}
  Returns: { path, summary, tags, enriched: true }
  Errors: 400 if note not found or API key not configured
```

## Gotchas

**Deletion is not permanent.** The delete endpoint moves files to `Jarvis/.trash/` rather than removing them. SQLite records are removed, so deleted notes disappear from all queries, but the file remains recoverable. There is currently no UI to manage or empty the trash.

**Path traversal protection is shallow.** `_validate_path` blocks `..` segments and absolute paths, but validation happens only in the service layer. Callers using `note_path` directly with file system operations should ensure they call `_validate_path` first.

**`list_notes` reads from SQLite only.** Notes that exist on disk but have not been indexed (e.g. placed there manually outside of Jarvis) will not appear in the list until `/api/memory/reindex` is called. The frontend has no automatic trigger for reindex; it must be called explicitly.

**Search tokenization strips all non-word characters.** A search for `C++` becomes `C` — the `+` signs are removed before the FTS query is built. This is intentional to avoid FTS5 query syntax errors, but it means searches containing punctuation will silently broaden.

**FTS search clears the active folder filter, and folder filter clears the search.** In `memory.vue`, `onSearch` sets `activeFolder` to `null` and `onFolderChange` sets `searchQuery` to `''`. These are mutually exclusive UI modes — you cannot search within a folder from the current interface.

**YouTube ingest requires `youtube-transcript-api` to be installed** and will save a metadata-only note if no transcript is available. The `no-transcript` tag is added in this case to make such notes identifiable.

**Web page ingest retries without SSL verification on certificate failure.** The retry is logged as a warning but proceeds. This is a convenience trade-off for ingesting pages with self-signed or expired certificates; it means content from such pages is fetched without TLS validation.

**`smart_enrich` truncates input to 3,000 characters.** For long notes this means Claude only sees the beginning of the document when generating the summary and tags.

## Known Issues

The following issues were identified in a codebase review. They are listed in order of severity. None have been fixed as of `last_updated`.

### Critical

**SSRF via URL ingest (`url_ingest.py:223`).**
`_ingest_webpage` calls `requests.get(url, ...)` after only checking that the URL scheme is `http` or `https`. There is no check whether the resolved host is a private, loopback, or link-local address (e.g. `127.0.0.1`, `169.254.x.x`, `10.x.x.x`). An attacker who can submit ingest requests can use this to probe or exfiltrate responses from internal network services.

**Path traversal not fully blocked on Windows (`memory_service.py:37–41`).**
`_validate_path` rejects strings containing `..` or starting with `/`, but it does not reject Windows-style absolute paths such as `C:\Users\...` or paths using forward-slash drive prefixes like `/c:/...`. On a Windows host, constructing a `Path` from such a string and joining it to the memory directory will silently resolve outside the workspace.

### High

**SSL verification silently disabled on retry (`url_ingest.py:227–234`).**
When the first HTTP request to a web URL fails for any reason (not just certificate errors), the retry attempt sets `verify=False`, disabling TLS certificate validation entirely. The retry is logged as a warning but the downgraded request proceeds without any user confirmation, making the ingest silently vulnerable to man-in-the-middle interception on that request.

**`reindex_all` clears the notes table outside a transaction (`memory_service.py:239–249`).**
The function issues `DELETE FROM notes` and commits it, then re-indexes each file in a separate connection per note. A crash, restart, or exception between the delete commit and the completion of re-indexing leaves the index empty. Notes on disk are unaffected (source of truth is Markdown files), but the application will appear to have no notes until another reindex is run.

**Unbounded file upload size (`memory.py:84–108`).**
The `/api/memory/ingest` endpoint calls `await file.read()` with no size limit. There is no `Content-Length` check, no streaming, and no cap. A sufficiently large upload will consume all available backend memory before any validation runs.

**`smart_enrich` does not validate `note_path` against path traversal (`ingest.py:139–142`).**
`smart_enrich` constructs `full_path = mem / note_path` without calling `_validate_path` first. A caller passing a path such as `../../etc/passwd` (or a Windows equivalent) will cause the function to read an arbitrary file from the filesystem and send its first 3,000 characters to the Claude API.

### Medium

**Frontmatter YAML built with f-strings is injection-prone (`ingest.py:172–178`, `url_ingest.py:84–92`).**
Both `smart_enrich` and `_build_frontmatter` construct YAML by concatenating raw field values into a `---`-delimited string using f-strings or a manual loop. A title or author value containing a colon, newline, or quote character will produce invalid or semantically incorrect YAML. `memory_service` and `add_frontmatter` in `utils/markdown.py` correctly use `yaml.dump` and are not affected.

**`json.loads(tags)` crashes on corrupt rows (`memory_service.py:158`).**
In `list_notes`, the tags column is decoded with `json.loads(row["tags"])` with no exception handling. If any row in the notes table has a malformed tags value (e.g. from a manual DB edit or a past bug), the entire listing call raises an unhandled `json.JSONDecodeError` rather than skipping or substituting the bad row.

**`folder` form field in file upload is not validated against path traversal (`memory.py:84–108`).**
The `folder` parameter accepted by `POST /ingest` is passed directly to `fast_ingest` as `target_folder`, which appends it to the memory directory path without checking for `..` segments or absolute path prefixes. The `UrlIngestRequest` schema validates the equivalent field with a regex pattern; the file upload endpoint has no equivalent guard.
