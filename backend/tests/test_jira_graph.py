"""Tests for services.graph_service.jira_projection (step 22b).

Uses the same small.xml fixture from step 22a to verify that imported
Jira issues are correctly projected into graph nodes and edges.
"""

from pathlib import Path

import aiosqlite
import pytest

from services.jira_ingest import run_import
from services.graph_service.models import Edge, Graph
from services.graph_service.jira_projection import project_jira, ProjectionStats, _slug

pytestmark = pytest.mark.anyio(backends=["asyncio"])

FIXTURES = Path(__file__).parent / "fixtures" / "jira"


@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    (tmp_path / "memory").mkdir()
    (tmp_path / "app").mkdir()
    return tmp_path


async def _import_fixture(ws: Path, fixture: str = "small.xml"):
    """Import fixture and return the stats."""
    return await run_import(FIXTURES / fixture, workspace_path=ws)


def _project(ws: Path, graph: Graph = None) -> tuple:
    """Run projection and return (graph, stats)."""
    g = graph or Graph()
    stats = project_jira(ws, g)
    return g, stats


# ────────────────────────────────────────────────────────────────────
# Core projection tests
# ────────────────────────────────────────────────────────────────────


async def test_projection_creates_issue_nodes(ws: Path):
    await _import_fixture(ws)
    graph, stats = _project(ws)

    assert stats.issues == 5
    assert "issue:ONB-142" in graph.nodes
    assert "issue:ONB-150" in graph.nodes
    assert "issue:ONB-100" in graph.nodes
    assert "issue:AUTH-88" in graph.nodes
    assert "issue:ONB-141" in graph.nodes

    node = graph.nodes["issue:ONB-142"]
    assert node.type == "jira_issue"
    assert "ONB-142" in node.label
    assert "Session expires" in node.label


async def test_projection_is_idempotent(ws: Path):
    await _import_fixture(ws)

    graph1, stats1 = _project(ws)
    edge_count_1 = len(graph1.edges)
    node_count_1 = len(graph1.nodes)

    # Run again on the same graph
    stats2 = project_jira(ws, graph1)
    edge_count_2 = len(graph1.edges)
    node_count_2 = len(graph1.nodes)

    assert edge_count_1 == edge_count_2
    assert node_count_1 == node_count_2
    assert stats2.edges_removed == stats1.edges_added


async def test_blocks_roundtrip(ws: Path):
    """ONB-142 blocks ONB-150 → graph has blocks edge and reverse depends_on."""
    await _import_fixture(ws)
    graph, _ = _project(ws)

    # ONB-142's outbound "blocks" link to ONB-150
    blocks_edges = [
        e for e in graph.edges
        if e.source == "issue:ONB-142" and e.target == "issue:ONB-150" and e.type == "blocks"
    ]
    assert len(blocks_edges) == 1
    assert blocks_edges[0].weight == 1.0
    assert blocks_edges[0].origin == "jira"

    # ONB-150's inbound "is blocked by" from ONB-142 → depends_on edge
    depends_edges = [
        e for e in graph.edges
        if e.source == "issue:ONB-150" and e.target == "issue:ONB-142" and e.type == "depends_on"
    ]
    assert len(depends_edges) == 1


async def test_relates_to_edges(ws: Path):
    """ONB-142 relates to ONB-141."""
    await _import_fixture(ws)
    graph, _ = _project(ws)

    relates = [
        e for e in graph.edges
        if e.type == "relates_to"
        and "ONB-142" in e.source and "ONB-141" in e.target
    ]
    assert len(relates) == 1
    assert relates[0].weight == 0.9


async def test_epic_shadow(ws: Path):
    """Epic issue present as both jira_issue and jira_epic with is_epic_shadow link."""
    await _import_fixture(ws)
    graph, stats = _project(ws)

    assert stats.epics >= 1

    # ONB-100 is an Epic — should have both node types
    assert "issue:ONB-100" in graph.nodes
    assert "epic:ONB-100" in graph.nodes
    assert graph.nodes["issue:ONB-100"].type == "jira_issue"
    assert graph.nodes["epic:ONB-100"].type == "jira_epic"

    # Shadow link
    shadow = [
        e for e in graph.edges
        if e.type == "is_epic_shadow"
        and e.source == "issue:ONB-100" and e.target == "epic:ONB-100"
    ]
    assert len(shadow) == 1
    assert shadow[0].weight == 1.0


async def test_in_epic_edges(ws: Path):
    """Issues with epic_key get in_epic edges to the epic node."""
    await _import_fixture(ws)
    graph, _ = _project(ws)

    # ONB-142 and ONB-150 are in epic ONB-100
    in_epic = [
        e for e in graph.edges
        if e.type == "in_epic" and e.target == "epic:ONB-100"
    ]
    sources = {e.source for e in in_epic}
    assert "issue:ONB-142" in sources
    assert "issue:ONB-150" in sources


async def test_sprint_node_merges_across_issues(ws: Path):
    """Two issues in 'Onboarding Sprint 14' → one sprint node, two in_sprint edges."""
    await _import_fixture(ws)
    graph, _ = _project(ws)

    sprint_slug = _slug("Onboarding Sprint 14")
    sprint_id = "sprint:%s" % sprint_slug
    assert sprint_id in graph.nodes
    assert graph.nodes[sprint_id].type == "jira_sprint"
    assert graph.nodes[sprint_id].label == "Onboarding Sprint 14"

    in_sprint = [e for e in graph.edges if e.type == "in_sprint" and e.target == sprint_id]
    # Only ONB-142 is in this sprint in the fixture
    assert len(in_sprint) >= 1
    assert any(e.source == "issue:ONB-142" for e in in_sprint)


async def test_project_nodes(ws: Path):
    """Distinct project_key values create jira_project nodes."""
    await _import_fixture(ws)
    graph, stats = _project(ws)

    assert stats.projects == 2
    assert "project:ONB" in graph.nodes
    assert "project:AUTH" in graph.nodes
    assert graph.nodes["project:ONB"].type == "jira_project"

    # Every issue links to its project
    in_project = [e for e in graph.edges if e.type == "in_project"]
    assert len(in_project) == 5  # all 5 issues


async def test_source_tagging(ws: Path):
    """Every new edge has origin='jira'; removing and re-projecting yields identical result."""
    await _import_fixture(ws)
    graph, stats = _project(ws)

    jira_edges = [e for e in graph.edges if e.origin == "jira"]
    assert len(jira_edges) == stats.edges_added
    assert all(e.origin == "jira" for e in jira_edges)

    # Remove and re-project
    graph.remove_edges_by_origin("jira")
    assert not any(e.origin == "jira" for e in graph.edges)

    stats2 = project_jira(ws, graph)
    assert stats2.edges_added == stats.edges_added


async def test_person_nodes_created(ws: Path):
    """Assignee/reporter fields create jira_person nodes."""
    await _import_fixture(ws)
    graph, _ = _project(ws)

    person_nodes = [n for n in graph.nodes.values() if n.type == "jira_person"]
    person_labels = {n.label for n in person_nodes}
    assert "michal.kowalski" in person_labels
    assert "anna.nowak" in person_labels
    assert "pm.lead" in person_labels


async def test_assigned_to_and_reported_by(ws: Path):
    """Assignee → assigned_to edge, reporter → reported_by edge."""
    await _import_fixture(ws)
    graph, _ = _project(ws)

    assigned = [e for e in graph.edges if e.type == "assigned_to" and e.source == "issue:ONB-142"]
    assert len(assigned) == 1
    assert assigned[0].weight == 1.0

    reported = [e for e in graph.edges if e.type == "reported_by" and e.source == "issue:ONB-142"]
    assert len(reported) == 1
    assert reported[0].weight == 0.9


async def test_component_nodes(ws: Path):
    """Components create jira_component nodes with has_component edges."""
    await _import_fixture(ws)
    graph, stats = _project(ws)

    assert stats.components >= 2
    comp_nodes = {n.id: n for n in graph.nodes.values() if n.type == "jira_component"}
    assert any("web-auth" in n.label for n in comp_nodes.values())
    assert any("onboarding-flow" in n.label for n in comp_nodes.values())

    has_comp = [e for e in graph.edges if e.type == "has_component" and e.source == "issue:ONB-142"]
    assert len(has_comp) == 2
    assert all(e.weight == 0.9 for e in has_comp)


async def test_label_nodes(ws: Path):
    """Labels create jira_label nodes with has_label edges."""
    await _import_fixture(ws)
    graph, stats = _project(ws)

    assert stats.labels >= 1
    label_nodes = {n.id: n for n in graph.nodes.values() if n.type == "jira_label"}
    assert any("onboarding" in n.label for n in label_nodes.values())
    assert any("auth" in n.label for n in label_nodes.values())

    has_label = [e for e in graph.edges if e.type == "has_label" and e.source == "issue:ONB-142"]
    assert len(has_label) == 4  # onboarding, auth, session, sprint14
    assert all(e.weight == 0.8 for e in has_label)


async def test_comment_authors(ws: Path):
    """Comment authors create commented_by edges."""
    await _import_fixture(ws)
    graph, _ = _project(ws)

    commented = [e for e in graph.edges if e.type == "commented_by" and e.source == "issue:ONB-142"]
    assert len(commented) == 2  # anna.nowak + michal.kowalski
    assert all(e.weight == 0.7 for e in commented)


async def test_auth88_blocks_onb142(ws: Path):
    """AUTH-88 blocks ONB-142 (outbound from AUTH-88)."""
    await _import_fixture(ws)
    graph, _ = _project(ws)

    blocks = [
        e for e in graph.edges
        if e.type == "blocks" and e.source == "issue:AUTH-88" and e.target == "issue:ONB-142"
    ]
    assert len(blocks) == 1


# ────────────────────────────────────────────────────────────────────
# Edge model tests
# ────────────────────────────────────────────────────────────────────


def test_remove_edges_by_origin():
    g = Graph()
    g.add_node("a", "note", "A")
    g.add_node("b", "note", "B")
    g.add_edge("a", "b", "linked", 1.0, origin="generic")
    g.add_edge("a", "b", "blocks", 1.0, origin="jira")

    assert len(g.edges) == 2
    removed = g.remove_edges_by_origin("jira")
    assert removed == 1
    assert len(g.edges) == 1
    assert g.edges[0].origin == "generic"


def test_edge_origin_preserved_in_serialization():
    g = Graph()
    g.add_node("a", "note", "A")
    g.add_node("b", "note", "B")
    g.add_edge("a", "b", "blocks", 1.0, origin="jira")
    g.add_edge("a", "b", "linked", 1.0)

    data = g.to_dict()
    jira_edge = [e for e in data["edges"] if e["type"] == "blocks"][0]
    generic_edge = [e for e in data["edges"] if e["type"] == "linked"][0]

    assert jira_edge["origin"] == "jira"
    assert "origin" not in generic_edge  # generic is omitted for compactness


def test_slug():
    assert _slug("Onboarding Sprint 14") == "onboarding-sprint-14"
    assert _slug("web-auth") == "web-auth"
    assert _slug("  Hello World  ") == "hello-world"


# ────────────────────────────────────────────────────────────────────
# CSV fixture projection
# ────────────────────────────────────────────────────────────────────


async def test_csv_projection(ws: Path):
    """CSV import also projects into graph correctly."""
    await _import_fixture(ws, "export.csv")
    graph, stats = _project(ws)

    assert stats.issues == 4
    assert "issue:ONB-142" in graph.nodes

    # CSV has blocks links too
    blocks = [e for e in graph.edges if e.type == "blocks"]
    assert len(blocks) >= 1


# ────────────────────────────────────────────────────────────────────
# Integration: import + auto-projection
# ────────────────────────────────────────────────────────────────────


async def test_import_triggers_projection(ws: Path):
    """run_import auto-projects into graph when issues are inserted."""
    from services.graph_service.builder import load_graph, invalidate_cache

    invalidate_cache()
    await _import_fixture(ws)

    graph = load_graph(ws)
    assert graph is not None
    assert "issue:ONB-142" in graph.nodes

    jira_edges = [e for e in graph.edges if e.origin == "jira"]
    assert len(jira_edges) > 0
    invalidate_cache()
