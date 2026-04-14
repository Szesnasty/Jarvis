# Step 19b — Local Embedding Service

> **Goal**: Add a local embedding engine that runs on the user's machine.
> No API calls, no extra keys, no data leaving the device. Notes get
> embedded on ingest; queries get embedded at search time. This is the
> foundation for semantic search and graph-semantic integration in step 19c.

**Status**: ⬜ Not started
**Depends on**: Step 19a (BM25 fix, so retrieval pipeline is clean)
**Effort**: ~4–6 hours

---

## Why This Matters

Keyword search fails when the user's words don't match the note's words.
"How to sleep better" won't find a note titled "Evening Wind-Down Routine"
or a health note about "circadian rhythm optimization". Embeddings capture
meaning — semantically similar content gets similar vectors regardless of
exact wording. This turns Jarvis from a file search into a **knowledge
retrieval** system.

---

## Core Principles

1. **100% local** — no API calls for embeddings, ever. Model runs on CPU.
2. **Lazy loading** — model loaded on first use, not at startup.
3. **Incremental** — embed new/changed notes only, skip unchanged.
4. **Lightweight** — use a small model (~80MB). Don't require GPU.
5. **Source of truth = Markdown** — embeddings are a derived cache in SQLite.
   If `note_embeddings` table is deleted, it's rebuilt from markdown files.

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| `embedding_service.py` | Local embedding engine using fastembed or sentence-transformers |
| `note_embeddings` table | SQLite table storing vectors as BLOB + content hash |
| Embed on ingest | Auto-embed when notes are created/updated |
| Similarity search | `search_similar(query, limit)` → ranked note paths |
| Reindex command | CLI/API to rebuild all embeddings from scratch |
| Background embedding | Embed existing notes without blocking startup |

**What this step does NOT cover**:
- Combining embeddings with BM25/graph (step 19c)
- Graph similarity edges from embeddings (step 19c)
- Frontend semantic search UI (step 19c)

---

## Model Selection

**Critical constraint**: User notes may be in Polish, English, or mixed. English-only
models produce garbage embeddings for non-English content. **Multilingual is mandatory.**

| Option | Size | Dims | Speed (CPU) | Languages | Quality (MTEB) | Verdict |
|--------|------|------|-------------|-----------|----------------|--------|
| ~~`BAAI/bge-small-en-v1.5`~~ | 33MB | 384 | ~10ms | EN only | ~51 | ❌ No Polish |
| `intfloat/multilingual-e5-small` | 118MB | 384 | ~15ms | 100+ (PL ✅) | ~55 | ✅ Lighter option |
| **`intfloat/multilingual-e5-base`** | 280MB | 768 | ~30ms | 100+ (PL ✅) | ~59 | ✅ **Recommended** |
| `BAAI/bge-m3` | 570MB | 1024 | ~60ms | 100+ (PL ✅) | ~68 | 🏆 SOTA, heavy |

**Recommendation**: `intfloat/multilingual-e5-base` via `fastembed`.
- **Multilingual** — Polish, English, mixed content all work correctly
- **768 dimensions** — much better semantic resolution than 384
- **280MB** — one-time download, ~400MB RAM when loaded, no GPU needed
- **~30ms/note on CPU** — 100 notes reindex = 3 seconds
- `fastembed` is pure Python + ONNX, no PyTorch dependency (~500MB less install)
- Can be changed later — `model_name` stored in `note_embeddings` table, auto-reindex on model change

---

## File Structure

```
backend/
  services/
    embedding_service.py       # NEW — local embedding engine
    ingest.py                  # MODIFY — call embed after ingest
    memory_service.py          # MODIFY — embed on create/update
  models/
    database.py                # MODIFY — add note_embeddings table
  routers/
    memory.py                  # MODIFY — add /api/memory/reindex-embeddings
  requirements.txt             # MODIFY — add fastembed
  tests/
    test_embedding_service.py  # NEW
```

---

## Data Model

### SQLite: `note_embeddings` table

```sql
CREATE TABLE IF NOT EXISTS note_embeddings (
    note_id INTEGER PRIMARY KEY REFERENCES notes(id),
    path TEXT UNIQUE NOT NULL,
    embedding BLOB NOT NULL,          -- float32 array as bytes
    content_hash TEXT NOT NULL,        -- SHA-256 of markdown content
    model_name TEXT NOT NULL,          -- e.g. "intfloat/multilingual-e5-base"
    dimensions INTEGER NOT NULL,       -- e.g. 768
    embedded_at TEXT NOT NULL
);
```

**Key design**: `content_hash` lets us skip re-embedding unchanged notes.
If the markdown file hasn't changed, the embedding is still valid.

---

## Implementation Details

### 1. `embedding_service.py`

```python
import hashlib
import struct
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

# Lazy-loaded model singleton
_model = None
_MODEL_NAME = "intfloat/multilingual-e5-base"
_DIMENSIONS = 768

def _get_model():
    """Lazy-load embedding model on first use."""
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(model_name=_MODEL_NAME)
    return _model


def embed_text(text: str) -> List[float]:
    """Embed a single text string → float vector."""
    model = _get_model()
    embeddings = list(model.embed([text]))
    return embeddings[0].tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed multiple texts in a batch (more efficient)."""
    model = _get_model()
    return [e.tolist() for e in model.embed(texts)]


def content_hash(content: str) -> str:
    """SHA-256 hash of note content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def vector_to_blob(vec: List[float]) -> bytes:
    """Pack float list to binary blob for SQLite storage."""
    return struct.pack(f"{len(vec)}f", *vec)


def blob_to_vector(blob: bytes) -> List[float]:
    """Unpack binary blob back to float list."""
    n = len(blob) // 4  # float32 = 4 bytes
    return list(struct.unpack(f"{n}f", blob))


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    a_np = np.array(a)
    b_np = np.array(b)
    dot = np.dot(a_np, b_np)
    norm = np.linalg.norm(a_np) * np.linalg.norm(b_np)
    return float(dot / norm) if norm > 0 else 0.0


async def embed_note(
    note_path: str,
    content: str,
    db_path: Path,
) -> None:
    """Embed a single note and store in SQLite.
    Skip if content hash unchanged."""
    import aiosqlite
    from datetime import datetime, timezone
    from utils.markdown import parse_frontmatter

    fm, body = parse_frontmatter(content)
    title = fm.get("title", "")
    tags = " ".join(fm.get("tags", []))
    # Combine title (weighted by repetition) + tags + body
    embed_input = f"{title}. {title}. {tags}. {body}"

    new_hash = content_hash(content)

    async with aiosqlite.connect(str(db_path)) as db:
        # Check if already embedded with same content
        cursor = await db.execute(
            "SELECT content_hash FROM note_embeddings WHERE path = ?",
            (note_path,),
        )
        row = await cursor.fetchone()
        if row and row[0] == new_hash:
            return  # Skip — content unchanged

        vec = embed_text(embed_input)
        blob = vector_to_blob(vec)

        # Get note_id
        cursor = await db.execute(
            "SELECT id FROM notes WHERE path = ?", (note_path,)
        )
        note_row = await cursor.fetchone()
        if not note_row:
            return

        now = datetime.now(timezone.utc).isoformat()
        await db.execute("""
            INSERT OR REPLACE INTO note_embeddings
            (note_id, path, embedding, content_hash, model_name, dimensions, embedded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (note_row[0], note_path, blob, new_hash, _MODEL_NAME, _DIMENSIONS, now))
        await db.commit()


async def search_similar(
    query: str,
    limit: int = 10,
    workspace_path: Optional[Path] = None,
) -> List[Tuple[str, float]]:
    """Find notes most similar to a query by cosine similarity.

    Returns list of (note_path, similarity_score) sorted by score desc.
    """
    import aiosqlite
    from config import get_settings

    db_path = (workspace_path or get_settings().workspace_path) / "app" / "jarvis.db"
    if not db_path.exists():
        return []

    query_vec = embed_text(query)

    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute(
            "SELECT path, embedding FROM note_embeddings"
        )
        rows = await cursor.fetchall()

    scored = []
    for path, blob in rows:
        note_vec = blob_to_vector(blob)
        sim = cosine_similarity(query_vec, note_vec)
        scored.append((path, sim))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


async def reindex_all(workspace_path: Optional[Path] = None) -> int:
    """Re-embed all notes from markdown files. Returns count embedded."""
    from config import get_settings

    ws = workspace_path or get_settings().workspace_path
    mem = ws / "memory"
    db_path = ws / "app" / "jarvis.db"

    count = 0
    for md_file in mem.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="replace")
        rel_path = str(md_file.relative_to(mem))
        await embed_note(rel_path, content, db_path)
        count += 1
    return count
```

### 2. `database.py` — New Table

```sql
CREATE TABLE IF NOT EXISTS note_embeddings (
    note_id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    embedding BLOB NOT NULL,
    content_hash TEXT NOT NULL,
    model_name TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedded_at TEXT NOT NULL
);
```

Added to `init_database()` alongside notes and FTS tables.

### 3. `memory_service.py` — Embed on Write

After `create_note()` and `update_note()` write to disk and index in SQLite:
```python
# Fire-and-forget embedding (don't block the response)
try:
    from services.embedding_service import embed_note
    await embed_note(note_path, full_content, db_p)
except ImportError:
    pass  # fastembed not installed — skip silently
```

### 4. `ingest.py` — Embed on Ingest

After `ingest_file()` successfully writes a note:
```python
try:
    from services.embedding_service import embed_note
    await embed_note(rel_path, content, db_path)
except ImportError:
    pass
```

### 5. API Endpoint

```python
# routers/memory.py
@router.post("/reindex-embeddings")
async def reindex_embeddings():
    """Rebuild all note embeddings from markdown files."""
    from services.embedding_service import reindex_all
    count = await reindex_all()
    return {"status": "ok", "notes_embedded": count}
```

---

## Performance Considerations

| Scenario | Cost | Notes |
|----------|------|-------|
| Embed 1 note | ~30ms | Barely noticeable on create/update |
| Embed 100 notes (reindex) | ~3s | Fine for initial setup |
| Embed 1000 notes | ~30s | Background task, progress indicator |
| Search 1000 embeddings | ~8ms | In-memory cosine (768-dim), very fast |
| Model cold start | ~3–4s | First embedding request only |
| Model disk size | ~280MB | One-time download, cached locally |
| Model RAM usage | ~400MB | Loaded lazily on first use |

For larger workspaces (1000+ notes), future optimization: use `sqlite-vss`
or `faiss` for approximate nearest neighbor. For MVP, brute-force cosine
over 1000 vectors is fast enough (~5ms).

---

## Graceful Degradation

`fastembed` is an **optional** dependency. If not installed:
- `embedding_service.py` functions raise `ImportError` caught by callers
- Search falls back to BM25-only (step 19a)
- No error messages in UI — semantic search simply isn't available
- Settings page shows "Semantic search: not available (install fastembed)"

---

## Test Cases

```python
# test_embedding_service.py

def test_embed_text_returns_correct_dimensions():
    """embed_text() returns a list of 384 floats."""

def test_vector_blob_roundtrip():
    """vector_to_blob → blob_to_vector is identity."""

def test_content_hash_changes_with_content():
    """Different content → different hash. Same content → same hash."""

def test_cosine_similarity_identical_vectors():
    """Same vector → similarity 1.0."""

def test_cosine_similarity_orthogonal_vectors():
    """Orthogonal vectors → similarity 0.0."""

async def test_embed_note_skips_unchanged():
    """Second call with same content doesn't re-embed."""

async def test_search_similar_returns_ranked():
    """Notes semantically closer to query rank higher."""

async def test_reindex_all_embeds_every_note():
    """reindex_all processes all .md files in memory/."""
```

---

## Acceptance Criteria

- [ ] `fastembed` added to `requirements.txt` (with comment: optional for semantic search)
- [ ] Model is multilingual (`intfloat/multilingual-e5-base`) — Polish, English, mixed content
- [ ] `note_embeddings` table created on `init_database()`
- [ ] `embed_note()` embeds a note and stores vector in SQLite
- [ ] `embed_note()` skips if content hash unchanged (idempotent)
- [ ] `search_similar(query)` returns notes ranked by cosine similarity
- [ ] Notes embedded automatically on create/update
- [ ] `POST /api/memory/reindex-embeddings` rebuilds all embeddings
- [ ] System works normally if fastembed is not installed (graceful fallback)
- [ ] All new tests pass
