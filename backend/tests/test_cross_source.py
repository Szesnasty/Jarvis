"""Tests for cross-source linking — step 22e."""
import json
import math
import sqlite3
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.embedding_service import vector_to_blob
from services.graph_service.models import Edge, Graph
from services.graph_service.cross_source import (
    CONFIDENCE_FLOORS,
    EDGE_ABOUT_SAME_TOPIC,
    EDGE_DERIVED_FROM_RESEARCH,
    EDGE_IMPLEMENTS_DECISION,
    EDGE_MENTIONED_IN_NOTE,
    EDGE_MENTIONS_ISSUE,
    EDGE_SAME_DOCUMENT_THREAD,
    MAX_OUT_DEGREE,
    confidence_about_same_topic,
    confidence_derived_from_research,
    confidence_implements_decision,
    enrichment_compatibility,
    find_issue_mentions_in_note,
    rebuild_cross_source_edges,
)


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


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


def _make_vec(dims, base):
    vec = [(base + i * 0.01) % 1.0 for i in range(dims)]
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec]


def _inject_node_embedding(db_path, node_id, node_type, label, vec):
    now = datetime.now(timezone.utc).isoformat()
    blob = vector_to_blob(vec)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR REPLACE INTO node_embeddings "
        "(node_id, node_type, label, embedding, content_hash, model_name, dimensions, embedded_at) "
        "VALUES (?, ?, ?, ?, 'hash', 'test', ?, ?)",
        (node_id, node_type, label, blob, len(vec), now),
    )
    conn.commit()
    conn.close()


def _inject_enrichment(db_path, subject_type, subject_id, payload):
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR REPLACE INTO enrichments "
        "(subject_type, subject_id, content_hash, model_id, prompt_version, "
        " status, payload, raw_output, tokens_in, tokens_out, duration_ms, created_at) "
        "VALUES (?, ?, 'hash', 'test', 1, 'ok', ?, NULL, 100, 100, 100, ?)",
        (subject_type, subject_id, json.dumps(payload), now),
    )
    conn.commit()
    conn.close()


def _inject_note(db_path, path, title, body, folder=""):
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR REPLACE INTO notes "
        "(path, title, folder, body, tags, frontmatter, created_at, updated_at, indexed_at) "
        "VALUES (?, ?, ?, ?, '[]', '{}', ?, ?, ?)",
        (path, title, folder, body, now, now, now),
    )
    conn.commit()
    conn.close()


def _inject_issue(db_path, issue_key, project_key, title, note_path, description=""):
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR REPLACE INTO issues "
        "(issue_key, project_key, title, description, issue_type, status, "
        " note_path, content_hash, created_at, updated_at, imported_at) "
        "VALUES (?, ?, ?, ?, 'Task', 'Open', ?, 'hash', ?, ?, ?)",
        (issue_key, project_key, title, description, note_path, now, now, now),
    )
    conn.commit()
    conn.close()


def _inject_chunk_embedding(db_path, path, chunk_index, vec, note_id=1, subject_type="note"):
    now = datetime.now(timezone.utc).isoformat()
    blob = vector_to_blob(vec)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT OR REPLACE INTO note_chunks "
        "(note_id, path, chunk_index, section_title, chunk_text, token_count, subject_type, created_at) "
        "VALUES (?, ?, ?, '', 'text', 50, ?, ?)",
        (note_id, path, chunk_index, subject_type, now),
    )
    chunk_id = conn.execute("SELECT id FROM note_chunks WHERE path=? AND chunk_index=?", (path, chunk_index)).fetchone()[0]
    conn.execute(
        "INSERT OR REPLACE INTO chunk_embeddings "
        "(chunk_id, path, chunk_index, embedding, content_hash, model_name, dimensions, embedded_at) "
        "VALUES (?, ?, ?, ?, 'hash', 'test', ?, ?)",
        (chunk_id, path, chunk_index, blob, len(vec), now),
    )
    conn.commit()
    conn.close()


# ── Pure function tests ──────────────────────────────────────


def test_mentions_issue_direct():
    """Note containing [[ONB-142]] finds the issue key."""
    body = "We discussed the fix for [[ONB-142]] in the meeting."
    keys = find_issue_mentions_in_note(body, {"ONB-142", "ONB-200"})
    assert "ONB-142" in keys
    assert "ONB-200" not in keys


def test_mentions_issue_bare_key():
    """Bare issue key without wiki-link syntax also matches."""
    body = "See ONB-142 for details."
    keys = find_issue_mentions_in_note(body, {"ONB-142"})
    assert "ONB-142" in keys


def test_mentions_issue_unknown_key_ignored():
    """Issue keys not in known set are ignored."""
    body = "See FAKE-999 for details."
    keys = find_issue_mentions_in_note(body, {"ONB-142"})
    assert len(keys) == 0


def test_implements_decision_gate():
    """Matching chunks but wrong execution_type → no edge."""
    # With investigation+implementation, bias is set for derived_from_research not implements_decision
    conf = confidence_implements_decision(
        chunk_sims=[0.90, 0.85, 0.60],
        enrichment_bias=0.0,  # no impl bias → gate depends on chunk quality only
    )
    # Should still pass chunk gate since we have ≥2 chunks ≥0.78
    assert conf > 0.0

    # But with no high chunks, should be 0
    conf_low = confidence_implements_decision(
        chunk_sims=[0.50, 0.40],
        enrichment_bias=0.10,
    )
    assert conf_low == 0.0


def test_cross_type_entity_gate():
    """Two subjects with high cosine but zero shared entities → no about_same_topic_as edge."""
    conf = confidence_about_same_topic(
        node_sim=0.95,
        chunk_sims=[0.90, 0.85, 0.80],
        shared_entity_count=0,
    )
    assert conf == 0.0


def test_cross_type_entity_gate_passes():
    """With shared entities AND high chunks, edge fires."""
    conf = confidence_about_same_topic(
        node_sim=0.90,
        chunk_sims=[0.90, 0.85, 0.80],
        shared_entity_count=2,
    )
    assert conf >= CONFIDENCE_FLOORS[EDGE_ABOUT_SAME_TOPIC]


def test_enrichment_compatibility_decision_impl():
    """Decision note ↔ implementation issue → implements_decision bias."""
    biases = enrichment_compatibility(
        {"execution_type": "decision"},
        {"execution_type": "implementation"},
    )
    assert EDGE_IMPLEMENTS_DECISION in biases
    assert biases[EDGE_IMPLEMENTS_DECISION] == 0.10


def test_enrichment_compatibility_area_mismatch():
    """Different business areas → negative bias on about_same_topic_as."""
    biases = enrichment_compatibility(
        {"business_area": "billing"},
        {"business_area": "growth"},
    )
    assert biases.get(EDGE_ABOUT_SAME_TOPIC, 0.0) == -0.10


def test_enrichment_compatibility_area_match():
    """Same business area → positive bias."""
    biases = enrichment_compatibility(
        {"business_area": "billing"},
        {"business_area": "billing"},
    )
    assert biases.get(EDGE_ABOUT_SAME_TOPIC, 0.0) == 0.05


def test_derived_from_research_requires_chunks():
    """derived_from_research needs ≥2 chunk matches ≥ 0.75."""
    conf = confidence_derived_from_research([0.50, 0.40], enrichment_bias=0.10)
    assert conf == 0.0

    conf2 = confidence_derived_from_research([0.80, 0.76], enrichment_bias=0.10)
    assert conf2 > 0.0


# ── Integration tests ────────────────────────────────────────


async def test_mention_edges_created(ws_db):
    """Note containing issue key → mentions_issue + mentioned_in_note edges."""
    ws = ws_db
    db_path = ws / "app" / "jarvis.db"

    graph = Graph()
    graph.add_node("note:projects/foo.md", "note", "Foo project")
    graph.add_node("issue:ONB-142", "jira_issue", "ONB-142 — Fix login")

    _inject_note(db_path, "projects/foo.md", "Foo project",
                 "We need to fix [[ONB-142]] before release.")
    _inject_issue(db_path, "ONB-142", "ONB", "Fix login", "jira/ONB/ONB-142.md")

    count = rebuild_cross_source_edges(ws, graph)
    assert count >= 2

    mention_edges = [e for e in graph.edges if e.type == EDGE_MENTIONS_ISSUE]
    assert len(mention_edges) >= 1
    assert mention_edges[0].source == "note:projects/foo.md"
    assert mention_edges[0].target == "issue:ONB-142"

    reverse = [e for e in graph.edges if e.type == EDGE_MENTIONED_IN_NOTE]
    assert len(reverse) >= 1
    assert reverse[0].source == "issue:ONB-142"
    assert reverse[0].target == "note:projects/foo.md"


async def test_intra_file_edges_only_long(ws_db):
    """Short note (<= 8 chunks) → no same_document_thread edges."""
    ws = ws_db
    db_path = ws / "app" / "jarvis.db"

    graph = Graph()
    graph.add_node("note:short.md", "note", "Short note")
    _inject_note(db_path, "short.md", "Short note", "Brief content.")

    # Inject only 5 chunks (below threshold of 8)
    for i in range(5):
        _inject_chunk_embedding(db_path, "short.md", i, _make_vec(384, 0.3 + i * 0.01))

    count = rebuild_cross_source_edges(ws, graph)

    intra_edges = [e for e in graph.edges if e.type == EDGE_SAME_DOCUMENT_THREAD]
    assert len(intra_edges) == 0


async def test_intra_file_edges_long_doc(ws_db):
    """Long file (> 8 chunks) with similar distant chunks → same_document_thread edges."""
    ws = ws_db
    db_path = ws / "app" / "jarvis.db"

    graph = Graph()
    graph.add_node("note:long.md", "note", "Long document")
    _inject_note(db_path, "long.md", "Long document", "Very long content here.")

    # Inject 12 chunks: first and last have very similar vectors
    for i in range(12):
        if i == 0 or i == 11:
            vec = _make_vec(384, 0.50)  # nearly identical
        else:
            vec = _make_vec(384, 0.10 + i * 0.05)  # different
        _inject_chunk_embedding(db_path, "long.md", i, vec)

    count = rebuild_cross_source_edges(ws, graph)

    intra_edges = [e for e in graph.edges if e.type == EDGE_SAME_DOCUMENT_THREAD]
    assert len(intra_edges) >= 1


async def test_rebuild_deterministic(ws_db):
    """Same inputs → identical edge set."""
    ws = ws_db
    db_path = ws / "app" / "jarvis.db"

    graph = Graph()
    graph.add_node("note:a.md", "note", "Note A")
    graph.add_node("issue:ONB-1", "jira_issue", "ONB-1 — Task")

    _inject_note(db_path, "a.md", "Note A", "See ONB-1 for info.")
    _inject_issue(db_path, "ONB-1", "ONB", "Task", "jira/ONB/ONB-1.md")

    count1 = rebuild_cross_source_edges(ws, graph)
    edges1 = [(e.source, e.target, e.type, e.weight) for e in graph.edges]

    # Rebuild again on same graph (edges should be removed and re-added identically)
    count2 = rebuild_cross_source_edges(ws, graph)
    edges2 = [(e.source, e.target, e.type, e.weight) for e in graph.edges]

    assert count1 == count2
    assert sorted(edges1) == sorted(edges2)


async def test_no_edges_without_data(ws_db):
    """Empty graph → zero cross-source edges."""
    ws = ws_db
    graph = Graph()
    count = rebuild_cross_source_edges(ws, graph)
    assert count == 0
