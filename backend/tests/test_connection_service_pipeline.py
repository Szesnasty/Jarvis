"""End-to-end tests for the Smart Connect ingest pipeline (Step 25, PR 1).

These tests run with ``JARVIS_DISABLE_EMBEDDINGS=1`` (set in conftest), so
they exercise the BM25 + frontmatter + graph-update path without loading
the embedding model. Embedding-specific behaviour is covered in
``test_embedding_service`` and ``test_hybrid_retrieval``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.connection_service import connect_note
from services.ingest import fast_ingest
from utils.markdown import parse_frontmatter


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    (tmp_path / "memory" / "knowledge").mkdir(parents=True)
    (tmp_path / "memory" / "inbox").mkdir(parents=True)
    (tmp_path / "app").mkdir()
    (tmp_path / "graph").mkdir()
    return tmp_path


@pytest.fixture
async def ws_db(ws: Path) -> Path:
    await init_database(ws / "app" / "jarvis.db")
    return ws


def _write_note(ws: Path, rel: str, title: str, body: str, tags=None) -> Path:
    full = ws / "memory" / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    fm_lines = ["---", f"title: {title}"]
    if tags:
        fm_lines.append("tags: [" + ", ".join(tags) + "]")
    fm_lines.append("---")
    full.write_text("\n".join(fm_lines) + "\n\n" + body, encoding="utf-8")
    return full


async def _index(ws: Path, rel: str) -> None:
    from services.memory_service import index_note_file

    await index_note_file(rel, workspace_path=ws)


@pytest.mark.anyio
async def test_connect_note_writes_suggested_related_block(ws_db):
    # Two notes that share vocabulary
    _write_note(ws_db, "knowledge/auth.md", "Auth pipeline",
                "Discusses authentication, JWT, OAuth tokens, login flow.",
                tags=["auth"])
    await _index(ws_db, "knowledge/auth.md")

    _write_note(ws_db, "knowledge/login.md", "Login flow",
                "OAuth, JWT and authentication during the login flow.",
                tags=["auth"])
    await _index(ws_db, "knowledge/login.md")

    result = await connect_note("knowledge/login.md", workspace_path=ws_db)

    # The other note should appear as a suggestion
    assert any(s.path == "knowledge/auth.md" for s in result.suggested)

    # Frontmatter has been written
    raw = (ws_db / "memory" / "knowledge" / "login.md").read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(raw)
    suggested = fm.get("suggested_related", [])
    assert isinstance(suggested, list)
    assert any(item.get("path") == "knowledge/auth.md" for item in suggested)


@pytest.mark.anyio
async def test_connect_note_never_suggests_self(ws_db):
    _write_note(ws_db, "knowledge/solo.md", "Solo note",
                "unique words quokka platypus narwhal " * 20)
    await _index(ws_db, "knowledge/solo.md")

    result = await connect_note("knowledge/solo.md", workspace_path=ws_db)
    assert all(s.path != "knowledge/solo.md" for s in result.suggested)


@pytest.mark.anyio
async def test_connect_note_does_not_write_to_related(ws_db):
    """`related:` is reserved for user-confirmed links; suggestions never touch it."""
    _write_note(ws_db, "knowledge/a.md", "Topic A", "shared word shared word shared")
    _write_note(ws_db, "knowledge/b.md", "Topic B", "shared word shared word shared")
    await _index(ws_db, "knowledge/a.md")
    await _index(ws_db, "knowledge/b.md")

    await connect_note("knowledge/b.md", workspace_path=ws_db)

    raw = (ws_db / "memory" / "knowledge" / "b.md").read_text(encoding="utf-8")
    fm, _ = parse_frontmatter(raw)
    assert "related" not in fm or fm["related"] in (None, [])


@pytest.mark.anyio
async def test_fast_ingest_skips_full_rebuild(ws_db, monkeypatch, tmp_path):
    """fast_ingest must call connect_note exactly once and never rebuild_graph."""
    src = tmp_path / "src" / "note.md"
    src.parent.mkdir()
    src.write_text(
        "---\ntitle: Hello\ntags: [demo]\n---\n\nA short note about hello world.",
        encoding="utf-8",
    )

    rebuild_calls = {"count": 0}
    connect_calls = {"count": 0}

    def _fake_rebuild(*a, **kw):
        rebuild_calls["count"] += 1

    real_connect = __import__(
        "services.connection_service", fromlist=["connect_note"],
    ).connect_note

    async def _fake_connect(note_path, workspace_path=None, mode="fast"):
        connect_calls["count"] += 1
        return await real_connect(
            note_path, workspace_path=workspace_path, mode=mode,
        )

    import services.graph_service as gs
    import services.connection_service as cs

    monkeypatch.setattr(gs, "rebuild_graph", _fake_rebuild)
    monkeypatch.setattr(cs, "connect_note", _fake_connect)

    result = await fast_ingest(src, "knowledge", workspace_path=ws_db)

    assert rebuild_calls["count"] == 0, "fast_ingest must not trigger a full graph rebuild"
    assert connect_calls["count"] == 1
    assert "connections" in result
    assert result["connections"] is not None


@pytest.mark.anyio
async def test_fast_ingest_returns_connection_payload(ws_db, tmp_path):
    src = tmp_path / "src" / "doc.md"
    src.parent.mkdir()
    src.write_text(
        "---\ntitle: Doc\ntags: [imported]\n---\n\nBody text body text body text.",
        encoding="utf-8",
    )
    result = await fast_ingest(src, "knowledge", workspace_path=ws_db)

    assert result["connections"] is not None
    assert "suggested" in result["connections"]
    assert "strong_count" in result["connections"]
    assert isinstance(result["connections"]["suggested"], list)
