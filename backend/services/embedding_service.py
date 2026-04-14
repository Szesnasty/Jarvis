"""Local embedding service for semantic search.

Uses fastembed (ONNX Runtime) to run a multilingual embedding model on CPU.
No API calls, no external services, all data stays local.

The model is lazy-loaded on first use (~3-4s cold start, ~400MB RAM).
Embeddings are stored in SQLite as BLOB (float32 packed).
Content hash ensures we skip re-embedding unchanged notes.
"""

import hashlib
import logging
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# Lazy-loaded model singleton
_model = None
_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_DIMENSIONS = 384


def _get_model():
    """Lazy-load embedding model on first use."""
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        logger.info("Loading embedding model %s...", _MODEL_NAME)
        _model = TextEmbedding(model_name=_MODEL_NAME)
        logger.info("Embedding model loaded.")
    return _model


def embed_text(text: str) -> List[float]:
    """Embed a single text string -> float vector."""
    model = _get_model()
    embeddings = list(model.embed([text]))
    return embeddings[0].tolist()


def embed_query(text: str) -> List[float]:
    """Embed a query string -> float vector."""
    return embed_text(text)


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
    import numpy as np
    a_np = np.array(a, dtype=np.float32)
    b_np = np.array(b, dtype=np.float32)
    dot = np.dot(a_np, b_np)
    norm = np.linalg.norm(a_np) * np.linalg.norm(b_np)
    return float(dot / norm) if norm > 0 else 0.0


async def embed_note(
    note_path: str,
    content: str,
    db_path: Path,
) -> bool:
    """Embed a single note and store in SQLite.

    Returns True if embedding was computed, False if skipped (unchanged).
    """
    import aiosqlite
    from utils.markdown import parse_frontmatter

    fm, body = parse_frontmatter(content)
    title = fm.get("title", "")
    tags = " ".join(str(t) for t in fm.get("tags", []))
    # Combine title (weighted by repetition) + tags + body for embedding
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
            return False  # Skip — content unchanged

        vec = embed_text(embed_input)
        blob = vector_to_blob(vec)

        # Get note_id
        cursor = await db.execute(
            "SELECT id FROM notes WHERE path = ?", (note_path,)
        )
        note_row = await cursor.fetchone()
        if not note_row:
            return False

        now = datetime.now(timezone.utc).isoformat()
        await db.execute("""
            INSERT OR REPLACE INTO note_embeddings
            (note_id, path, embedding, content_hash, model_name, dimensions, embedded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (note_row[0], note_path, blob, new_hash, _MODEL_NAME, _DIMENSIONS, now))
        await db.commit()
        return True


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

    query_vec = embed_query(query)

    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute(
            "SELECT path, embedding FROM note_embeddings"
        )
        rows = await cursor.fetchall()

    if not rows:
        return []

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

    if not mem.exists():
        return 0

    count = 0
    for md_file in mem.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="replace")
        rel_path = str(md_file.relative_to(mem))
        embedded = await embed_note(rel_path, content, db_path)
        if embedded:
            count += 1
    return count


async def delete_embedding(note_path: str, db_path: Path) -> None:
    """Remove embedding for a deleted note."""
    import aiosqlite
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("DELETE FROM note_embeddings WHERE path = ?", (note_path,))
        await db.commit()


def is_available() -> bool:
    """Check if fastembed is installed and usable."""
    try:
        import fastembed  # noqa: F401
        return True
    except ImportError:
        return False
