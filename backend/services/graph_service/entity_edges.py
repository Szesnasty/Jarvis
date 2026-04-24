"""Shared helpers for translating extracted entities into graph nodes/edges.

Used by both the full ``rebuild_graph`` pass (``builder._enrich_with_entities``)
and the incremental ``ingest_note`` path so the two stay in sync.

Step 25 PR 2 — adds organization, project and place entity types alongside
the pre-existing person extraction. Dates are intentionally excluded from
the graph: they create dense, low-signal stars and are better expressed as
temporal edges (``rebuild_graph`` handles that separately).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from services.graph_service.models import Graph

# entity type from extractor → (graph node type, edge type, min confidence)
ENTITY_EDGE_MAP: Dict[str, Tuple[str, str, float]] = {
    "person": ("person", "mentions", 0.5),
    "organization": ("org", "mentions_org", 0.5),
    "project": ("project", "mentions_project", 0.5),
    "place": ("place", "mentions_place", 0.5),
}


def apply_extracted_entities(
    graph: Graph,
    note_id: str,
    body: str,
    fm: Dict,
    existing_labels_by_type: Dict[str, List[str]],
    *,
    db_path: Optional[Path] = None,
    is_conversation: bool = False,
) -> int:
    """Run entity extraction on ``body`` and add nodes/edges to ``graph``.

    Mutates ``graph`` and ``existing_labels_by_type`` in place. Returns the
    number of entity edges added (for tests + telemetry).

    Person extraction uses :func:`entity_canonicalization.resolve_entity_sync`
    when ``db_path`` exists, so the same person mentioned with slightly
    different spellings collapses into one canonical node. Other entity
    types currently use raw labels (canonicalisation for orgs/projects is a
    follow-up — the helper centralises the wiring so it's a one-line change
    when the time comes).
    """
    from services.entity_extraction import clean_conversation_text, extract_entities

    extraction_text = clean_conversation_text(body) if is_conversation else body
    person_min_confidence = 0.3 if is_conversation else 0.5

    fm_people = {str(p).lower() for p in fm.get("people", [])}
    fm_orgs = {str(o).lower() for o in fm.get("organizations", [])}

    canon_available = False
    if db_path is not None and db_path.exists():
        try:
            from services.entity_canonicalization import resolve_entity_sync  # noqa: F401
            canon_available = True
        except ImportError:
            canon_available = False

    edges_added = 0
    seen_pairs: set = set()
    existing_people = existing_labels_by_type.setdefault("person", [])

    for ent in extract_entities(extraction_text, existing_people):
        mapping = ENTITY_EDGE_MAP.get(ent.type)
        if mapping is None:
            continue
        node_type, edge_type, default_min = mapping

        threshold = person_min_confidence if ent.type == "person" else default_min
        if ent.confidence < threshold:
            continue

        text_lower = ent.text.lower()
        if ent.type == "person" and text_lower in fm_people:
            continue
        if ent.type == "organization" and text_lower in fm_orgs:
            continue

        if ent.type == "person" and canon_available and db_path is not None:
            try:
                from services.entity_canonicalization import resolve_entity_sync
                node_id = resolve_entity_sync(
                    ent.text, "person", db_path, existing_people,
                )
                label = node_id.split(":", 1)[1] if ":" in node_id else ent.text
            except Exception:
                node_id = f"person:{ent.text}"
                label = ent.text
        else:
            label = ent.text
            node_id = f"{node_type}:{label}"

        pair = (note_id, node_id, edge_type)
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)

        graph.add_node(node_id, node_type, label)
        graph.add_edge(note_id, node_id, edge_type)
        edges_added += 1

        existing_for_type = existing_labels_by_type.setdefault(node_type, [])
        if label not in existing_for_type:
            existing_for_type.append(label)

    return edges_added
