# Step 20a — Chunk-Level Embeddings

> **Goal**: Split notes into meaningful chunks (by headings + sliding window),
> embed each chunk separately, and make `search_similar()` return chunks
> grouped back to parent notes. This is the single highest-impact change
> in the entire semantic upgrade.

**Status**: ⬜ Not started
**Depends on**: Step 20f (eval baseline established)
**Effort**: ~2 days
**Branch**: `feat/semantic-node-connection`

---

## Why This Matters

Today one long note = one embedding vector. If a 2000-word note about a project
has one paragraph about sleep habits, that paragraph is invisible to semantic search
because the note's overall vector is about "project management". Chunk-level
embeddings let us find **the exact section** that matches a query.

**Current code** (`embedding_service.py:98`):
```python
embed_input = f"{title}. {title}. {tags}. {body}"
```
This concatenates the entire note body into one embedding input. A note with
5 sections about different topics gets one averaged vector.

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| `chunking.py` service | Split markdown into chunks by heading + sliding window |
| `note_chunks` table | Store chunks with position, section title, token count |
| `chunk_embeddings` table | Store embeddings per chunk (not per note) |
| `embed_note_chunks()` | Chunk a note and embed each chunk |
| `search_similar_chunks()` | Search chunks, return grouped by parent note |
| Incremental chunking | On note create/update, re-chunk + re-embed only changed note |
| `reindex_all_chunks()` | Full reindex of all chunks from markdown files |
| Backwards compat | `note_embeddings` stays; `search_similar()` continues to work |

**What this step does NOT cover**:
- Changing retrieval weights (step 20e)
- Chunk-level graph edges (step 20c)
- Node embeddings (step 20b)

---

## File Structure

```
backend/
  services/
    chunking.py              # NEW — markdown chunking logic
    embedding_service.py     # MODIFY — add chunk embedding + chunk search
  models/
    database.py              # MODIFY — add note_chunks + chunk_embeddings tables
  services/
    memory_service.py        # MODIFY — trigger chunk embedding on note create/update
  tests/
    test_chunking.py         # NEW — chunk splitting tests
    test_chunk_embeddings.py # NEW — chunk embed + search tests
```

---

## Schema Changes (`database.py`)

```sql
CREATE TABLE IF NOT EXISTS note_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    note_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    section_title TEXT DEFAULT '',
    chunk_text TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (note_id) REFERENCES notes(id) ON DELETE CASCADE,
    UNIQUE(path, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_path ON note_chunks(path);
CREATE INDEX IF NOT EXISTS idx_chunks_note_id ON note_chunks(note_id);

CREATE TABLE IF NOT EXISTS chunk_embeddings (
    chunk_id INTEGER PRIMARY KEY,
    path TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    embedding BLOB NOT NULL,
    content_hash TEXT NOT NULL,
    model_name TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedded_at TEXT NOT NULL,
    FOREIGN KEY (chunk_id) REFERENCES note_chunks(id) ON DELETE CASCADE,
    UNIQUE(path, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunk_emb_path ON chunk_embeddings(path);
```

**Note**: `note_embeddings` table stays unchanged. Both systems coexist.
The old note-level embeddings serve as fallback and are used for
note↔note similarity in graph (until step 20c replaces them).

---

## Implementation Details

### 1. `chunking.py` — Markdown Chunker

Strategy: **heading-based splitting + sliding window for long sections**

```python
@dataclass
class Chunk:
    index: int
    section_title: str   # "" for intro, "## Goals" for a section
    text: str
    token_count: int     # approximate: len(text.split())

def chunk_markdown(
    content: str,
    title: str = "",
    tags: list[str] | None = None,
    max_chunk_tokens: int = 300,
    overlap_tokens: int = 50,
) -> list[Chunk]:
```

**Algorithm**:

1. Parse frontmatter → extract title + tags
2. Split body by markdown headings (`## `, `### `, etc.)
3. For each section:
   - If section ≤ `max_chunk_tokens` → one chunk
   - If section > `max_chunk_tokens` → sliding window with `overlap_tokens`
4. Prepend context to each chunk: `"{title}. {section_title}. {chunk_text}"`
   (so the embedding knows what note/section this chunk belongs to)
5. First chunk always includes title + tags as context prefix

**Why heading-based, not fixed-size**:
- Markdown notes have natural semantic boundaries at headings
- "## Meeting Notes" and "## Technical Decisions" are different topics in the same note
- Fixed-size windows break mid-sentence and lose section context

**Edge cases**:
- Notes without headings → treat entire body as one section → sliding window if long
- Empty body → single chunk with just title + tags
- Very short notes (< 50 tokens) → single chunk, no splitting

### 2. `embedding_service.py` — Changes

Add these functions (keep existing ones unchanged):

```python
async def embed_note_chunks(
    note_path: str,
    content: str,
    db_path: Path,
) -> int:
    """Chunk a note, embed each chunk, store in SQLite.
    Returns number of chunks embedded.
    """

async def search_similar_chunks(
    query: str,
    limit: int = 10,
    workspace_path: Path | None = None,
) -> list[dict]:
    """Find most similar chunks, grouped by parent note.

    Returns:
        [
            {
                "path": "projects/website.md",
                "best_chunk_score": 0.87,
                "best_chunk_text": "Met with Michał about...",
                "best_chunk_section": "## Meeting Notes",
                "chunk_scores": [0.87, 0.45, 0.32],  # all chunks
            },
            ...
        ]
    """

async def reindex_all_chunks(workspace_path: Path | None = None) -> int:
    """Re-chunk and re-embed all notes. Returns count of chunks embedded."""
```

**Search implementation**:

```python
async def search_similar_chunks(query, limit=10, workspace_path=None):
    query_vec = embed_query(query)

    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute(
            "SELECT ce.path, ce.chunk_index, ce.embedding, nc.chunk_text, nc.section_title "
            "FROM chunk_embeddings ce "
            "JOIN note_chunks nc ON ce.chunk_id = nc.id"
        )
        rows = await cursor.fetchall()

    # Score all chunks
    scored = []
    for path, idx, blob, text, section in rows:
        vec = blob_to_vector(blob)
        sim = cosine_similarity(query_vec, vec)
        scored.append((path, idx, sim, text, section))

    scored.sort(key=lambda x: x[2], reverse=True)

    # Group by parent note, keep best chunk per note
    note_groups: dict[str, dict] = {}
    for path, idx, sim, text, section in scored:
        if path not in note_groups:
            note_groups[path] = {
                "path": path,
                "best_chunk_score": sim,
                "best_chunk_text": text[:500],
                "best_chunk_section": section,
                "chunk_scores": [],
            }
        note_groups[path]["chunk_scores"].append(round(sim, 4))

    # Sort notes by best chunk score, return top-K
    results = sorted(
        note_groups.values(),
        key=lambda x: x["best_chunk_score"],
        reverse=True,
    )
    return results[:limit]
```

### 3. `memory_service.py` — Trigger Chunk Embedding

In `_index_note()`, after the existing `embed_note()` call, add:

```python
# Auto-embed chunks for semantic search
if os.environ.get("JARVIS_DISABLE_EMBEDDINGS") != "1":
    try:
        from services.embedding_service import embed_note_chunks
        await embed_note_chunks(note_path, full_content, db_path)
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("embed_note_chunks failed for %s: %s", note_path, exc)
```

### 4. Content Hash for Chunks

Reuse the existing `content_hash()` function. Hash each chunk's text individually.
If a note is updated but only one section changed, only re-embed the changed chunks.

```python
async def embed_note_chunks(note_path, content, db_path):
    from services.chunking import chunk_markdown
    fm, body = parse_frontmatter(content)
    chunks = chunk_markdown(content, title=fm.get("title", ""), tags=fm.get("tags", []))

    async with aiosqlite.connect(str(db_path)) as db:
        # Get note_id
        cursor = await db.execute("SELECT id FROM notes WHERE path = ?", (note_path,))
        row = await cursor.fetchone()
        if not row:
            return 0
        note_id = row[0]

        # Delete old chunks for this note (simpler than diffing)
        await db.execute("DELETE FROM note_chunks WHERE path = ?", (note_path,))
        await db.execute("DELETE FROM chunk_embeddings WHERE path = ?", (note_path,))

        count = 0
        for chunk in chunks:
            # Insert chunk
            cursor = await db.execute(
                "INSERT INTO note_chunks (note_id, path, chunk_index, section_title, chunk_text, token_count, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (note_id, note_path, chunk.index, chunk.section_title, chunk.text, chunk.token_count, now),
            )
            chunk_id = cursor.lastrowid

            # Embed and store
            vec = embed_text(chunk.text)
            blob = vector_to_blob(vec)
            c_hash = content_hash(chunk.text)
            await db.execute(
                "INSERT INTO chunk_embeddings (chunk_id, path, chunk_index, embedding, content_hash, model_name, dimensions, embedded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (chunk_id, note_path, chunk.index, blob, c_hash, _MODEL_NAME, _DIMENSIONS, now),
            )
            count += 1

        await db.commit()
    return count
```

---

## Chunking Strategy Details

### Parameters

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `max_chunk_tokens` | 300 | MiniLM-L12 handles up to 512 tokens; 300 leaves room for context prefix |
| `overlap_tokens` | 50 | ~1-2 sentences of overlap to maintain continuity between windows |
| Context prefix | `"{title}. {section}."` | Gives the embedding model note-level context for each chunk |

### Example

Input note:
```markdown
---
title: Website Redesign Project
tags: [project, web]
---

We decided to redesign the site in Q2.

## Meeting Notes
Met with Michał about the new landing page. He suggested...
(200 tokens of content)

## Technical Decisions
- Framework: Nuxt 3
- Hosting: Vercel
(100 tokens)

## Budget
The budget discussion was long...
(400 tokens)
```

Output chunks:
| Index | Section | Tokens | Text prefix |
|-------|---------|--------|-------------|
| 0 | (intro) | ~60 | "Website Redesign Project. project, web. We decided to redesign..." |
| 1 | Meeting Notes | ~220 | "Website Redesign Project. Meeting Notes. Met with Michał..." |
| 2 | Technical Decisions | ~120 | "Website Redesign Project. Technical Decisions. Framework: Nuxt 3..." |
| 3 | Budget (window 1) | ~300 | "Website Redesign Project. Budget. The budget discussion..." |
| 4 | Budget (window 2) | ~150 | "Website Redesign Project. Budget. ...continued from overlap..." |

---

## Migration Path

1. New tables are created on startup (additive schema migration in `init_database()`)
2. Existing `note_embeddings` stays — no data loss
3. `search_similar()` (note-level) continues to work unchanged
4. New `search_similar_chunks()` is available in parallel
5. `retrieval.py` is NOT changed in this step (that's step 20e)
6. Running `reindex_all_chunks()` via API or startup populates chunk tables

---

## Test Cases

```python
# test_chunking.py

def test_short_note_single_chunk():
    """Note under max_chunk_tokens → exactly 1 chunk."""

def test_heading_based_split():
    """Note with ## headings → one chunk per section."""

def test_long_section_sliding_window():
    """Section over max_chunk_tokens → multiple overlapping chunks."""

def test_context_prefix_includes_title():
    """Each chunk text starts with note title."""

def test_empty_body_still_produces_chunk():
    """Note with only frontmatter → 1 chunk with title+tags."""

def test_no_headings_long_note():
    """Long note without headings → sliding window on entire body."""

def test_chunk_overlap():
    """Adjacent window chunks share overlap_tokens of text."""


# test_chunk_embeddings.py

async def test_embed_note_chunks_stores_in_db():
    """After embedding, note_chunks and chunk_embeddings have matching rows."""

async def test_search_similar_chunks_returns_grouped():
    """search_similar_chunks groups results by parent note."""

async def test_best_chunk_score_is_highest():
    """best_chunk_score is the max of all chunk scores for that note."""

async def test_reindex_all_chunks_processes_all_notes():
    """reindex_all_chunks creates chunks for every .md in memory/."""

async def test_re_embedding_deletes_old_chunks():
    """Updating a note replaces its old chunks, not appends."""

async def test_chunk_embedding_skipped_when_disabled():
    """JARVIS_DISABLE_EMBEDDINGS=1 skips chunk embedding too."""
```

---

## Acceptance Criteria

- [ ] `chunking.py` splits notes by headings + sliding window
- [ ] Each chunk includes title context prefix
- [ ] `note_chunks` and `chunk_embeddings` tables created on startup
- [ ] `embed_note_chunks()` stores chunks + embeddings in SQLite
- [ ] `search_similar_chunks()` returns results grouped by parent note with best chunk score
- [ ] `reindex_all_chunks()` processes all markdown files
- [ ] Note update triggers re-chunking (delete old + insert new)
- [ ] Existing `note_embeddings` and `search_similar()` continue to work unchanged
- [ ] All new tests pass
- [ ] All existing tests pass (no regressions)
- [ ] Re-run eval set: semantic query recall should improve vs baseline
