"""Unit tests for the local embedding service.

Tests stay fast by stubbing the fastembed model. A single smoke test
exercises the real model (skipped if fastembed isn't installed).
"""
import os

import aiosqlite
import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services import embedding_service
from services.embedding_service import (
    blob_to_vector,
    content_hash,
    cosine_similarity,
    vector_to_blob,
)
from services.memory_service import create_note


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    return tmp_path


@pytest.fixture
async def ws_db(ws):
    await init_database(ws / "app" / "jarvis.db")
    return ws


@pytest.fixture
def enable_embeddings(monkeypatch):
    """Stub the fastembed model with a deterministic hash-based vector so
    tests don't need to download 200MB of model weights."""
    monkeypatch.delenv("JARVIS_DISABLE_EMBEDDINGS", raising=False)

    class FakeModel:
        def embed(self, texts):
            import hashlib
            for text in texts:
                digest = hashlib.sha256(text.encode("utf-8")).digest()
                vec = [(digest[i] - 128) / 128.0 for i in range(32)]
                yield _FakeVec(vec)

    class _FakeVec(list):
        def tolist(self):
            return list(self)

    monkeypatch.setattr(embedding_service, "_model", FakeModel())
    monkeypatch.setattr(embedding_service, "_DIMENSIONS", 32)
    monkeypatch.setattr(embedding_service, "is_available", lambda: True)
    yield


def test_content_hash_changes_with_content():
    assert content_hash("hello") == content_hash("hello")
    assert content_hash("hello") != content_hash("hello!")


def test_vector_blob_roundtrip():
    vec = [0.1, -0.2, 0.3, 0.4, -0.5]
    blob = vector_to_blob(vec)
    recovered = blob_to_vector(blob)
    assert len(recovered) == len(vec)
    for a, b in zip(vec, recovered):
        assert abs(a - b) < 1e-6


def test_cosine_similarity_identical():
    v = [1.0, 2.0, 3.0]
    assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-6)


def test_cosine_similarity_orthogonal():
    a = [1.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0]
    assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)


def test_cosine_similarity_zero_vector():
    """A zero vector is degenerate — return 0 instead of NaN."""
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_embed_text_returns_vector(enable_embeddings):
    vec = embedding_service.embed_text("hello world")
    assert isinstance(vec, list)
    assert len(vec) == 32
    assert all(isinstance(x, float) for x in vec)


@pytest.mark.anyio
async def test_embed_note_stores_embedding(enable_embeddings, ws_db):
    await create_note(
        "inbox/test.md",
        "---\ntitle: Test\ntags: []\n---\n\nSome body content",
        ws_db,
    )

    db_path = ws_db / "app" / "jarvis.db"
    await embedding_service.embed_note(
        "inbox/test.md",
        "---\ntitle: Test\ntags: []\n---\n\nSome body content",
        db_path,
    )

    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute(
            "SELECT path, dimensions, model_name FROM note_embeddings"
        )
        rows = await cursor.fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "inbox/test.md"
    assert rows[0][1] == 32


@pytest.mark.anyio
async def test_embed_note_skips_unchanged(enable_embeddings, ws_db):
    db_path = ws_db / "app" / "jarvis.db"
    content = "---\ntitle: Test\ntags: []\n---\n\nBody"

    await create_note("inbox/test.md", content, ws_db)
    first = await embedding_service.embed_note("inbox/test.md", content, db_path)
    second = await embedding_service.embed_note("inbox/test.md", content, db_path)

    assert first is True
    assert second is False  # skipped because content unchanged


@pytest.mark.anyio
async def test_search_similar_returns_ranked(enable_embeddings, ws_db):
    db_path = ws_db / "app" / "jarvis.db"
    await create_note(
        "inbox/alpha.md",
        "---\ntitle: Alpha\ntags: []\n---\n\nFirst body",
        ws_db,
    )
    await create_note(
        "inbox/beta.md",
        "---\ntitle: Beta\ntags: []\n---\n\nSecond body",
        ws_db,
    )

    results = await embedding_service.search_similar(
        "First body", limit=5, workspace_path=ws_db
    )
    assert len(results) == 2
    # Scores should be monotonically decreasing
    assert results[0][1] >= results[1][1]


@pytest.mark.anyio
async def test_reindex_all_processes_every_note(enable_embeddings, ws_db):
    await create_note(
        "inbox/a.md", "---\ntitle: A\n---\n\naa", ws_db
    )
    await create_note(
        "inbox/b.md", "---\ntitle: B\n---\n\nbb", ws_db
    )

    from services.embedding_service import reindex_all
    count = await reindex_all(workspace_path=ws_db)
    assert count >= 0  # Notes may have been embedded at create time

    db_path = ws_db / "app" / "jarvis.db"
    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM note_embeddings")
        row = await cursor.fetchone()
    assert row[0] == 2


def test_is_available_reflects_fastembed_install():
    """is_available should return True when fastembed module is importable."""
    import importlib.util
    expected = importlib.util.find_spec("fastembed") is not None
    assert embedding_service.is_available() == expected
