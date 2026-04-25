"""Shared helpers for translating extracted entities into graph nodes/edges.

Used by both the full ``rebuild_graph`` pass (``builder._enrich_with_entities``)
and the incremental ``ingest_note`` path so the two stay in sync.

Step 25 PR 2 — adds organization, project and place entity types alongside
the pre-existing person extraction. Dates are intentionally excluded from
the graph: they create dense, low-signal stars and are better expressed as
temporal edges (``rebuild_graph`` handles that separately).

Step 27 — per-note caps + co-mention bridges.

Prior failure modes (logged here so we don't repeat them):

* **No caps** — a 200-page paper produced ~510 ``mentions_org`` edges from
  one note, dominating the graph. Bibliography fragments leaked through
  because the extractor was over-recalling. Fixed: per-type top-K caps
  ranked by confidence so the *best* entities survive, not the first.

* **Too aggressive caps + confidence floor** (briefly tried) — a 0.7
  confidence floor combined with caps of 8/5/3/3 produced *zero* entity
  edges, because the extractor's natural confidences sit at 0.5–0.6.
  Lesson: don't override the extractor's calibration; trust its filters
  (structural rejects + lemmatisation are already in entity_extraction.py)
  and rely on top-K caps for volume control instead.

* **Entities only connected to the note** — a graph where every person
  hangs off the same note and never connects to anything else fails the
  "who works where?" question. Fixed: ``co_mentioned`` edges between
  distinct entities sharing a note (person↔org most useful).

Frontmatter override (``extract_entities: false``) still wins for notes
where the user wants explicit-only entity edges.
"""

from __future__ import annotations

from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from services.graph_service.models import Graph

# entity type from extractor → (graph node type, edge type, min confidence)
# The min-confidence values are the extractor's own calibration thresholds
# — do not raise them here without first measuring extractor recall.
ENTITY_EDGE_MAP: Dict[str, Tuple[str, str, float]] = {
    "person": ("person", "mentions", 0.5),
    "organization": ("org", "mentions_org", 0.5),
    "project": ("project", "mentions_project", 0.5),
    "place": ("place", "mentions_place", 0.5),
}

# Per-note caps. Generous because long-form documents (papers, reports)
# legitimately mention dozens of authors / affiliations. Top-K by
# confidence keeps the highest-quality entities and drops the bibliography
# tail. Tune by measuring entity-precision against a held-out set, not by
# eyeballing the graph.
#
# Step 27b — caps now scale with body length. A 200-word memo keeps the
# original 50/50/25/25 budget; a 30 KB section gets up to 200/200/100/100.
# Hard ceilings prevent a pathological 1 MB note from exploding the graph.
MAX_PERSONS_PER_NOTE = 50  # base / short-note value (kept for back-compat)
MAX_ORGS_PER_NOTE = 50
MAX_PROJECTS_PER_NOTE = 25
MAX_PLACES_PER_NOTE = 25

_PER_TYPE_CAPS: Dict[str, int] = {
    "person": MAX_PERSONS_PER_NOTE,
    "org": MAX_ORGS_PER_NOTE,
    "project": MAX_PROJECTS_PER_NOTE,
    "place": MAX_PLACES_PER_NOTE,
}

# Hard ceilings — never exceeded regardless of body length.
_HARD_CAPS: Dict[str, int] = {
    "person": 200,
    "org": 200,
    "project": 100,
    "place": 100,
}

# Linear scaling window: at <= 2 KB use base caps, at >= 40 KB use hard caps.
_SCALE_BODY_MIN = 2_000
_SCALE_BODY_MAX = 40_000


def compute_caps(body_len: int) -> Dict[str, int]:
    """Scale per-type caps linearly with body length.

    A 200-word memo (~1 KB) gets the original 50/50/25/25 budget. A 30 KB
    section of a long PDF gets a much larger budget so its long-tail
    entities survive and become bridges to other notes.
    """
    if body_len <= _SCALE_BODY_MIN:
        return dict(_PER_TYPE_CAPS)
    if body_len >= _SCALE_BODY_MAX:
        return dict(_HARD_CAPS)
    span = _SCALE_BODY_MAX - _SCALE_BODY_MIN
    ratio = (body_len - _SCALE_BODY_MIN) / span
    return {
        k: int(_PER_TYPE_CAPS[k] + ratio * (_HARD_CAPS[k] - _PER_TYPE_CAPS[k]))
        for k in _PER_TYPE_CAPS
    }


def compute_co_mention_cap(body_len: int) -> int:
    """Scale the per-note co-mention pair cap with body length.

    Base 100 pairs at <= 2 KB, 400 at >= 40 KB.
    """
    if body_len <= _SCALE_BODY_MIN:
        return 100
    if body_len >= _SCALE_BODY_MAX:
        return 400
    span = _SCALE_BODY_MAX - _SCALE_BODY_MIN
    ratio = (body_len - _SCALE_BODY_MIN) / span
    return int(100 + ratio * 300)


def should_run_ner(rel_path: str, fm: Dict) -> bool:
    """Always run NER unless the note explicitly opts out via frontmatter.

    Folder-based deny lists were tried and rolled back — see module
    docstring. The extractor's own structural filters do the quality work.
    """
    explicit = fm.get("extract_entities")
    if explicit is False:
        return False
    return True


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

    rel_path = note_id[5:] if note_id.startswith("note:") else ""
    if not should_run_ner(rel_path, fm):
        return 0

    extraction_text = clean_conversation_text(body) if is_conversation else body
    # Limit NER to the first 20 000 chars. spaCy is O(n) and large PDF sections
    # can exceed 270 KB; full-text NER on those notes takes minutes per note and
    # makes the graph rebuild hang. Entity names appear early in most texts so
    # truncating at 20k chars loses little signal while keeping rebuild fast.
    _NER_CHAR_LIMIT = 20_000
    if len(extraction_text) > _NER_CHAR_LIMIT:
        extraction_text = extraction_text[:_NER_CHAR_LIMIT]
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

    # Pass 1: collect candidates (filtered, threshold-checked, canonicalised).
    # Pass 2: per-type top-K-by-confidence emission.
    # The two-pass split prevents a body that mentions 80 capitalised phrases
    # from blowing the per-note caps with the FIRST 25 it sees rather than
    # the BEST 25.
    existing_people = existing_labels_by_type.setdefault("person", [])
    candidates_by_type: Dict[str, List[Tuple[float, str, str, str]]] = {}
    seen_keys: set = set()

    for ent in extract_entities(extraction_text, existing_people):
        mapping = ENTITY_EDGE_MAP.get(ent.type)
        if mapping is None:
            continue
        node_type, edge_type, default_min = mapping

        if ent.type == "person":
            threshold = person_min_confidence
        else:
            threshold = default_min
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
                resolved_id = resolve_entity_sync(
                    ent.text, "person", db_path, existing_people,
                )
                label = resolved_id.split(":", 1)[1] if ":" in resolved_id else ent.text
                target_node_id = resolved_id
            except Exception:
                label = ent.text
                target_node_id = f"person:{ent.text}"
        else:
            label = ent.text
            target_node_id = f"{node_type}:{label}"

        key = (node_type, target_node_id.lower())
        if key in seen_keys:
            continue
        seen_keys.add(key)

        candidates_by_type.setdefault(node_type, []).append(
            (ent.confidence, target_node_id, label, edge_type)
        )

    edges_added = 0
    # Step 27b — scale caps with body length so long-form sections keep
    # more entities than short memos. Short bodies still get the original
    # 50/50/25/25 to preserve previous behaviour.
    cap_table = compute_caps(len(body))
    # Track which entities actually landed in the graph for this note so
    # the co-mention pass below only links *kept* entities (not the ones
    # that lost the top-K cut).
    kept_entities: List[str] = []  # node ids
    for node_type, candidates in candidates_by_type.items():
        cap = cap_table.get(node_type, 25)
        candidates.sort(key=lambda x: x[0], reverse=True)
        for _conf, target_node_id, label, edge_type in candidates[:cap]:
            graph.add_node(target_node_id, node_type, label)
            graph.add_edge(note_id, target_node_id, edge_type)
            edges_added += 1
            kept_entities.append(target_node_id)

            existing_for_type = existing_labels_by_type.setdefault(node_type, [])
            if label not in existing_for_type:
                existing_for_type.append(label)

    # Frontmatter-declared people/orgs are added by builder.py before this
    # function runs; pull them in too so a body-extracted org can co-mention
    # a frontmatter-declared person.
    for fm_person in fm.get("people", []):
        nid = f"person:{fm_person}"
        if nid in graph.nodes and nid not in kept_entities:
            kept_entities.append(nid)
    for fm_org in fm.get("organizations", []):
        nid = f"org:{fm_org}"
        if nid in graph.nodes and nid not in kept_entities:
            kept_entities.append(nid)

    co_mention_cap = compute_co_mention_cap(len(body))
    edges_added += _emit_co_mentions(graph, kept_entities, max_pairs=co_mention_cap)

    return edges_added


# ── Co-mention edges ────────────────────────────────────────────────────────
#
# Two entities mentioned together in one note are *probably* related. We
# don't try to label the relation (works_for / co-author / based-in) — that's
# a job for an LLM-augmented pass. We just emit a generic ``co_mentioned``
# edge.
#
# Strategy: emit ALL pairs but cap at ``_MAX_CO_MENTION_PAIRS_PER_NOTE``,
# preferring **cross-type** pairs (person↔org, person↔place, org↔project)
# because those answer the most useful questions ("who works where?").
# Same-type pairs (two co-authors) are still emitted but only after the
# cross-type budget is filled — in a 50-person paper that's 1225 pair
# candidates, dwarfing real signal.

CO_MENTION_EDGE_TYPE = "co_mentioned"
_CO_MENTION_TYPES = frozenset({"person", "org", "project", "place"})
# Cap roughly matches MAX_PERSONS + MAX_ORGS so cross-type pairs survive
# but the all-pairs blow-up doesn't.
_MAX_CO_MENTION_PAIRS_PER_NOTE = 100


def _emit_co_mentions(
    graph: Graph,
    kept_entity_ids: List[str],
    *,
    max_pairs: int = _MAX_CO_MENTION_PAIRS_PER_NOTE,
) -> int:
    """Emit ``co_mentioned`` edges between distinct entities of one note.

    Cross-type pairs (person↔org, etc.) are prioritised over same-type
    pairs. Existing pairs are deduped (graph-wide) so two notes mentioning
    the same pair don't duplicate the edge.
    """
    if len(kept_entity_ids) < 2:
        return 0

    allowed: List[str] = []
    seen: set = set()
    for nid in kept_entity_ids:
        node = graph.nodes.get(nid)
        if node is None or node.type not in _CO_MENTION_TYPES:
            continue
        if nid in seen:
            continue
        seen.add(nid)
        allowed.append(nid)

    if len(allowed) < 2:
        return 0

    existing_pairs: set = set()
    for e in graph.edges:
        if e.type == CO_MENTION_EDGE_TYPE:
            existing_pairs.add(tuple(sorted((e.source, e.target))))

    cross_type: List[Tuple[str, str]] = []
    same_type: List[Tuple[str, str]] = []
    allowed.sort()
    for a, b in combinations(allowed, 2):
        type_a = graph.nodes[a].type
        type_b = graph.nodes[b].type
        if type_a != type_b:
            cross_type.append((a, b))
        else:
            same_type.append((a, b))

    pairs_added = 0
    for a, b in cross_type + same_type:
        if pairs_added >= max_pairs:
            break
        key = tuple(sorted((a, b)))
        if key in existing_pairs:
            continue
        existing_pairs.add(key)
        graph.add_edge(a, b, CO_MENTION_EDGE_TYPE)
        pairs_added += 1

    return pairs_added
