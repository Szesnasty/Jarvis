"""Graph construction: full rebuild, entity enrichment, and persistence.

Handles the multi-pass graph rebuild pipeline and cache management.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from config import get_settings
from utils.markdown import parse_frontmatter

from services.graph_service.models import Edge, Graph, Node, apply_edge_weights, extract_wiki_links
from services.graph_service.similarity import compute_similarity_edges, compute_temporal_edges, prune_overloaded_tags

logger = logging.getLogger(__name__)

# In-memory graph cache
_graph_cache: Optional[Graph] = None


def _memory_path(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "memory"


def _graph_path(workspace_path: Optional[Path] = None) -> Path:
    return (workspace_path or get_settings().workspace_path) / "graph" / "graph.json"


def _save_and_cache(graph: Graph, workspace_path: Optional[Path] = None) -> None:
    global _graph_cache
    _graph_cache = graph
    gp = _graph_path(workspace_path)
    gp.parent.mkdir(parents=True, exist_ok=True)
    gp.write_text(json.dumps(graph.to_dict(), indent=2), encoding="utf-8")


def load_graph(workspace_path: Optional[Path] = None) -> Optional[Graph]:
    global _graph_cache
    if _graph_cache is not None:
        return _graph_cache

    gp = _graph_path(workspace_path)
    if not gp.exists():
        return None

    data = json.loads(gp.read_text(encoding="utf-8"))
    graph = Graph()
    for n in data.get("nodes", []):
        graph.add_node(n["id"], n["type"], n["label"], n.get("folder", ""))
    for e in data.get("edges", []):
        # Parse evidence tuples from JSON if present
        evidence_raw = e.get("evidence", [])
        evidence = tuple(
            (ev["source_chunk"], ev["target_chunk"], ev["similarity"])
            for ev in evidence_raw
        ) if evidence_raw else ()
        edge = Edge(
            source=e["source"], target=e["target"],
            type=e["type"], weight=e.get("weight", 1.0),
            evidence=evidence,
            origin=e.get("origin", "generic"),
        )
        if edge not in graph.edges:
            graph.edges.append(edge)

    _graph_cache = graph
    return graph


def invalidate_cache() -> None:
    global _graph_cache
    _graph_cache = None


def _enrich_with_entities(graph: Graph, mem: Path) -> None:
    """Extract entities from note bodies and add person nodes/edges.

    Uses entity canonicalization (step 20d) to deduplicate person names.
    Pre-seeds existing_people from people/*.md note titles for better
    canonical form matching on the first pass.
    For conversation notes, cleans markdown artifacts and uses a lower
    confidence threshold (0.3) since single-word names get ~0.35 from spaCy.
    """
    from services.entity_extraction import extract_entities, clean_conversation_text

    # Pre-seed known people from people/ folder titles + existing graph nodes
    existing_people = [n.label for n in graph.nodes.values() if n.type == "person"]
    people_dir = mem / "people"
    if people_dir.is_dir():
        for md_file in people_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                fm, _ = parse_frontmatter(content)
                title = fm.get("title", "")
                if title and title not in existing_people:
                    existing_people.append(title)
            except Exception:
                pass

    # Try to use canonicalization; fall back to raw IDs if unavailable
    canon_available = False
    db_path = mem.parent / "app" / "jarvis.db"
    try:
        from services.entity_canonicalization import resolve_entity_sync
        if db_path.exists():
            canon_available = True
    except ImportError:
        pass

    for node in list(graph.nodes.values()):
        if node.type != "note":
            continue
        filepath = mem / node.id[5:]
        if not filepath.exists():
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            fm, body = parse_frontmatter(content)
        except Exception:
            continue

        # Detect conversation notes: lower threshold + clean body
        rel_path = node.id[5:]  # strip "note:" prefix
        is_conversation = (
            fm.get("type") == "conversation"
            or rel_path.startswith("conversations/")
        )
        if is_conversation:
            body = clean_conversation_text(body)
        min_confidence = 0.3 if is_conversation else 0.5

        fm_people = {str(p).lower() for p in fm.get("people", [])}
        entities = extract_entities(body, existing_people)

        for ent in entities:
            if ent.type == "person" and ent.confidence >= min_confidence:
                if ent.text.lower() not in fm_people:
                    if canon_available:
                        try:
                            person_id = resolve_entity_sync(
                                ent.text, "person", db_path, existing_people,
                            )
                            label = person_id.split(":", 1)[1] if ":" in person_id else ent.text
                        except Exception:
                            person_id = f"person:{ent.text}"
                            label = ent.text
                    else:
                        person_id = f"person:{ent.text}"
                        label = ent.text
                    graph.add_node(person_id, "person", label)
                    graph.add_edge(node.id, person_id, "mentions")
                    # Grow existing_people so later notes can match
                    if label not in existing_people:
                        existing_people.append(label)


def _resolve_bidirectional_links(graph: Graph) -> None:
    """For each linked edge A->B, add B->A if not already present."""
    forward_links = [(e.source, e.target) for e in graph.edges if e.type == "linked"]
    forward_set = set(forward_links)

    for src, tgt in forward_links:
        if (tgt, src) not in forward_set and tgt in graph.nodes:
            graph.add_edge(tgt, src, "linked", weight=0.6)
            forward_set.add((tgt, src))


def rebuild_graph(workspace_path: Optional[Path] = None) -> Graph:
    global _graph_cache
    mem = _memory_path(workspace_path)
    graph = Graph()

    if not mem.exists():
        _save_and_cache(graph, workspace_path)
        return graph

    # Clear entity alias cache (rebuilt during entity extraction pass)
    db_path = mem.parent / "app" / "jarvis.db"
    if db_path.exists():
        import sqlite3
        try:
            conn = sqlite3.connect(str(db_path))
            conn.execute("DELETE FROM entity_aliases")
            conn.commit()
            conn.close()
        except sqlite3.OperationalError:
            pass  # Table may not exist yet

    # Pass 1: Parse notes, extract frontmatter edges
    for md_file in sorted(mem.rglob("*.md")):
        rel = md_file.relative_to(mem).as_posix()
        content = md_file.read_text(encoding="utf-8")
        fm, body = parse_frontmatter(content)

        # Skip Jira issue Markdown files — they get proper jira_issue nodes
        # from the Jira projection pass (step 22b).
        if fm.get("type") == "jira_issue":
            continue

        note_id = f"note:{rel}"
        folder = str(md_file.relative_to(mem).parent) if "/" in rel else ""
        graph.add_node(note_id, "note", fm.get("title", md_file.stem), folder=folder)

        # Tags
        for tag in fm.get("tags", []):
            tag_id = f"tag:{tag}"
            graph.add_node(tag_id, "tag", str(tag))
            graph.add_edge(note_id, tag_id, "tagged")

        # Wiki links
        for link in extract_wiki_links(body):
            target_id = f"note:{link}"
            graph.add_edge(note_id, target_id, "linked")

        # People
        for person in fm.get("people", []):
            person_id = f"person:{person}"
            graph.add_node(person_id, "person", str(person))
            graph.add_edge(note_id, person_id, "mentions")

        # Related
        for related in fm.get("related", []):
            rel_path = related if related.endswith(".md") else related + ".md"
            graph.add_edge(note_id, f"note:{rel_path}", "related")

        # Folder membership
        if folder:
            area_id = f"area:{folder}"
            graph.add_node(area_id, "area", folder)
            graph.add_edge(note_id, area_id, "part_of")

    # Pass 2: Entity extraction (adds person nodes from body text)
    _enrich_with_entities(graph, mem)

    # Pass 3: Bidirectional wiki-link resolution
    _resolve_bidirectional_links(graph)

    # Pass 4: Keyword similarity edges (kill switch)
    settings = get_settings()
    if settings.similarity_edges_enabled:
        for edge in compute_similarity_edges(graph, mem):
            graph.edges.append(edge)

    # Pass 5: Temporal edges (kill switch)
    if settings.temporal_edges_enabled:
        for edge in compute_temporal_edges(graph, mem):
            graph.edges.append(edge)

    # Pass 6: Apply IDF-weighted edge weights
    apply_edge_weights(graph)

    # Pass 7: Prune overloaded tags
    prune_overloaded_tags(graph)

    # Pass 8: Jira graph projection (step 22b)
    ws = workspace_path or get_settings().workspace_path
    try:
        from services.graph_service.jira_projection import project_jira
        jira_stats = project_jira(ws, graph)
        if jira_stats.issues > 0:
            logger.info(
                "Jira projection: %d issues, %d edges added",
                jira_stats.issues, jira_stats.edges_added,
            )
    except Exception as exc:
        logger.debug("Jira projection skipped: %s", exc)

    # Pass 9: Embed node labels for semantic anchoring (step 20b)
    if os.environ.get("JARVIS_DISABLE_EMBEDDINGS") != "1":
        try:
            from services.embedding_service import embed_graph_nodes, is_available
            if is_available():
                import asyncio
                nodes_data = [
                    {"id": n.id, "type": n.type, "label": n.label}
                    for n in graph.nodes.values()
                ]
                db_path = (workspace_path or get_settings().workspace_path) / "app" / "jarvis.db"
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(embed_graph_nodes(nodes_data, db_path))
                else:
                    asyncio.run(embed_graph_nodes(nodes_data, db_path))
        except (ImportError, Exception) as exc:
            logger.debug("Node embedding skipped: %s", exc)

    _save_and_cache(graph, workspace_path)
    return graph
