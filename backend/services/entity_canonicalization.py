"""Entity canonicalization: deduplicate entities via alias table + fuzzy matching.

Maps variant names ("Michał", "Kowalski", "Michał Kowalski") to a single
canonical entity ID. Uses Jaro-Winkler string similarity for fuzzy matching.
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Thresholds for automatic merge
AUTO_MERGE_THRESHOLD = 0.88
SUGGEST_MERGE_THRESHOLD = 0.75


@dataclass
class CanonicalEntity:
    canonical_id: str
    label: str
    entity_type: str
    aliases: List[str]


def normalize_name(name: str) -> str:
    """Lowercase, strip whitespace, collapse multiple spaces."""
    return " ".join(name.lower().strip().split())


def _jaro_similarity(s1: str, s2: str) -> float:
    """Jaro string similarity. Returns 0.0–1.0."""
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    match_distance = max(len1, len2) // 2 - 1
    if match_distance < 0:
        match_distance = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2

    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len2)
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    return (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3


def jaro_winkler_similarity(s1: str, s2: str, p: float = 0.1) -> float:
    """Jaro-Winkler string similarity. Returns 0.0–1.0."""
    jaro = _jaro_similarity(s1, s2)
    # Common prefix length (max 4)
    prefix = 0
    for i in range(min(len(s1), len(s2), 4)):
        if s1[i] == s2[i]:
            prefix += 1
        else:
            break
    return jaro + prefix * p * (1 - jaro)


def resolve_entity_sync(
    raw_name: str,
    entity_type: str,
    db_path: Path,
    existing_labels: Optional[List[str]] = None,
) -> str:
    """Resolve a raw entity name to its canonical ID (sync version for graph rebuild).

    1. Check alias table for exact match
    2. Check fuzzy match against existing canonical entities
    3. If no match found, create new canonical entity
    """
    normalized = normalize_name(raw_name)
    if not normalized:
        return f"{entity_type}:{raw_name}"

    conn = sqlite3.connect(str(db_path))
    try:
        # Step 1: Exact alias lookup
        try:
            cursor = conn.execute(
                "SELECT canonical_id FROM entity_aliases WHERE alias = ? AND entity_type = ?",
                (normalized, entity_type),
            )
            row = cursor.fetchone()
            if row:
                return row[0]
        except sqlite3.OperationalError:
            # Table may not exist yet
            return f"{entity_type}:{raw_name}"

        # Step 2: Fuzzy match against all known aliases of this type
        cursor = conn.execute(
            "SELECT DISTINCT canonical_id, alias FROM entity_aliases WHERE entity_type = ?",
            (entity_type,),
        )
        known = cursor.fetchall()

        best_match = None
        best_score = 0.0
        for canonical_id, alias in known:
            score = jaro_winkler_similarity(normalized, alias)
            if score > best_score:
                best_score = score
                best_match = canonical_id

        if best_match and best_score >= AUTO_MERGE_THRESHOLD:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO entity_aliases (alias, canonical_id, entity_type, confidence, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (normalized, best_match, entity_type, round(best_score, 3), now),
            )
            conn.commit()
            return best_match

        # Step 3: Check existing_labels from graph (for first-time entities)
        if existing_labels:
            for label in existing_labels:
                score = jaro_winkler_similarity(normalized, normalize_name(label))
                if score >= AUTO_MERGE_THRESHOLD:
                    canonical_id = f"{entity_type}:{label}"
                    now = datetime.now(timezone.utc).isoformat()
                    conn.execute(
                        "INSERT OR IGNORE INTO entity_aliases (alias, canonical_id, entity_type, confidence, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (normalized, canonical_id, entity_type, round(score, 3), now),
                    )
                    conn.commit()
                    return canonical_id

        # Step 4: New entity — register canonical form
        canonical_id = f"{entity_type}:{raw_name}"
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO entity_aliases (alias, canonical_id, entity_type, confidence, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (normalized, canonical_id, entity_type, 1.0, now),
        )
        conn.commit()
        return canonical_id
    finally:
        conn.close()


async def merge_entities(
    source_id: str,
    target_id: str,
    entity_type: str,
    db_path: Path,
) -> None:
    """Merge source entity into target. All source aliases become target aliases."""
    import aiosqlite
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(
            "UPDATE entity_aliases SET canonical_id = ? WHERE canonical_id = ? AND entity_type = ?",
            (target_id, source_id, entity_type),
        )
        await db.commit()


async def find_merge_candidates(
    entity_type: str,
    db_path: Path,
) -> List[dict]:
    """Find pairs of entities that might be duplicates."""
    import aiosqlite
    async with aiosqlite.connect(str(db_path)) as db:
        try:
            cursor = await db.execute(
                "SELECT DISTINCT canonical_id FROM entity_aliases WHERE entity_type = ?",
                (entity_type,),
            )
            canonical_ids = [row[0] for row in await cursor.fetchall()]
        except Exception:
            return []

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
