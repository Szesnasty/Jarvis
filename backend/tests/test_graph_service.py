import json

import pytest

pytestmark = pytest.mark.anyio(backends=["asyncio"])

from models.database import init_database
from services.graph_service import (
    Graph,
    add_conversation_to_graph,
    extract_wiki_links,
    get_neighbors,
    invalidate_cache,
    load_graph,
    query_entity,
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


NOTE_A = "---\ntitle: Note A\ntags: [python, ai]\npeople: [Alice]\n---\n\nSome content about python and AI.\n\nSee also [[note-b]]."
NOTE_B = "---\ntitle: Note B\ntags: [python]\nrelated: [inbox/note-a.md]\n---\n\nAnother note about python."
NOTE_C = "---\ntitle: Note C\ntags: [health]\n---\n\nHealth related content."


def test_extract_wiki_links():
    assert extract_wiki_links("See [[note-b]] and [[folder/note-c]]") == ["note-b.md", "folder/note-c.md"]


def test_extract_wiki_links_with_alias():
    assert extract_wiki_links("See [[note-b|my alias]]") == ["note-b.md"]


def test_extract_wiki_links_empty():
    assert extract_wiki_links("No links here") == []


def test_build_graph_empty(ws):
    graph = rebuild_graph(ws)
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0


@pytest.mark.anyio
async def test_build_graph_single_note(ws_db):
    await create_note("inbox/note-a.md", NOTE_A, ws_db)
    graph = rebuild_graph(ws_db)
    assert "note:inbox/note-a.md" in graph.nodes


@pytest.mark.anyio
async def test_build_graph_multiple_notes(ws_db):
    await create_note("inbox/note-a.md", NOTE_A, ws_db)
    await create_note("inbox/note-b.md", NOTE_B, ws_db)
    graph = rebuild_graph(ws_db)
    note_nodes = [n for n in graph.nodes.values() if n.type == "note"]
    assert len(note_nodes) == 2


@pytest.mark.anyio
async def test_graph_folder_membership_edge(ws_db):
    await create_note("projects/jarvis.md", "---\ntitle: Jarvis\ntags: []\n---\n\nContent", ws_db)
    graph = rebuild_graph(ws_db)
    part_of_edges = [e for e in graph.edges if e.type == "part_of"]
    assert len(part_of_edges) >= 1
    assert part_of_edges[0].source == "note:projects/jarvis.md"


@pytest.mark.anyio
async def test_graph_shared_tag_edge(ws_db):
    await create_note("inbox/note-a.md", NOTE_A, ws_db)
    await create_note("inbox/note-b.md", NOTE_B, ws_db)
    graph = rebuild_graph(ws_db)
    # Both share "python" tag - both connected to tag:python
    tagged = [e for e in graph.edges if e.type == "tagged" and e.target == "tag:python"]
    assert len(tagged) == 2


@pytest.mark.anyio
async def test_graph_no_edge_different_tags(ws_db):
    await create_note("inbox/note-a.md", NOTE_A, ws_db)
    await create_note("inbox/note-c.md", NOTE_C, ws_db)
    graph = rebuild_graph(ws_db)
    # "health" tag only on C, "ai" only on A
    health_tagged = [e for e in graph.edges if e.target == "tag:health"]
    assert len(health_tagged) == 1


@pytest.mark.anyio
async def test_graph_wikilink_edge(ws_db):
    await create_note("inbox/note-a.md", NOTE_A, ws_db)
    graph = rebuild_graph(ws_db)
    linked = [e for e in graph.edges if e.type == "linked"]
    assert any(e.target == "note:note-b.md" for e in linked)


@pytest.mark.anyio
async def test_graph_frontmatter_related(ws_db):
    await create_note("inbox/note-b.md", NOTE_B, ws_db)
    graph = rebuild_graph(ws_db)
    related = [e for e in graph.edges if e.type == "related"]
    assert len(related) >= 1


@pytest.mark.anyio
async def test_graph_node_has_metadata(ws_db):
    await create_note("inbox/note-a.md", NOTE_A, ws_db)
    graph = rebuild_graph(ws_db)
    node = graph.nodes["note:inbox/note-a.md"]
    assert node.id == "note:inbox/note-a.md"
    assert node.label == "Note A"
    assert node.folder == "inbox"


@pytest.mark.anyio
async def test_graph_edge_has_type(ws_db):
    await create_note("inbox/note-a.md", NOTE_A, ws_db)
    graph = rebuild_graph(ws_db)
    types = {e.type for e in graph.edges}
    assert "tagged" in types


@pytest.mark.anyio
async def test_query_neighbors(ws_db):
    await create_note("inbox/note-a.md", NOTE_A, ws_db)
    await create_note("inbox/note-b.md", NOTE_B, ws_db)
    rebuild_graph(ws_db)
    neighbors = get_neighbors("note:inbox/note-a.md", depth=1, workspace_path=ws_db)
    assert len(neighbors) >= 1


@pytest.mark.anyio
async def test_query_neighbors_depth_2(ws_db):
    await create_note("inbox/note-a.md", NOTE_A, ws_db)
    await create_note("inbox/note-b.md", NOTE_B, ws_db)
    await create_note("inbox/note-c.md", NOTE_C, ws_db)
    rebuild_graph(ws_db)
    neighbors_1 = get_neighbors("note:inbox/note-a.md", depth=1, workspace_path=ws_db)
    neighbors_2 = get_neighbors("note:inbox/note-a.md", depth=2, workspace_path=ws_db)
    assert len(neighbors_2) >= len(neighbors_1)


@pytest.mark.anyio
async def test_query_neighbors_empty(ws_db):
    await create_note("inbox/solo.md", "---\ntitle: Solo\ntags: []\n---\n\nAlone.", ws_db)
    rebuild_graph(ws_db)
    neighbors = get_neighbors("note:inbox/solo.md", depth=1, workspace_path=ws_db)
    # Only 'part_of' folder edge
    note_neighbors = [n for n in neighbors if n["type"] == "note"]
    assert note_neighbors == []


@pytest.mark.anyio
async def test_graph_rebuild_idempotent(ws_db):
    await create_note("inbox/note-a.md", NOTE_A, ws_db)
    g1 = rebuild_graph(ws_db)
    invalidate_cache()
    g2 = rebuild_graph(ws_db)
    assert g1.to_dict() == g2.to_dict()


@pytest.mark.anyio
async def test_graph_rebuild_after_delete(ws_db):
    await create_note("inbox/note-a.md", NOTE_A, ws_db)
    g1 = rebuild_graph(ws_db)
    # Delete the graph file
    gp = ws_db / "graph" / "graph.json"
    if gp.exists():
        gp.unlink()
    invalidate_cache()
    g2 = rebuild_graph(ws_db)
    assert g1.to_dict() == g2.to_dict()


def test_no_anthropic_calls(ws):
    """Graph building should never call Anthropic API."""
    import anthropic
    from unittest.mock import patch

    with patch.object(anthropic, "Anthropic", side_effect=AssertionError("Should not be called")):
        with patch.object(anthropic, "AsyncAnthropic", side_effect=AssertionError("Should not be called")):
            rebuild_graph(ws)


def test_add_conversation_to_graph(ws):
    """Incrementally adding a conversation creates node + edges."""
    # Start with an empty graph
    rebuild_graph(ws)

    add_conversation_to_graph(
        note_path="conversations/2026-04-14-stoicism.md",
        title="Stoicism discussion",
        tags=["conversation", "philosophy"],
        topics=["stoicism", "life"],
        notes_accessed=["knowledge/stoicism.md"],
        workspace_path=ws,
    )

    g = load_graph(ws)
    assert g is not None

    # Conversation node exists
    assert "note:conversations/2026-04-14-stoicism.md" in g.nodes

    # Tag edges exist
    assert "tag:conversation" in g.nodes
    assert "tag:philosophy" in g.nodes
    assert "tag:stoicism" in g.nodes

    # Related note edge exists
    related_edges = [e for e in g.edges if e.target == "note:knowledge/stoicism.md"]
    assert len(related_edges) >= 1

    # Folder area
    assert "area:conversations" in g.nodes
