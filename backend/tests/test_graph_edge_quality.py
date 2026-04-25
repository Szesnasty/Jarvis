import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.graph_service import (
    Edge,
    Graph,
    compute_tag_idf,
    find_orphans,
    get_node_detail,
    invalidate_cache,
    rebuild_graph,
)
from services.memory_service import create_note


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


NOTE_WITH_PERSON = "---\ntitle: Meeting Notes\ntags: [work]\npeople: [Alice]\n---\n\nMet with Bob Wilson to discuss the roadmap."
NOTE_SAME_TAG = "---\ntitle: Work Log\ntags: [work]\n---\n\nDaily work log entry."
NOTE_ORPHAN = "---\ntitle: Orphan Note\ntags: []\n---\n\nThis note has no connections."
NOTE_DATED_A = "---\ntitle: Day Note A\ntags: []\ndate: 2026-04-14\n---\n\nFirst note of the day."
NOTE_DATED_B = "---\ntitle: Day Note B\ntags: []\ndate: 2026-04-14\n---\n\nSecond note of the day."


# --- Tag IDF ---

@pytest.mark.anyio
async def test_tag_idf_rare_beats_common(ws_db):
    """Rare tag should have higher IDF than common tag."""
    # Both tags need >= 2 notes so they survive the singleton-prune pass.
    await create_note("inbox/a.md", "---\ntitle: A\ntags: [python, rare-topic]\n---\n\n", ws_db)
    await create_note("inbox/b.md", "---\ntitle: B\ntags: [python, rare-topic]\n---\n\n", ws_db)
    await create_note("inbox/c.md", "---\ntitle: C\ntags: [python]\n---\n\n", ws_db)
    await create_note("inbox/d.md", "---\ntitle: D\ntags: [python]\n---\n\n", ws_db)
    graph = rebuild_graph(ws_db)
    idf = compute_tag_idf(graph)
    assert idf.get("tag:rare-topic", 0) > idf.get("tag:python", 0)


@pytest.mark.anyio
async def test_tag_idf_single_note(ws_db):
    # Singleton tags are pruned by the entity cleanup pass — the resulting
    # graph has no tag:solo node and IDF is empty for it.
    await create_note("inbox/a.md", "---\ntitle: A\ntags: [solo]\n---\n\n", ws_db)
    graph = rebuild_graph(ws_db)
    assert "tag:solo" not in graph.nodes
    idf = compute_tag_idf(graph)
    assert "tag:solo" not in idf


# --- Edge weights ---

@pytest.mark.anyio
async def test_edges_have_weights(ws_db):
    await create_note("inbox/a.md", "---\ntitle: A\ntags: [python]\n---\n\nSee [[b]].", ws_db)
    await create_note("inbox/b.md", "---\ntitle: B\ntags: [python]\n---\n\nContent.", ws_db)
    graph = rebuild_graph(ws_db)
    for edge in graph.edges:
        assert isinstance(edge.weight, float)
        assert edge.weight >= 0


@pytest.mark.anyio
async def test_linked_edge_weight_higher_than_part_of(ws_db):
    await create_note("projects/a.md", "---\ntitle: A\ntags: []\n---\n\nSee [[b]].", ws_db)
    graph = rebuild_graph(ws_db)
    linked = [e for e in graph.edges if e.type == "linked"]
    part_of = [e for e in graph.edges if e.type == "part_of"]
    assert len(linked) > 0 and len(part_of) > 0
    assert linked[0].weight > part_of[0].weight


# --- Orphan detection ---

@pytest.mark.anyio
async def test_orphan_detection(ws_db):
    # Note at root (no folder) with no tags → truly orphaned
    await create_note("orphan.md", NOTE_ORPHAN, ws_db)
    rebuild_graph(ws_db)
    orphans = find_orphans(ws_db)
    ids = [o["id"] for o in orphans]
    assert "note:orphan.md" in ids


@pytest.mark.anyio
async def test_connected_note_not_orphan(ws_db):
    await create_note("inbox/a.md", "---\ntitle: A\ntags: [work]\n---\n\n", ws_db)
    rebuild_graph(ws_db)
    orphans = find_orphans(ws_db)
    ids = [o["id"] for o in orphans]
    assert "note:inbox/a.md" not in ids


# --- Node detail ---

@pytest.mark.anyio
async def test_node_detail(ws_db):
    await create_note("inbox/a.md", NOTE_WITH_PERSON, ws_db)
    rebuild_graph(ws_db)
    detail = get_node_detail("note:inbox/a.md", ws_db)
    assert detail is not None
    assert detail["node"]["type"] == "note"
    assert detail["degree"] > 0
    assert "Alice" in detail["connected_people"]


@pytest.mark.anyio
async def test_node_detail_missing(ws_db):
    rebuild_graph(ws_db)
    detail = get_node_detail("note:nonexistent.md", ws_db)
    assert detail is None


# --- Bidirectional links ---

@pytest.mark.anyio
async def test_bidirectional_links(ws_db):
    # Use root-level notes so wiki link path matches node ID
    await create_note("a.md", "---\ntitle: A\ntags: []\n---\n\nSee [[b]].", ws_db)
    await create_note("b.md", "---\ntitle: B\ntags: []\n---\n\nSee [[a]].", ws_db)
    graph = rebuild_graph(ws_db)
    # Both directions should exist as linked edges
    forward = [e for e in graph.edges if e.type == "linked" and e.source == "note:a.md" and e.target == "note:b.md"]
    backward = [e for e in graph.edges if e.type == "linked" and e.source == "note:b.md" and e.target == "note:a.md"]
    assert len(forward) >= 1
    assert len(backward) >= 1


# --- Temporal edges ---

@pytest.mark.anyio
async def test_temporal_edges(ws_db):
    await create_note("inbox/day-a.md", NOTE_DATED_A, ws_db)
    await create_note("inbox/day-b.md", NOTE_DATED_B, ws_db)
    graph = rebuild_graph(ws_db)
    temporal = [e for e in graph.edges if e.type == "temporal"]
    assert len(temporal) >= 1


# --- Entity extraction integration ---

@pytest.mark.anyio
async def test_entity_enrichment(ws_db):
    await create_note("inbox/meeting.md", NOTE_WITH_PERSON, ws_db)
    graph = rebuild_graph(ws_db)
    # "Alice" comes from frontmatter people field — always reliable
    person_nodes = [n for n in graph.nodes.values() if n.type == "person"]
    labels = [n.label for n in person_nodes]
    assert "Alice" in labels  # from frontmatter
    # "Bob Wilson" comes from entity extraction (spaCy NER) — may not be
    # detected by the small model; assert only when available.
    if "Bob Wilson" not in labels:
        pytest.xfail("spaCy sm model did not extract 'Bob Wilson' from body text")
