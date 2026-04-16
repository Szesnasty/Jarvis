# Step 20d — Entity Canonicalization + Alias Table

> **Goal**: Deduplicate entities in the knowledge graph so that "Sam Altman",
> "Altman", "Sam", and "CEO of OpenAI" all resolve to the same canonical node.
> Add an alias table and a fuzzy merge pipeline.

**Status**: ⬜ Not started
**Depends on**: Nothing (can run in parallel with 20b/20c)
**Effort**: ~1.5 days

---

## Why This Matters

Today's entity extraction (`entity_extraction.py`) creates person nodes from regex.
There is no canonicalization — the same person can appear as multiple nodes:

```
person:Michał Kowalski   (from frontmatter `people: [Michał Kowalski]`)
person:Michał            (from body text "met with Michał")
person:Kowalski          (from body text "Kowalski said...")
```

This means:
- Graph shows 3 disconnected person nodes for one person
- `query_entity("Michał")` only finds edges to `person:Michał`, missing ones from `person:Michał Kowalski`
- Graph scoring in retrieval misses connections through aliases
- Node count inflates, making graph visualization messy

---

## What This Step Covers

| Feature | Description |
|---------|-------------|
| `entity_aliases` table | Maps variant names to canonical entity IDs |
| `canonicalize_entity()` | Given a raw name, return canonical ID or create new |
| Merge pipeline | Find and merge duplicate person/project nodes |
| Fuzzy matching | Jaro-Winkler + lowercase normalization for dedup |
| Updated `_enrich_with_entities()` | Use canonical IDs when adding entity nodes |
| Updated `ingest_note()` | Canonicalize entities during incremental graph update |
| Graph merge endpoint | API to manually merge two nodes (UI-driven) |

**What this step does NOT cover**:
- Embedding-based entity matching (overkill for this scale — fuzzy string is enough)
- Automatic cross-type entity linking (person↔project)
- NER model replacement (regex extraction stays; canonicalization is a post-processing step)

---

## File Structure

```
backend/
  services/
    entity_canonicalization.py  # NEW — canonical ID resolution + merge
    entity_extraction.py        # MODIFY — integrate canonicalization
    graph_service.py            # MODIFY — use canonical IDs in entity edges
  models/
    database.py                 # MODIFY — add entity_aliases table
  routers/
    graph.py                    # MODIFY — add merge endpoint
  tests/
    test_entity_canonicalization.py # NEW
```

---

## Schema Changes (`database.py`)

```sql
CREATE TABLE IF NOT EXISTS entity_aliases (
    alias TEXT NOT NULL,
    canonical_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,       -- "person", "project", etc.
    confidence REAL DEFAULT 1.0,     -- 1.0 = manual merge, <1.0 = auto
    created_at TEXT NOT NULL,
    PRIMARY KEY (alias, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_alias_canonical ON entity_aliases(canonical_id);
```

**Example rows**:

| alias | canonical_id | entity_type | confidence |
|-------|-------------|-------------|------------|
| michał kowalski | person:Michał Kowalski | person | 1.0 |
| michał | person:Michał Kowalski | person | 0.85 |
| kowalski | person:Michał Kowalski | person | 0.80 |
| sam altman | person:Sam Altman | person | 1.0 |
| altman | person:Sam Altman | person | 0.75 |

---

## Implementation Details

### 1. `entity_canonicalization.py` — Core Logic

```python
from dataclasses import dataclass
from typing import Optional
import aiosqlite


@dataclass
class CanonicalEntity:
    canonical_id: str
    label: str
    entity_type: str
    aliases: list[str]


def normalize_name(name: str) -> str:
    """Lowercase, strip whitespace, collapse multiple spaces."""
    return " ".join(name.lower().strip().split())


def jaro_winkler_similarity(s1: str, s2: str) -> float:
    """Jaro-Winkler string similarity. Returns 0.0–1.0."""
    # Implementation or use jellyfish/rapidfuzz library
    ...


# Thresholds for automatic merge
AUTO_MERGE_THRESHOLD = 0.88       # Above this: auto-merge
SUGGEST_MERGE_THRESHOLD = 0.75    # Above this: suggest merge (log, don't auto)


async def resolve_entity(
    raw_name: str,
    entity_type: str,
    db_path: Path,
    existing_labels: list[str] | None = None,
) -> str:
    """Resolve a raw entity name to its canonical ID.

    1. Check alias table for exact match
    2. Check fuzzy match against existing canonical entities
    3. If no match found, create new canonical entity
    """
    normalized = normalize_name(raw_name)

    async with aiosqlite.connect(str(db_path)) as db:
        # Step 1: Exact alias lookup
        cursor = await db.execute(
            "SELECT canonical_id FROM entity_aliases WHERE alias = ? AND entity_type = ?",
            (normalized, entity_type),
        )
        row = await cursor.fetchone()
        if row:
            return row[0]

        # Step 2: Fuzzy match against all known aliases of this type
        cursor = await db.execute(
            "SELECT DISTINCT canonical_id, alias FROM entity_aliases WHERE entity_type = ?",
            (entity_type,),
        )
        known = await cursor.fetchall()

        best_match = None
        best_score = 0.0
        for canonical_id, alias in known:
            score = jaro_winkler_similarity(normalized, alias)
            if score > best_score:
                best_score = score
                best_match = canonical_id

        if best_match and best_score >= AUTO_MERGE_THRESHOLD:
            # Auto-merge: add this as a new alias
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT OR IGNORE INTO entity_aliases (alias, canonical_id, entity_type, confidence, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (normalized, best_match, entity_type, round(best_score, 3), now),
            )
            await db.commit()
            return best_match

        # Step 3: Also check existing_labels from graph (for first-time entities)
        if existing_labels:
            for label in existing_labels:
                score = jaro_winkler_similarity(normalized, normalize_name(label))
                if score >= AUTO_MERGE_THRESHOLD:
                    canonical_id = f"{entity_type}:{label}"
                    now = datetime.now(timezone.utc).isoformat()
                    await db.execute(
                        "INSERT OR IGNORE INTO entity_aliases (alias, canonical_id, entity_type, confidence, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (normalized, canonical_id, entity_type, round(score, 3), now),
                    )
                    await db.commit()
                    return canonical_id

        # Step 4: New entity — register canonical form
        canonical_id = f"{entity_type}:{raw_name}"
        now = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "INSERT OR IGNORE INTO entity_aliases (alias, canonical_id, entity_type, confidence, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (normalized, canonical_id, entity_type, 1.0, now),
        )
        await db.commit()
        return canonical_id


async def merge_entities(
    source_id: str,
    target_id: str,
    entity_type: str,
    db_path: Path,
) -> None:
    """Merge source entity into target. All source aliases become target aliases."""
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(
            "UPDATE entity_aliases SET canonical_id = ? WHERE canonical_id = ? AND entity_type = ?",
            (target_id, source_id, entity_type),
        )
        await db.commit()


async def find_merge_candidates(
    entity_type: str,
    db_path: Path,
) -> list[dict]:
    """Find pairs of entities that might be duplicates (score >= SUGGEST_MERGE_THRESHOLD)."""
    async with aiosqlite.connect(str(db_path)) as db:
        cursor = await db.execute(
            "SELECT DISTINCT canonical_id FROM entity_aliases WHERE entity_type = ?",
            (entity_type,),
        )
        canonical_ids = [row[0] for row in await cursor.fetchall()]

    candidates = []
    for i in range(len(canonical_ids)):
        for j in range(i + 1, len(canonical_ids)):
            id_a, id_b = canonical_ids[i], canonical_ids[j]
            label_a = id_a.split(":", 1)[1] if ":" in id_a else id_a
            label_b = id_b.split(":", 1)[1] if ":" in id_b else id_b
            score = jaro_winkler_similarity(
                normalize_name(label_a), normalize_name(label_b),
            )
            if score >= SUGGEST_MERGE_THRESHOLD:
                candidates.append({
                    "entity_a": id_a,
                    "entity_b": id_b,
                    "similarity": round(score, 3),
                })

    return sorted(candidates, key=lambda x: x["similarity"], reverse=True)
```

### 2. Integration with `graph_service.py`

In `_enrich_with_entities()`, replace direct node creation with canonical resolution:

```python
# Before (current code):
person_id = f"person:{ent.text}"
graph.add_node(person_id, "person", ent.text)
graph.add_edge(node.id, person_id, "mentions")

# After:
from services.entity_canonicalization import resolve_entity
canonical_id = await resolve_entity(
    ent.text, "person", db_path,
    existing_labels=existing_people,
)
label = canonical_id.split(":", 1)[1] if ":" in canonical_id else ent.text
graph.add_node(canonical_id, "person", label)
graph.add_edge(node.id, canonical_id, "mentions")
```

**Problem**: `_enrich_with_entities()` is sync, `resolve_entity()` is async.
Options:
1. Make `_enrich_with_entities()` async + `rebuild_graph()` async — large refactor
2. Use sync SQLite in `resolve_entity_sync()` — simpler, OK for rebuild

**Recommendation**: Add `resolve_entity_sync()` using `sqlite3` directly,
matching the pattern already used by `_compute_embedding_similarity_edges()`.

### 3. API Endpoint for Manual Merge

```python
# routers/graph.py

class MergeRequest(BaseModel):
    source_id: str
    target_id: str

@router.post("/merge-entities")
async def merge_entities_endpoint(body: MergeRequest):
    """Manually merge two entity nodes."""
    from services.entity_canonicalization import merge_entities
    db_path = memory_service._db_path()
    await merge_entities(body.source_id, body.target_id, entity_type="person", db_path=db_path)
    # Rebuild graph to reflect merge
    import asyncio
    graph_service.invalidate_cache()
    await asyncio.to_thread(graph_service.rebuild_graph)
    return {"status": "merged", "kept": body.target_id, "removed": body.source_id}


@router.get("/merge-candidates")
async def get_merge_candidates(entity_type: str = "person"):
    """Find entity pairs that might be duplicates."""
    from services.entity_canonicalization import find_merge_candidates
    db_path = memory_service._db_path()
    return await find_merge_candidates(entity_type, db_path)
```

---

## Jaro-Winkler Implementation

Rather than adding a dependency (`jellyfish`, `rapidfuzz`), implement a
minimal Jaro-Winkler in pure Python (~40 lines). The function is only
called during graph rebuild (not per-query), so performance isn't critical.

Alternatively, use `difflib.SequenceMatcher` as a quick proxy:
```python
from difflib import SequenceMatcher

def string_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()
```

This is simpler and good enough for MVP. Jaro-Winkler can replace it later.

---

## Test Cases

```python
# test_entity_canonicalization.py

async def test_exact_alias_resolution():
    """'michał kowalski' resolves to person:Michał Kowalski."""

async def test_fuzzy_alias_resolution():
    """'Kowalski' auto-merges to person:Michał Kowalski (Jaro-Winkler > 0.88)."""

async def test_new_entity_registered():
    """Unknown name creates new canonical entity + alias."""

async def test_merge_entities():
    """After merge, all source aliases point to target."""

async def test_find_merge_candidates():
    """Candidates sorted by similarity, filtered by threshold."""

async def test_normalize_name():
    """'  Michał   KOWALSKI ' → 'michał kowalski'."""

async def test_graph_uses_canonical_ids():
    """After rebuild, 'Michał' and 'Michał Kowalski' share the same node."""

async def test_case_insensitive_resolution():
    """'MICHAŁ' resolves to same canonical as 'michał'."""

async def test_no_false_positive_merge():
    """'Anna' and 'Hanna' stay separate (below threshold)."""

async def test_manual_merge_via_api():
    """POST /api/graph/merge-entities merges nodes and rebuilds graph."""
```

---

## Acceptance Criteria

- [ ] `entity_aliases` table created on startup
- [ ] `resolve_entity()` resolves raw names to canonical IDs
- [ ] Auto-merge at Jaro-Winkler ≥ 0.88
- [ ] New entities auto-registered in alias table
- [ ] `_enrich_with_entities()` uses canonical IDs
- [ ] `merge_entities()` repoints all aliases from source to target
- [ ] `find_merge_candidates()` finds potential duplicates
- [ ] `POST /api/graph/merge-entities` endpoint works
- [ ] `GET /api/graph/merge-candidates` returns ranked candidates
- [ ] Graph node count reduced (fewer duplicates)
- [ ] All existing entity extraction tests pass
- [ ] All new tests pass
