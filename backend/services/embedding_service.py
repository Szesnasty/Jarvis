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
    """Re-embed all notes (note-level + chunk-level) from markdown files. Returns count embedded."""
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
        # Also embed chunks for this note
        try:
            await embed_note_chunks(rel_path, content, db_path)
        except Exception:
            pass
    return count


async def delete_embedding(note_path: str, db_path: Path) -> None:
    """Remove embedding for a deleted note."""
    import aiosqlite
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute("DELETE FROM note_embeddings WHERE path = ?", (note_path,))
        await db.execute("DELETE FROM chunk_embeddings WHERE path = ?", (note_path,))
        await db.execute("DELETE FROM note_chunks WHERE path = ?", (note_path,))
        await db.commit()


# --- Step 20a: Chunk-level embeddings ---


async def embed_note_chunks(
    note_path: str,
    content: str,
    db_path: Path,
    subject_type: str = "note",
) -> int:
    """Chunk a note, embed each chunk, store in SQLite.

    Args:
        subject_type: the subject kind (``note``, ``jira_issue``,
            ``url_ingest``, etc.).  Stored in ``note_chunks.subject_type``
            and passed to the chunker for section-weighting.

    Returns number of chunks embedded.
    """
    import aiosqlite
    from services.chunking import chunk_markdown
    from utils.markdown import parse_frontmatter

    fm, body = parse_frontmatter(content)
    chunks = chunk_markdown(
        content,
        title=fm.get("title", ""),
        tags=[str(t) for t in fm.get("tags", [])],
        subject_kind=subject_type,
    )

    async with aiosqlite.connect(str(db_path)) as db:
        # Get note_id
        cursor = await db.execute("SELECT id FROM notes WHERE path = ?", (note_path,))
        row = await cursor.fetchone()
        if not row:
            return 0
        note_id = row[0]

        # Delete old chunks for this note
        await db.execute("DELETE FROM chunk_embeddings WHERE path = ?", (note_path,))
        await db.execute("DELETE FROM note_chunks WHERE path = ?", (note_path,))

        now = datetime.now(timezone.utc).isoformat()
        count = 0
        for chunk in chunks:
            # Insert chunk record
            cursor = await db.execute(
                "INSERT INTO note_chunks (note_id, path, chunk_index, section_title, chunk_text, token_count, subject_type, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (note_id, note_path, chunk.index, chunk.section_title, chunk.text, chunk.token_count, subject_type, now),
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


async def search_similar_chunks(
    query: str,
    limit: int = 10,
    workspace_path: Optional[Path] = None,
) -> List[dict]:
    """Find most similar chunks, grouped by parent note.

    Returns list of dicts with keys: path, best_chunk_score,
    best_chunk_text, best_chunk_section, chunk_scores.
    """
    import aiosqlite
    from config import get_settings

    db_path = (workspace_path or get_settings().workspace_path) / "app" / "jarvis.db"
    if not db_path.exists():
        return []

    query_vec = embed_query(query)

    async with aiosqlite.connect(str(db_path)) as db:
        try:
            cursor = await db.execute(
                "SELECT ce.path, ce.chunk_index, ce.embedding, nc.chunk_text, nc.section_title "
                "FROM chunk_embeddings ce "
                "JOIN note_chunks nc ON ce.chunk_id = nc.id"
            )
            rows = await cursor.fetchall()
        except Exception:
            return []

    if not rows:
        return []

    # Score all chunks
    scored = []
    for path, idx, blob, text, section in rows:
        vec = blob_to_vector(blob)
        sim = cosine_similarity(query_vec, vec)
        scored.append((path, idx, sim, text, section))

    scored.sort(key=lambda x: x[2], reverse=True)

    # Group by parent note, keep best chunk per note
    note_groups: dict = {}
    for path, idx, sim, text, section in scored:
        if path not in note_groups:
            note_groups[path] = {
                "path": path,
                "best_chunk_score": sim,
                "best_chunk_text": text[:1200],
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


async def reindex_all_chunks(workspace_path: Optional[Path] = None) -> int:
    """Re-chunk and re-embed all notes. Returns count of chunks embedded."""
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
        try:
            n = await embed_note_chunks(rel_path, content, db_path)
            count += n
        except Exception as e:
            logger.warning("Failed to embed chunks for %s: %s", rel_path, e)
    return count


# --- Step 20b: Node embeddings for semantic graph anchoring ---


async def embed_graph_nodes(
    graph_nodes: List[dict],
    db_path: Path,
) -> int:
    """Embed graph node labels in batch. Returns count of newly embedded nodes."""
    import aiosqlite

    embeddable = [n for n in graph_nodes if len(n.get("label", "")) >= 2]
    if not embeddable:
        return 0

    # Batch embed all labels
    texts = [n["label"] for n in embeddable]
    vectors = embed_texts(texts)

    async with aiosqlite.connect(str(db_path)) as db:
        count = 0
        for node, vec in zip(embeddable, vectors):
            c_hash = content_hash(node["label"])

            # Check if already embedded with same label
            cursor = await db.execute(
                "SELECT content_hash FROM node_embeddings WHERE node_id = ?",
                (node["id"],),
            )
            row = await cursor.fetchone()
            if row and row[0] == c_hash:
                continue  # unchanged

            blob = vector_to_blob(vec)
            now = datetime.now(timezone.utc).isoformat()
            await db.execute("""
                INSERT OR REPLACE INTO node_embeddings
                (node_id, node_type, label, embedding, content_hash, model_name, dimensions, embedded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (node["id"], node["type"], node["label"], blob, c_hash, _MODEL_NAME, _DIMENSIONS, now))
            count += 1

        await db.commit()
    return count


async def find_similar_nodes(
    query: str,
    limit: int = 5,
    node_types: Optional[List[str]] = None,
    workspace_path: Optional[Path] = None,
) -> List[Tuple[str, str, float]]:
    """Find graph nodes whose labels are semantically similar to query.

    Returns: [(node_id, label, similarity_score), ...]
    """
    import aiosqlite
    from config import get_settings

    db_path = (workspace_path or get_settings().workspace_path) / "app" / "jarvis.db"
    if not db_path.exists():
        return []

    query_vec = embed_query(query)

    async with aiosqlite.connect(str(db_path)) as db:
        try:
            if node_types:
                placeholders = ",".join("?" * len(node_types))
                cursor = await db.execute(
                    f"SELECT node_id, label, embedding FROM node_embeddings WHERE node_type IN ({placeholders})",
                    node_types,
                )
            else:
                cursor = await db.execute("SELECT node_id, label, embedding FROM node_embeddings")
            rows = await cursor.fetchall()
        except Exception:
            return []

    scored = []
    for node_id, label, blob in rows:
        vec = blob_to_vector(blob)
        sim = cosine_similarity(query_vec, vec)
        scored.append((node_id, label, sim))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:limit]


def is_available() -> bool:
    """Check if fastembed is installed and usable."""
    try:
        import fastembed  # noqa: F401
        return True
    except ImportError:
        return False
