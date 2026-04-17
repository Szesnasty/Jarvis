"""Tests for derived (soft) graph edges — step 22d."""
import json
import sqlite3
from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.embedding_service import vector_to_blob
from services.graph_service.models import Edge, Graph
from services.graph_service.soft_edges import (
    CONFIDENCE_FLOORS,
    EDGE_LIKELY_DEP,
    EDGE_SAME_AREA,
    EDGE_SAME_PROBLEM,
    EDGE_SAME_RISK,
    EDGE_SAME_TOPIC,
    MAX_OUT_DEGREE,
    confidence_likely_dependency,
    confidence_same_business_area,
    confidence_same_problem,
    confidence_same_topic,
    keyword_jaccard,
    node_cosine,
    rebuild_soft_edges,
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


def _make_vec(dims: int, base: float) -> list:
    """Create a deterministic vector with a given base value."""
    import math
    vec = [(base + i * 0.01) % 1.0 for i in range(dims)]
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec]  # unit vector


def _inject_node_embedding(db_path, node_id, node_type, label, vec):
    now = datetime.now(timezone.utc).isoformat()
    blob = vector_to_blob(vec)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT OR REPLACE INTO node_embeddings
        (node_id, node_type, label, embedding, content_hash, model_name, dimensions, embedded_at)
        VALUES (?, ?, ?, ?, 'testhash', 'test-model', ?, ?)
        """,
        (node_id, node_type, label, blob, len(vec), now),
    )
    conn.commit()
    conn.close()


def _inject_enrichment(db_path, subject_type, subject_id, payload):
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        INSERT OR REPLACE INTO enrichments
        (subject_type, subject_id, content_hash, model_id, prompt_version,
         status, payload, raw_output, tokens_in, tokens_out, duration_ms, created_at)
        VALUES (?, ?, 'hash', 'test', 1, 'ok', ?, NULL, 100, 100, 100, ?)
        """,
        (subject_type, subject_id, json.dumps(payload), now),
    )
    conn.commit()
    conn.close()


# ── Pure function tests ──────────────────────────────────────


def test_confidence_monotonic():
    """Raising any input signal only raises confidence (same_topic_as)."""
    base = confidence_same_topic(0.5, [0.5, 0.5], 0.3)
    higher_node = confidence_same_topic(0.8, [0.5, 0.5], 0.3)
    higher_chunk = confidence_same_topic(0.5, [0.9, 0.9], 0.3)
    higher_kw = confidence_same_topic(0.5, [0.5, 0.5], 0.8)

    assert higher_node > base
    assert higher_chunk > base
    assert higher_kw > base


def test_hard_edge_suppresses_soft():
    """If blocks(a,b) exists, rebuild emits no likely_dependency_on(a,b)."""
    conf = confidence_likely_dependency(
        has_forward_ref=True, topic_signal=0.9, has_hard_blocks=True
    )
    assert conf == 0.0


def test_same_area_zero_when_no_match():
    """Business area confidence is 0 when areas don't match."""
    conf = confidence_same_business_area(areas_match=False, topic_signal=0.9)
    assert conf == 0.0


def test_same_problem_requires_chunks():
    """implementation_of_same_problem requires ≥3 high chunk pairs."""
    # Only 2 chunks: should be 0
    conf = confidence_same_problem(high_chunk_count=2, same_area=True, best_chunk_sim=0.9)
    assert conf == 0.0
    # 3 chunks with same area: should be > 0
    conf3 = confidence_same_problem(high_chunk_count=3, same_area=True, best_chunk_sim=0.9)
    assert conf3 >= CONFIDENCE_FLOORS[EDGE_SAME_PROBLEM]


def test_keyword_jaccard_disjoint():
    assert keyword_jaccard(["auth", "billing"], ["growth", "infra"]) == 0.0


def test_keyword_jaccard_identical():
    assert keyword_jaccard(["auth", "billing"], ["auth", "billing"]) == 1.0


# ── Integration tests ────────────────────────────────────────


async def test_topk_respected(ws_db):
    """Node with many similar neighbours keeps exactly max_out_degree edges."""
    ws = ws_db
    db_path = ws / "app" / "jarvis.db"
    graph = Graph()

    # Create one central issue and MAX+5 neighbours with near-identical embeddings
    # Also inject enrichments with matching keywords to push confidence above floor.
    # Pure node cosine alone gives 0.55 (below 0.60 floor); keywords add +0.10.
    central = "issue:ONB-1"
    graph.add_node(central, "jira_issue", "ONB-1 — Central")
    central_vec = _make_vec(384, 0.5)
    _inject_node_embedding(db_path, central, "jira_issue", "Central", central_vec)
    _inject_enrichment(db_path, "jira_issue", "ONB-1", {
        "summary": "Central", "actionable_next_step": "Go",
        "work_type": "feature", "business_area": "billing",
        "execution_type": "implementation", "risk_level": "medium",
        "ambiguity_level": "clear", "hidden_concerns": [],
        "likely_related_issue_keys": [], "likely_related_note_paths": [],
        "keywords": ["billing", "payment", "central"],
    })

    n_neighbors = MAX_OUT_DEGREE[EDGE_SAME_TOPIC] + 5
    for k in range(n_neighbors):
        nid = f"issue:ONB-{k+100}"
        graph.add_node(nid, "jira_issue", f"ONB-{k+100}")
        vec = _make_vec(384, 0.5 + k * 0.0001)
        _inject_node_embedding(db_path, nid, "jira_issue", f"Nb {k}", vec)
        _inject_enrichment(db_path, "jira_issue", f"ONB-{k+100}", {
            "summary": f"Neighbor {k}", "actionable_next_step": "Go",
            "work_type": "feature", "business_area": "billing",
            "execution_type": "implementation", "risk_level": "medium",
            "ambiguity_level": "clear", "hidden_concerns": [],
            "likely_related_issue_keys": [], "likely_related_note_paths": [],
            "keywords": ["billing", "payment", "central"],
        })

    count = rebuild_soft_edges(ws, graph)
    assert count > 0

    # Check max out-degree for central node
    central_topic_edges = [
        e for e in graph.edges
        if e.source == central and e.type == EDGE_SAME_TOPIC and e.origin == "derived"
    ]
    assert len(central_topic_edges) <= MAX_OUT_DEGREE[EDGE_SAME_TOPIC]


async def test_rebuild_deterministic(ws_db):
    """Same inputs → identical edge set (sort-stable)."""
    ws = ws_db
    db_path = ws / "app" / "jarvis.db"

    graph = Graph()
    for i in range(5):
        nid = f"issue:TEST-{i}"
        graph.add_node(nid, "jira_issue", f"Test {i}")
        _inject_node_embedding(db_path, nid, "jira_issue", f"Test {i}", _make_vec(384, 0.3 + i * 0.05))
        _inject_enrichment(db_path, "jira_issue", f"TEST-{i}", {
            "summary": f"Test issue {i}",
            "actionable_next_step": "Do stuff",
            "work_type": "feature",
            "business_area": "billing",
            "execution_type": "implementation",
            "risk_level": "medium",
            "ambiguity_level": "clear",
            "hidden_concerns": [],
            "likely_related_issue_keys": [],
            "likely_related_note_paths": [],
            "keywords": ["test", "billing", "feature"],
        })

    # Run twice
    rebuild_soft_edges(ws, graph)
    edges_1 = sorted(
        [(e.source, e.target, e.type, e.weight) for e in graph.edges if e.origin == "derived"]
    )

    # Second run: rebuild removes and recreates
    rebuild_soft_edges(ws, graph)
    edges_2 = sorted(
        [(e.source, e.target, e.type, e.weight) for e in graph.edges if e.origin == "derived"]
    )

    assert edges_1 == edges_2


async def test_source_separation(ws_db):
    """remove_edges_where_source('derived') does not touch origin='jira' edges."""
    ws = ws_db
    db_path = ws / "app" / "jarvis.db"

    graph = Graph()
    # Add a jira edge
    graph.add_edge("issue:A", "issue:B", "blocks", weight=1.0, origin="jira")

    # Add two nodes with embeddings so soft edges can be generated
    for nid, label in [("issue:A", "Issue A"), ("issue:B", "Issue B")]:
        graph.add_node(nid, "jira_issue", label)
        _inject_node_embedding(db_path, nid, "jira_issue", label, _make_vec(384, 0.5))

    rebuild_soft_edges(ws, graph)

    # Jira edge still present
    jira_edges = [e for e in graph.edges if e.origin == "jira"]
    assert len(jira_edges) == 1
    assert jira_edges[0].type == "blocks"


async def test_no_self_loops(ws_db):
    """No derived edge should have source == target."""
    ws = ws_db
    db_path = ws / "app" / "jarvis.db"

    graph = Graph()
    nid = "issue:SOLO-1"
    graph.add_node(nid, "jira_issue", "Solo issue")
    _inject_node_embedding(db_path, nid, "jira_issue", "Solo", _make_vec(384, 0.5))

    rebuild_soft_edges(ws, graph)

    for e in graph.edges:
        if e.origin == "derived":
            assert e.source != e.target, f"Self-loop found: {e}"
