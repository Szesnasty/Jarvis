"""Step 25 PR 5 — provenance edges (source / batch) + dismissed suggestions."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.connection_service import (
    _classify_source,
    _emit_provenance_edges,
    connect_note,
)
from services.dismissed_suggestions import (
    DISMISSED_SUGGESTIONS_SQL,
    dismiss,
    list_dismissed_for,
    undismiss,
)
from services.graph_service import (
    invalidate_cache,
    load_graph,
    rebuild_graph,
)
from services.memory_service import _db_path, create_note


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture(autouse=True)
def clear_cache():
    invalidate_cache()
    yield
    invalidate_cache()


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    (tmp_path / "graph").mkdir()
    return tmp_path


@pytest.fixture
async def ws_db(ws):
    await init_database(ws / "app" / "jarvis.db")
    return ws


# ---------------------------------------------------------------------------
# _classify_source — pure helper, no IO
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://example.com/article", "url"),
        ("HTTPS://example.com", "url"),
        ("jira:PROJ-123", "jira"),
        ("inbox/notes/whitepaper.pdf", "file"),
        ("data/export.csv", "file"),
        ("README.md", "file"),
        ("manual user paste", "other"),
    ],
)
def test_classify_source(raw, expected):
    assert _classify_source(raw) == expected


# ---------------------------------------------------------------------------
# Provenance edges
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_emit_provenance_edges_source_only(ws_db, monkeypatch):
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities", lambda *_a, **_kw: [],
    )
    await create_note(
        "inbox/raw.md",
        "---\ntitle: Raw\nsource: https://example.com/post\n---\n\nbody",
        ws_db,
    )
    rebuild_graph(ws_db)

    fm = {"source": "https://example.com/post"}
    added = _emit_provenance_edges("inbox/raw.md", fm, ws_db)
    assert added == 1

    g = load_graph(workspace_path=ws_db)
    src_edges = [e for e in g.edges if e.type == "derived_from"]
    assert len(src_edges) == 1
    assert src_edges[0].source == "note:inbox/raw.md"
    assert src_edges[0].target.startswith("source:")
    # Idempotent: re-running adds nothing.
    assert _emit_provenance_edges("inbox/raw.md", fm, ws_db) == 0


@pytest.mark.anyio
async def test_emit_provenance_edges_batch_only(ws_db, monkeypatch):
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities", lambda *_a, **_kw: [],
    )
    await create_note(
        "inbox/a.md", "---\ntitle: A\n---\n\nbody", ws_db,
    )
    rebuild_graph(ws_db)
    fm = {"batch_id": "import-2026-04-27"}
    added = _emit_provenance_edges("inbox/a.md", fm, ws_db)
    assert added == 1

    g = load_graph(workspace_path=ws_db)
    batch_edges = [e for e in g.edges if e.type == "same_batch"]
    assert len(batch_edges) == 1
    assert batch_edges[0].target == "batch:import-2026-04-27"


@pytest.mark.anyio
async def test_emit_provenance_edges_both(ws_db, monkeypatch):
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities", lambda *_a, **_kw: [],
    )
    await create_note("inbox/x.md", "---\ntitle: X\n---\n\nbody", ws_db)
    rebuild_graph(ws_db)
    fm = {"source": "https://example.com", "batch_id": "b1"}
    assert _emit_provenance_edges("inbox/x.md", fm, ws_db) == 2


@pytest.mark.anyio
async def test_emit_provenance_edges_no_metadata(ws_db, monkeypatch):
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities", lambda *_a, **_kw: [],
    )
    await create_note("inbox/y.md", "---\ntitle: Y\n---\n\nbody", ws_db)
    rebuild_graph(ws_db)
    assert _emit_provenance_edges("inbox/y.md", {}, ws_db) == 0


# ---------------------------------------------------------------------------
# dismissed_suggestions module
# ---------------------------------------------------------------------------


def test_dismiss_then_list(tmp_path):
    db = tmp_path / "x.db"
    dismiss(db, "a.md", "b.md")
    dismiss(db, "a.md", "c.md")
    dismiss(db, "z.md", "b.md")
    result = list_dismissed_for(db, "a.md")
    assert result == {"b.md", "c.md"}


def test_undismiss(tmp_path):
    db = tmp_path / "x.db"
    dismiss(db, "a.md", "b.md")
    assert "b.md" in list_dismissed_for(db, "a.md")
    undismiss(db, "a.md", "b.md")
    assert list_dismissed_for(db, "a.md") == set()


def test_list_dismissed_for_missing_db_is_empty(tmp_path):
    assert list_dismissed_for(tmp_path / "nope.db", "a.md") == set()


def test_dismiss_is_idempotent(tmp_path):
    db = tmp_path / "x.db"
    dismiss(db, "a.md", "b.md")
    dismiss(db, "a.md", "b.md")  # same pair, INSERT OR REPLACE
    assert list_dismissed_for(db, "a.md") == {"b.md"}


# ---------------------------------------------------------------------------
# Dismissal filter inside connect_note
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_connect_note_drops_dismissed_targets(ws_db, monkeypatch):
    """A dismissed target must never appear in suggested_related."""
    monkeypatch.setattr(
        "services.entity_extraction.extract_entities", lambda *_a, **_kw: [],
    )
    # Two notes that share clearly overlapping content so BM25 will link them.
    body = "kubernetes deployment rolling update strategy probes liveness"
    await create_note("a.md", f"---\ntitle: A\n---\n\n{body}", ws_db)
    await create_note("b.md", f"---\ntitle: B\n---\n\n{body}", ws_db)

    # Sanity check: without dismissal, b.md is suggested for a.md.
    res = await connect_note("a.md", workspace_path=ws_db)
    assert any(s.path == "b.md" for s in res.suggested), (
        f"baseline expected b.md in suggestions, got {[s.path for s in res.suggested]}"
    )

    # Dismiss the pair, re-run, and confirm it's gone.
    dismiss(_db_path(ws_db), "a.md", "b.md")
    res2 = await connect_note("a.md", workspace_path=ws_db)
    assert not any(s.path == "b.md" for s in res2.suggested)


# ---------------------------------------------------------------------------
# Schema registration in init_database
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_init_database_creates_dismissed_suggestions_table(ws_db):
    import sqlite3
    with sqlite3.connect(str(_db_path(ws_db))) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='dismissed_suggestions'"
        ).fetchall()
    assert rows, "dismissed_suggestions table should be created by init_database"


def test_dismissed_suggestions_sql_constant_present():
    assert "dismissed_suggestions" in DISMISSED_SUGGESTIONS_SQL
    assert "PRIMARY KEY" in DISMISSED_SUGGESTIONS_SQL
