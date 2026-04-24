"""Alias index for Step 25 Smart Connect.

Maintains a SQLite table of normalised phrases (titles, aliases, headings)
that map to note paths. Used at ingest time to detect when a new note's
body mentions another note by title or by a frontmatter-declared alias.

Source of truth remains Markdown frontmatter (`title`, `aliases:`); this
table is a rebuildable index. If `app/jarvis.db` is wiped, calling
`rebuild_index()` over the workspace recreates it.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

ALIAS_INDEX_SQL = """
CREATE TABLE IF NOT EXISTS alias_index (
    phrase_norm TEXT NOT NULL,
    note_path   TEXT NOT NULL,
    kind        TEXT NOT NULL,
    PRIMARY KEY (phrase_norm, note_path, kind)
);
CREATE INDEX IF NOT EXISTS idx_alias_phrase ON alias_index(phrase_norm);
CREATE INDEX IF NOT EXISTS idx_alias_note   ON alias_index(note_path);
"""

# Phrases shorter than this (after normalisation) are dropped — too noisy.
MIN_PHRASE_CHARS = 4
# Maximum n-gram length when scanning a body.
MAX_NGRAM = 4
# Token regex — keep unicode word chars (Polish, etc.) and digits.
_TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)

# Characters NFKD doesn't decompose (no combining marks). Mapped manually so
# Polish/Czech/etc. stems compare equal to their ASCII transliteration.
_EXTRA_DIACRITIC_MAP = str.maketrans({
    "ł": "l", "Ł": "l",
    "đ": "d", "Đ": "d",
    "ø": "o", "Ø": "o",
    "ß": "ss",
})


def _strip_diacritics(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    no_marks = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    return no_marks.translate(_EXTRA_DIACRITIC_MAP)


def normalise_phrase(text: str) -> str:
    """Lowercase, NFKD-strip combining marks, collapse whitespace.

    Keeps Polish stems intact at the byte level (mój → moj) so that
    'Mój Dzień' and 'mój dzień' compare equal and 'Mój' inside a body
    text matches a frontmatter title 'Mój dzień'.
    """
    if not text:
        return ""
    return re.sub(r"\s+", " ", _strip_diacritics(text).lower()).strip()


def _ensure_table(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(ALIAS_INDEX_SQL)
        conn.commit()


def _collect_phrases(
    title: Optional[str],
    aliases: Iterable[str],
    headings: Iterable[str],
) -> List[Tuple[str, str]]:
    """Return list of (phrase_norm, kind) pairs, deduplicated, length-filtered."""
    out: Dict[Tuple[str, str], None] = {}
    if title:
        norm = normalise_phrase(title)
        if len(norm) >= MIN_PHRASE_CHARS:
            out[(norm, "title")] = None
    for raw in aliases or ():
        if not isinstance(raw, str):
            continue
        norm = normalise_phrase(raw)
        if len(norm) >= MIN_PHRASE_CHARS:
            out.setdefault((norm, "alias"), None)
    for raw in headings or ():
        if not isinstance(raw, str):
            continue
        norm = normalise_phrase(raw)
        if len(norm) >= MIN_PHRASE_CHARS:
            out.setdefault((norm, "heading"), None)
    return list(out.keys())


def upsert_note_aliases(
    db_path: Path,
    note_path: str,
    *,
    title: Optional[str],
    aliases: Iterable[str] = (),
    headings: Iterable[str] = (),
) -> int:
    """Replace all alias_index rows for ``note_path`` with the new set.

    Returns the number of rows written.
    """
    _ensure_table(db_path)
    rows = _collect_phrases(title, aliases, headings)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("DELETE FROM alias_index WHERE note_path = ?", (note_path,))
        if rows:
            conn.executemany(
                "INSERT OR IGNORE INTO alias_index(phrase_norm, note_path, kind) "
                "VALUES (?, ?, ?)",
                [(norm, note_path, kind) for norm, kind in rows],
            )
        conn.commit()
    return len(rows)


def remove_note(db_path: Path, note_path: str) -> None:
    if not db_path.exists():
        return
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("DELETE FROM alias_index WHERE note_path = ?", (note_path,))
        conn.commit()


def _tokenise(text: str) -> List[str]:
    if not text:
        return []
    return [tok.lower() for tok in _TOKEN_RE.findall(_strip_diacritics(text))]


def scan_body(
    db_path: Path,
    body: str,
    *,
    exclude_path: Optional[str] = None,
    max_ngram: int = MAX_NGRAM,
) -> List[Dict[str, object]]:
    """Find alias_index hits inside ``body``.

    Generates n-grams (1..max_ngram) over the body and checks each against
    the index. Returns one entry per (note_path, kind) hit:

    ``{"path": str, "phrase": str, "kind": str, "count": int}``

    The ``exclude_path`` argument suppresses self-matches (a note's own
    title appearing in its own body).
    """
    if not db_path.exists():
        return []
    tokens = _tokenise(body)
    if not tokens:
        return []

    # Generate candidate phrases (deduped) with their occurrence counts.
    candidate_counts: Dict[str, int] = {}
    for n in range(1, max_ngram + 1):
        if n > len(tokens):
            break
        for i in range(len(tokens) - n + 1):
            phrase = " ".join(tokens[i : i + n])
            if len(phrase) < MIN_PHRASE_CHARS:
                continue
            candidate_counts[phrase] = candidate_counts.get(phrase, 0) + 1

    if not candidate_counts:
        return []

    # Look up in chunks (SQLite parameter limit is ~999).
    phrases = list(candidate_counts.keys())
    hits: Dict[Tuple[str, str], Dict[str, object]] = {}
    with sqlite3.connect(str(db_path)) as conn:
        for start in range(0, len(phrases), 800):
            batch = phrases[start : start + 800]
            placeholders = ",".join("?" * len(batch))
            cursor = conn.execute(
                f"SELECT phrase_norm, note_path, kind FROM alias_index "
                f"WHERE phrase_norm IN ({placeholders})",
                batch,
            )
            for phrase_norm, note_path, kind in cursor.fetchall():
                if exclude_path and note_path == exclude_path:
                    continue
                key = (note_path, kind)
                count = candidate_counts.get(phrase_norm, 0)
                existing = hits.get(key)
                if existing is None or count > existing["count"]:  # type: ignore[index]
                    hits[key] = {
                        "path": note_path,
                        "phrase": phrase_norm,
                        "kind": kind,
                        "count": count,
                    }
    return list(hits.values())


def known_paths(db_path: Path) -> Set[str]:
    if not db_path.exists():
        return set()
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.execute("SELECT DISTINCT note_path FROM alias_index")
        return {row[0] for row in cursor.fetchall()}
