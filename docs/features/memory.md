---
title: Memory System
status: active
type: feature
sources:
  - backend/routers/memory.py
  - backend/services/memory_service.py
  - backend/services/ingest.py
  - backend/services/url_ingest.py
  - backend/services/embedding_service.py
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

`list_notes` queries SQLite directly. When a search string is present, the service tokenizes it into individual words (stripping punctuation to avoid FTS5 syntax errors) and constructs a BM25-ranked FTS5 query against the `notes_fts` virtual table. Each candidate carries a `_bm25_score` pulled from SQLite's built-in `bm25()` function so callers can fuse this with other signals. Without a search string it falls back to a plain ordered scan. The result set is capped at a configurable `limit` (default 50, max 200).

### Semantic search (local embeddings)

`embedding_service.py` provides local, on-device semantic search via **fastembed** (ONNX Runtime). No API calls, no keys, no data leaving the machine. The model — `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dims, ~220MB) — is multilingual and handles Polish alongside English. It is lazy-loaded on first use (~3–4s cold start, ~400MB RAM).

- **On-write embedding.** `memory_service._index_note()` calls `embed_note()` after writing a Markdown file. The note's title, tags, and body are combined (title weighted by repetition) and passed to the model. Output vectors are packed as float32 BLOBs and stored in the `note_embeddings` table alongside a content-SHA256 hash. If the hash hasn't changed, `embed_note()` skips re-embedding — a cheap no-op for unchanged notes.
- **Graceful degradation.** The embed call is wrapped in a try/except and guarded by the `JARVIS_DISABLE_EMBEDDINGS` env var. If `fastembed` isn't installed (ImportError) or the call fails, indexing still succeeds — only the embedding step is skipped. Tests set `JARVIS_DISABLE_EMBEDDINGS=1` in `conftest.py` to avoid loading the model for every run.
- **Query path.** `search_similar(query, limit)` embeds the query at call time, loads all stored vectors, scores them by cosine similarity, and returns `(path, score)` tuples sorted descending. For large workspaces this is linear in the embedding count, which is fine for the MVP scale.
- **Reindex.** `reindex_all()` walks `memory/` and re-embeds every Markdown file. The content-hash check means the first run embeds everything while subsequent runs only embed changed notes.
- **Availability check.** `is_available()` returns `True` if `fastembed` can be imported. Callers use this to decide whether to attempt semantic features or fall back to BM25.

### Frontend search modes

`NoteList.vue` exposes a three-way toggle — **Keyword**, **Semantic**, **Hybrid** — above the search input. The parent `memory.vue` page dispatches each mode to a different backend endpoint:

- **Keyword** — `GET /api/memory/notes?search=...` (BM25 FTS ranking).
- **Semantic** — `GET /api/memory/semantic-search?q=...` followed by a metadata fetch to hydrate the result set. If the service returns `mode: "unavailable"` (fastembed not installed), the list is shown empty rather than falling through to keyword search.
- **Hybrid** — currently falls through to keyword search in the memory page; the hybrid fusion path is used by the chat pipeline via `retrieval.py`, not the UI list view. The toggle exists in the list UI for future wiring.

### Deletion (soft)

`delete_note` checks both the filesystem and the SQLite index. If the Markdown file exists on disk it is moved to `Jarvis/.trash/{relative-path}` rather than deleted outright. The SQLite record is always removed regardless of whether the file was present on disk — this handles the case where a file was deleted externally but its index entry remained, which previously caused the note to appear in the list but fail to delete with a 404 error. After deletion, it calls `graph_service.invalidate_cache()` so that the knowledge graph rebuilds from the current filesystem state on next access, preventing stale graph nodes from referencing deleted notes. The note is recoverable from the `.trash` folder even after deletion via the UI.

### Ingest pipeline — files

`fast_ingest` accepts `.md`, `.txt`, `.pdf`, `.csv`, and `.xml` files. The core logic:

1. Text extraction: `.md` files are used as-is (frontmatter added if missing); `.txt` files are wrapped in generated frontmatter and saved as `.md`; `.pdf` files are parsed by `pdfplumber` and also wrapped before saving.
2. The resulting `.md` file is written to `memory/{target_folder}/` using a slug-based filename.
3. If a filename already exists at the target path a numeric suffix (`-1`, `-2`, ...) is appended rather than overwriting.
4. The new note is indexed in SQLite (which also auto-embeds it). The ingest then calls `connection_service.connect_note()` which writes a `suggested_related` block to the note's frontmatter and updates the graph incrementally via `graph_service.ingest_note()`. **Per-note ingest no longer triggers a full `rebuild_graph()`** — that remains for batch imports and the manual "Reindex all" / "Repair graph" actions. A failed Smart Connect step logs a warning but does not roll back the ingest.

For `.csv` and `.xml` files, `fast_ingest` delegates to `structured_ingest.ingest_structured_file` which handles both Jira exports and generic structured data:

- **Jira detection**: CSV files are identified as Jira exports when headers contain at least 3 of: Issue key, Summary, Status, Issue Type, Assignee, Priority. XML files are detected by the RSS `<rss>` root element or `<item>` elements with `<key>` children.
- **Jira processing**: Issues are grouped by epic (falling back to project, then "ungrouped"). The pipeline creates an overview note with status/type breakdowns and people lists, plus one note per group containing all issues formatted as markdown sections. People names are wiki-linked (`[[Name]]`) so the graph builder picks them up.
- **Generic CSV**: Converted to a single markdown note containing a markdown table (first 500 rows) with column/row counts in frontmatter.
- **Generic XML**: Converted to a single markdown note with structure analysis and first 200 elements rendered with their attributes and text content.
- **Large file handling**: Groups with more than 100 issues are split into multiple notes (part 1, part 2, etc.). The graph is rebuilt once after all notes are created, not per-note.

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

### Smart Connect (per-note linking)

`connection_service.connect_note()` runs after every single-file ingest. It builds a connection query from the note's title, headings, tags and first 800 characters, and gathers candidate links from three deterministic signals already produced by indexing:

- BM25 over `notes_fts` (via `memory_service.list_notes(search=...)`)
- Note-level cosine similarity (via `embedding_service.search_similar`)
- Chunk-level cosine similarity (via `embedding_service.search_similar_chunks`)

Candidates are merged with weighted scoring (BM25 0.30, note embedding 0.30, chunk embedding 0.20, alias 0.07). When a signal is unavailable (e.g. embeddings disabled, no chunks yet, no alias hits) the score is divided by the sum of weights of *active* signals so a single strong signal can still cross the floor — graceful degradation, not weight inflation. Tiers: `strong` ≥ 0.80, `normal` ≥ 0.60, `weak` ≥ 0.45 (kept only in `mode="aggressive"`). Caps: max 5 suggestions per note, max 2 from the same folder, max 1 near-duplicate (combined confidence ≥ 0.92).

Results are persisted to the note's frontmatter as a `suggested_related` block (path, confidence, methods, optional `evidence`). The authoritative `related:` field is **never** auto-written; promoting a suggestion is a user action (UI follow-up). The graph is then updated incrementally via `graph_service.ingest_note()`, after which any candidate carrying an `alias` method is also persisted as an `alias_match` edge (weight 0.75) on the graph.

#### Alias index

`services/alias_index.py` maintains a SQLite table `alias_index(phrase_norm, note_path, kind)` that maps **normalised** phrases (lowercase, NFKD-stripped, plus an explicit map for ł/Ł/đ/Đ/ø/Ø/ß which NFKD does not decompose) to the notes that own them. Each note contributes:

- its `title` (kind = `title`)
- every entry in its frontmatter `aliases:` list (kind = `alias`)
- every Markdown heading in its body (kind = `heading`)

Phrases shorter than 4 normalised characters are dropped to keep the index small and to avoid noise. The index is rebuildable from Markdown — it is purely an acceleration layer (per the source-of-truth doctrine).

`upsert_note_aliases()` is called inside `_index_note()` after every FTS write, so the index stays consistent with the canonical store. `scan_body()` tokenises a body, generates n-grams up to length 4, normalises each, and looks them up in a single SQL `IN` query (chunked at 800 to stay below SQLite's parameter limit). Self-matches are excluded via `exclude_path`.

The Smart Connect `_alias_signal` step calls `scan_body()` against `title + body[:800]`, treats every distinct hit as a binary 1.0 alias score for that target note, records the longest matched phrase as `evidence`, and surfaces the matched phrase list in `ConnectionResult.aliases_matched`.

`_slugify()` in `services/ingest.py` was rewritten to use the same NFKD + extra-diacritic strategy so Polish titles like *"Mój dzień"* produce `moj-dzien` instead of collapsing to an empty slug.

#### Semantic orphan repair

`graph_service.find_semantic_orphans()` extends the legacy `find_orphans()` (which only flagged degree-0 notes). A note is a *semantic* orphan if **every** edge touching it is either of a low-signal type — `tagged`, `part_of`, `temporal`, `derived_from` — or a `tagged` edge into a noisy bucket (`imported`, `data`, `xml`, `csv`). Both ignore sets are configurable.

`connect_note()` uses `is_semantic_orphan()` as a trigger for self-repair: when a fast-mode pass produces no suggestion at the `normal` tier (≥ 0.60) **and** the note is currently a semantic orphan in the graph, the pipeline retries once in `mode="aggressive"`. Aggressive mode keeps the `weak` tier (0.45–0.59) so a weakly-related neighbour can still surface for an otherwise isolated note. This is the only place that lowers the bar — every other code path drops weak suggestions.

`GET /api/connections/orphans` returns the current semantic orphan list. `POST /api/connections/run/{path}?mode=aggressive` re-runs Smart Connect for a given note (lives in [routers/connections.py](backend/routers/connections.py)).

#### Provenance edges

`connect_note()` emits two extra graph edges from a note's frontmatter (handled by `_emit_provenance_edges()`):

- **`derived_from`** (weight 0.45) — when `fm["source"]` is set, a `source:<sha1[:12]>` node is bootstrapped (label `"<kind>:<source[:60]>"` where kind is `url`, `jira`, `file`, or `other`) and the note links to it. Multiple notes derived from the same source converge on the same node, making it easy to find sibling notes.
- **`same_batch`** (weight 0.55) — when `fm["batch_id"]` is set, a `batch:<id>` node is bootstrapped and the note links to it. Co-imported notes naturally cluster.

Both edges are emitted after the standard graph ingest in `_finalise()` and are idempotent.

#### Dismissed suggestions

`services/dismissed_suggestions.py` maintains a SQLite table `dismissed_suggestions(note_path, target_path, dismissed_at)` (PK on the pair). `connect_note()` calls `_dismissed_targets_for()` right after collecting all signal scores and pops dismissed targets from BM25, note-embedding, chunk-embedding, and alias maps before merging — so dismissed pairs never participate in scoring or capping and therefore never re-surface.

`POST /api/connections/dismiss` records a `(note_path, target_path)` pair. `POST /api/connections/promote` moves a suggestion into the note's `related:` frontmatter list (the only automated writer of `related:`, representing explicit user confirmation) and removes it from `suggested_related`.

### Frontend

The memory page is a two-panel layout: a sidebar with `NoteList` for browsing/searching, and a main area with `NoteViewer` for reading the selected note.

`NoteViewer` strips the YAML frontmatter from the raw note content before rendering, parses the remaining Markdown with `marked`, and sanitizes the HTML output with `DOMPurify` before injecting it into the DOM. Frontmatter fields are displayed separately as labeled tags above the body.

`NoteList` derives the folder list from the current notes array in the parent component — it does not fetch folders independently. Clicking an already-active folder deactivates it (toggles off), returning to the unfiltered view.

`ImportDialog` uses a drag-and-drop zone backed by a hidden `<input type="file">` and submits via `multipart/form-data` using Nuxt's `$fetch`. `LinkIngestDialog` uses `v-model` for open/close state and performs client-side URL type detection with the same regex patterns used on the backend, giving the user immediate visual feedback before submitting.

## Key Files

- `backend/routers/memory.py` — HTTP endpoints for note CRUD, file ingest, URL ingest, reindex, AI enrichment, embedding reindex, and semantic search
- `backend/services/memory_service.py` — Core note operations: create, read, list, append, delete, reindex; manages Markdown files and SQLite index together; triggers on-write embedding
- `backend/services/ingest.py` — File ingest pipeline for `.md`, `.txt`, `.pdf`, `.csv`, `.xml`; AI enrichment via `smart_enrich`
- `backend/services/connection_service.py` — Smart Connect: per-note ingest-time linking; pure scoring + caps; writes `suggested_related` and calls incremental graph update
- `backend/services/alias_index.py` — Smart Connect alias index: SQLite-backed normalised phrase → note path map; `upsert_note_aliases()` (called from `_index_note`) and `scan_body()` (n-gram lookup, NFKD-normalised, Polish-aware)
- `backend/services/dismissed_suggestions.py` — Smart Connect dismissal store: SQLite table `dismissed_suggestions(note_path, target_path, dismissed_at)` with `dismiss()`, `undismiss()`, `list_dismissed_for()`, `list_all()`, `remove_note()`
- `backend/routers/connections.py` — Smart Connect HTTP surface: `GET /api/connections/orphans`, `POST /api/connections/run/{path}` (mode=fast|aggressive), `POST /api/connections/dismiss`, `POST /api/connections/promote`
- `backend/services/structured_ingest.py` — CSV/XML ingest with Jira export detection; groups issues by epic/project, creates overview + detail notes with wiki-linked people for graph integration
- `backend/services/url_ingest.py` — URL ingest for YouTube videos (transcript + oEmbed metadata) and general web articles (trafilatura + markdownify)
- `backend/services/embedding_service.py` — Local fastembed wrapper: lazy model loading, `embed_note` (with content-hash skip), `search_similar`, `reindex_all`, `delete_embedding`, `is_available`, vector blob packing, and cosine similarity helper
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

POST   /reindex-embeddings
  Returns: { status: "ok", notes_embedded: number }
  Errors: 503 if fastembed is not installed

GET    /semantic-search
  Query params: q: string (required), limit?: number (1–50, default 10)
  Returns: { results: [{ path, similarity }], mode: "semantic" | "unavailable", error?: string }
  Notes: returns mode="unavailable" (not a 503) when fastembed is missing, so the UI can fall back silently

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

**Deletion is not permanent.** The delete endpoint moves files to `Jarvis/.trash/` rather than removing them. SQLite records are always removed (even if the file is already missing from disk) and the graph cache is invalidated, so deleted notes disappear from all queries and the graph on next access. The file remains recoverable from `.trash`. There is currently no UI to manage or empty the trash.

**Path traversal protection uses containment checking.** `_validate_path` now uses `Path.resolve()` plus `.relative_to()` to ensure the final resolved path stays inside the memory directory, and also rejects Windows-style absolute paths at the input stage. Callers that construct paths outside the service layer must still call `_validate_path` themselves.

**`list_notes` reads from SQLite only.** Notes that exist on disk but have not been indexed (e.g. placed there manually outside of Jarvis) will not appear in the list until `/api/memory/reindex` is called. Conversely, if a file is removed from disk but the SQLite entry remains, the note will still appear in the list — however, deleting it via the UI will clean up the orphaned index entry. The frontend has no automatic trigger for reindex; it must be called explicitly.

**Search tokenization strips all non-word characters.** A search for `C++` becomes `C` — the `+` signs are removed before the FTS query is built. This is intentional to avoid FTS5 query syntax errors, but it means searches containing punctuation will silently broaden.

**Embedding is best-effort and silent on failure.** `_index_note()` wraps `embed_note()` in try/except and only logs at WARNING on unexpected errors; `ImportError` is swallowed entirely. If fastembed is not installed or the model fails to load, notes will still be created and indexed but won't carry embeddings — semantic search will simply return no results for those notes until a successful reindex.

**Embedding reindex is not triggered automatically.** The `/api/memory/reindex-embeddings` endpoint must be called explicitly. After upgrading or installing fastembed for the first time on an existing workspace, users must hit this endpoint to backfill embeddings for all existing notes.

**FTS search clears the active folder filter, and folder filter clears the search.** In `memory.vue`, `onSearch` sets `activeFolder` to `null` and `onFolderChange` sets `searchQuery` to `''`. These are mutually exclusive UI modes — you cannot search within a folder from the current interface.

**YouTube ingest requires `youtube-transcript-api` to be installed** and will save a metadata-only note if no transcript is available. The `no-transcript` tag is added in this case to make such notes identifiable.

**Web page ingest no longer retries without SSL verification.** The earlier `verify=False` retry has been removed. Pages with self-signed or expired certificates will fail ingest rather than being fetched insecurely.

**`smart_enrich` truncates input to 3,000 characters.** For long notes this means Claude only sees the beginning of the document when generating the summary and tags.
