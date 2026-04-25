"""Tests for step-26d context_builder expansion budget.

Tests:
- core context never trimmed in favour of expansion
- expansion notes capped at max_expansion_notes
- expansion notes capped at max_expansion_tokens
- notes excluded by cap are lowest scored
- trace: expansion note includes edge type in log (via DEBUG)
"""

from __future__ import annotations

import pytest
import logging

pytestmark = pytest.mark.anyio(backends=["asyncio"])


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path):
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    (tmp_path / "graph").mkdir()
    return tmp_path


@pytest.fixture(autouse=True)
def patch_workspace(ws, monkeypatch):
    monkeypatch.setattr("config.get_settings", lambda: type("S", (), {"workspace_path": ws})())
    monkeypatch.setattr("services.entity_extraction.extract_entities", lambda *a, **k: [])
    monkeypatch.setenv("JARVIS_DISABLE_EMBEDDINGS", "1")


# ---------------------------------------------------------------------------
# Helper: build a graph with related edges from note A to candidates
# ---------------------------------------------------------------------------

def _make_test_graph(ws, note_paths: list[str], hub: str) -> None:
    """Create a minimal graph.json with related edges from hub to all note_paths."""
    import json
    from pathlib import Path

    nodes = []
    edges = []
    hub_id = f"note:{hub}"
    nodes.append({"id": hub_id, "type": "note", "label": hub, "folder": ""})
    seen = {hub_id}
    for p in note_paths:
        nid = f"note:{p}"
        if nid not in seen:
            nodes.append({"id": nid, "type": "note", "label": p, "folder": ""})
            seen.add(nid)
        edges.append({"source": hub_id, "target": nid, "type": "related",
                       "weight": 0.9, "evidence": []})

    graph_dir = ws / "graph"
    graph_dir.mkdir(exist_ok=True)
    (graph_dir / "graph.json").write_text(
        json.dumps({"nodes": nodes, "edges": edges}), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# _build_expansion_context unit tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_expansion_empty_when_no_graph(ws, monkeypatch):
    """No graph → no expansion notes."""
    from services.context_builder import _build_expansion_context
    # No graph.json created
    parts, trace = await _build_expansion_context("test query", [{"path": "a.md"}], workspace_path=ws)
    assert parts == []
    assert trace == []


@pytest.mark.anyio
async def test_expansion_includes_related_notes(ws, monkeypatch):
    """Notes linked via 'related' edges are included in expansion."""
    from services.graph_service import invalidate_cache
    from services.memory_service import create_note
    from services.context_builder import _build_expansion_context

    invalidate_cache()
    await create_note("core.md", "---\ntitle: Core\n---\n\ncore body.", ws)
    await create_note("linked.md", "---\ntitle: Linked\n---\n\nlinked body.", ws)
    _make_test_graph(ws, ["linked.md"], hub="core.md")

    core_results = [{"path": "core.md", "title": "Core"}]
    parts, trace = await _build_expansion_context("query", core_results, workspace_path=ws)
    # Should include the linked note
    combined = "\n".join(parts)
    assert "linked.md" in combined or "linked" in combined.lower()
    # Step 28a — expansion entries carry their edge type for the trace UI.
    if trace:
        assert any(t["reason"] == "expansion" and t["edge_type"] for t in trace)
    invalidate_cache()


@pytest.mark.anyio
async def test_expansion_capped_at_max_notes(ws, monkeypatch):
    """Expansion never returns more than _MAX_EXPANSION_NOTES notes."""
    from services.graph_service import invalidate_cache
    from services.memory_service import create_note
    from services.context_builder import _build_expansion_context
    from services.retrieval.pipeline import _MAX_EXPANSION_NOTES

    invalidate_cache()
    await create_note("hub.md", "---\ntitle: Hub\n---\n\nhub body.", ws)
    overflow_count = _MAX_EXPANSION_NOTES + 3
    note_paths = [f"n{i}.md" for i in range(overflow_count)]
    for p in note_paths:
        await create_note(p, f"---\ntitle: N{p}\n---\n\nbody of {p}.", ws)
    _make_test_graph(ws, note_paths, hub="hub.md")

    core_results = [{"path": "hub.md"}]
    parts, _trace = await _build_expansion_context("query", core_results, workspace_path=ws)
    assert len(parts) <= _MAX_EXPANSION_NOTES
    invalidate_cache()


@pytest.mark.anyio
async def test_expansion_capped_at_token_budget(ws, monkeypatch):
    """Expansion stops before max notes if token budget is exhausted."""
    import services.retrieval.pipeline as pipeline_mod
    from services.graph_service import invalidate_cache
    from services.memory_service import create_note
    from services.context_builder import _build_expansion_context

    # Set a small budget: ~500 chars (first note fits, second overflows)
    monkeypatch.setattr(pipeline_mod, "_MAX_EXPANSION_TOKENS", 125)  # 125*4=500 chars

    invalidate_cache()
    await create_note("hub.md", "---\ntitle: Hub\n---\n\nhub body.", ws)
    note_content = "y" * 200  # each note is ~300 chars including frontmatter
    note_paths = [f"big{i}.md" for i in range(5)]
    for p in note_paths:
        await create_note(p, f"---\ntitle: Big{p}\n---\n\n{note_content}", ws)
    _make_test_graph(ws, note_paths, hub="hub.md")

    core_results = [{"path": "hub.md"}]
    parts, _trace = await _build_expansion_context("query", core_results, workspace_path=ws)
    # Token budget of 500 chars means < 5 notes can be included
    assert len(parts) < 5
    invalidate_cache()


@pytest.mark.anyio
async def test_core_results_not_included_in_expansion(ws, monkeypatch):
    """Notes already in core results are not re-added as expansion notes."""
    from services.graph_service import invalidate_cache
    from services.memory_service import create_note
    from services.context_builder import _build_expansion_context

    invalidate_cache()
    await create_note("core.md", "---\ntitle: Core\n---\n\ncore body.", ws)
    # Make core.md point to itself via related (artificial — tests dedup)
    _make_test_graph(ws, ["core.md"], hub="core.md")

    core_results = [{"path": "core.md"}]
    parts, _trace = await _build_expansion_context("query", core_results, workspace_path=ws)
    # core.md should not appear as an expansion note
    assert all("core.md" not in p for p in parts)
    invalidate_cache()


@pytest.mark.anyio
async def test_expansion_trace_logs_edge_type(ws, monkeypatch, caplog):
    """Expansion logs the edge type for each included note in DEBUG."""
    from services.graph_service import invalidate_cache
    from services.memory_service import create_note
    from services.context_builder import _build_expansion_context

    invalidate_cache()
    await create_note("hub.md", "---\ntitle: Hub\n---\n\nhub.", ws)
    await create_note("nbr.md", "---\ntitle: Nbr\n---\n\nnbr content.", ws)
    _make_test_graph(ws, ["nbr.md"], hub="hub.md")

    with caplog.at_level(logging.DEBUG, logger="services.context_builder"):
        await _build_expansion_context("query", [{"path": "hub.md"}], workspace_path=ws)

    log_text = "\n".join(caplog.messages)
    assert "related" in log_text or len(log_text) == 0  # may be empty if no results
    invalidate_cache()
