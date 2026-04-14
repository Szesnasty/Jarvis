# Step 14a — Entity Extraction + Bidirectional Links

> **Goal**: Enrich graph with entities extracted from note body text (zero API cost)
> and make wiki-links bidirectional so backlinks appear automatically.

**Status**: ⬜ Not started
**Depends on**: Step 13 (graph-guided retrieval)

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| **Entity extraction** | Regex-based extraction of people, dates, projects from note body |
| **Bidirectional wiki-links** | If A links to B, B automatically links back to A |
| **Integration with ingest** | Entities extracted during fast ingest (no rebuild needed) |

**What this step does NOT cover** (deferred to 14b):
- Keyword-similarity edges
- Temporal edges
- Edge pruning for overloaded tags
- Full rebuild pipeline integration

---

## Dependencies

No new packages. Uses existing regex, frontmatter parsing, and graph infrastructure.

---

## Files to Create / Modify

```
backend/
├── services/
│   ├── entity_extraction.py       # NEW — regex-based entity extractor
│   ├── graph_service.py           # MODIFY — bidirectional links in rebuild
│   └── ingest.py                  # MODIFY — call entity extraction during fast ingest
├── tests/
│   ├── test_entity_extraction.py  # NEW — entity extractor tests
│   └── test_graph_service.py      # MODIFY — add bidirectional link tests
```

---

## A. Entity Extraction at Ingest (Zero API Cost)

Extract entities from note body during fast ingest. No Claude call — pure regex + heuristics.

**File: `entity_extraction.py`**

```python
import re
from dataclasses import dataclass
from typing import List


@dataclass
class ExtractedEntity:
    text: str
    type: str       # "person" | "date" | "project" | "place" | "organization"
    confidence: float  # 0.0 - 1.0


# --- Person detection ---
_PERSON_RE = re.compile(
    r"(?<![.!?]\s)(?:(?:with|from|by|to|for|and|met|called|emailed|told|asked)\s+)"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"
)

_STANDALONE_NAME_RE = re.compile(
    r"\b((?:Dr|Mr|Mrs|Ms|Prof)\.?\s+)?([A-Z][a-z]{1,20}\s+[A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20})?)\b"
)

# --- Date detection ---
_DATE_PATTERNS = [
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
    re.compile(r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})\b", re.I),
    re.compile(r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4})\b", re.I),
    re.compile(r"\b((?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))\b", re.I),
    re.compile(r"\b(yesterday|today|tomorrow|last week|next week|this week)\b", re.I),
]

# --- Project detection ---
_PROJECT_RE = re.compile(r"(?:project|initiative|program)[:\s]+([A-Z][\w\s-]{2,30}?)(?:[,.\n]|$)", re.I)
_ACRONYM_RE = re.compile(r"\b([A-Z]{2,6})\b")

# Common false positives
_SKIP_NAMES = frozenset({
    "The", "This", "That", "There", "These", "Those", "What", "When",
    "Where", "Which", "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday", "January", "February", "March",
    "April", "May", "June", "July", "August", "September", "October",
    "November", "December", "New York", "United States", "San Francisco",
    "HTTP", "HTML", "JSON", "YAML", "TODO", "NOTE", "FIXME",
})

_SKIP_ACRONYMS = frozenset({
    "AI", "ML", "US", "UK", "EU", "IT", "HR", "PM", "CEO", "CTO",
    "API", "URL", "PDF", "CSV", "SQL", "HTTP", "HTML", "JSON",
    "TODO", "NOTE", "FIXME", "NASA", "FAQ",
})


def extract_entities(text: str, existing_people: list[str] = None) -> list[ExtractedEntity]:
    """Extract entities from note text using regex heuristics.

    existing_people: known person labels from graph, used to boost confidence.
    """
    entities = []
    existing_set = {p.lower() for p in (existing_people or [])}

    # People
    for match in _STANDALONE_NAME_RE.finditer(text):
        name = match.group(2).strip()
        if name in _SKIP_NAMES or len(name) < 4:
            continue
        confidence = 0.7 if name.lower() in existing_set else 0.4
        entities.append(ExtractedEntity(text=name, type="person", confidence=confidence))

    for match in _PERSON_RE.finditer(text):
        name = match.group(1).strip()
        if name in _SKIP_NAMES or len(name) < 4:
            continue
        confidence = 0.8 if name.lower() in existing_set else 0.5
        entities.append(ExtractedEntity(text=name, type="person", confidence=confidence))

    # Dates
    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            entities.append(ExtractedEntity(
                text=match.group(1) if match.lastindex else match.group(0),
                type="date",
                confidence=0.9,
            ))

    # Projects
    for match in _PROJECT_RE.finditer(text):
        name = match.group(1).strip()
        if len(name) < 3:
            continue
        entities.append(ExtractedEntity(text=name, type="project", confidence=0.6))

    # Deduplicate
    seen = set()
    unique = []
    for e in entities:
        key = (e.text.lower(), e.type)
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return unique
```

**Integration with ingest:** During `fast_ingest`, after parsing frontmatter, run `extract_entities` on body. Entities with `confidence >= 0.5` of type "person" are added as `mentions` edges (only if not already in frontmatter `people:`).

---

## B. Bidirectional Wiki-Link Resolution

Currently if note A has `[[B]]`, we create edge `A → B`. But B doesn't know about A.

**Fix in `rebuild_graph`:**

After first pass (collecting all forward links), run a second pass:

```python
def _resolve_bidirectional_links(graph: Graph) -> None:
    """For each linked edge A→B, add B→A if not already present."""
    forward_links = [(e.source, e.target) for e in graph.edges if e.type == "linked"]
    forward_set = set(forward_links)

    for src, tgt in forward_links:
        reverse = (tgt, src)
        if reverse in forward_set:
            # Mutual link: boost both edges weight
            pass
        elif tgt in graph.nodes:
            # One-way link: add weak backlink (0.6 weight vs 1.0 for explicit)
            graph.add_edge(tgt, src, "linked")
```

---

## Tests

```
test_extract_entities_person          — "met with Jan Kowalski" → person entity
test_extract_entities_date            — "2026-04-14" and "last week" → date entities
test_extract_entities_project         — "Project: Aurora" → project entity
test_extract_entities_dedup           — same name twice → one entity
test_extract_entities_skip_common     — "The Monday" not extracted as person
test_extract_entities_known_boost     — known person gets higher confidence

test_bidirectional_links              — A→B exists, B→A added automatically
test_bidirectional_mutual_boost       — A→B and B→A both exist → weight boosted
```

---

## Definition of Done

- [ ] Entity extraction runs during fast ingest, finds people/dates/projects from body text
- [ ] Entities with confidence ≥ 0.5 added to graph as `mentions` edges
- [ ] Wiki-links are bidirectional (backlinks auto-generated)
- [ ] Backlinks have lower weight (0.6) than explicit links (1.0)
- [ ] Mutual links get boosted weight
- [ ] All tests pass (8 test cases)
- [ ] Documentation updated
