"""Tests for Polish / diacritic normalisation in alias_index - Step 26b."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from services.alias_index import (
    normalise_phrase,
    upsert_note_aliases,
    scan_body,
)


# ---------------------------------------------------------------------------
# normalise_phrase -- diacritic stripping
# ---------------------------------------------------------------------------

class TestNormalisePhrase:
    def test_lodz(self):
        # L-stroke, o-acute, z-acute -> lodz
        assert normalise_phrase("\u0141\xf3d\u017a") == "lodz"

    def test_zazolc_gesla_jazn(self):
        # "Zaz\xf3\u0142\u0107 g\u0119\u015bl\u0105 ja\u017a\u0144"
        result = normalise_phrase("Za\u017c\xf3\u0142\u0107 g\u0119\u015bl\u0105 ja\u017a\u0144")
        assert result == "zazolc gesla jazn"

    def test_swinoujscie(self):
        # Ś=Ś w-i-n-o-u-j-ś-c-i-e (11 chars)
        assert normalise_phrase("\u015awinouj\u015bcie") == "swinoujscie"

    def test_michal(self):
        # l-stroke -> l
        assert normalise_phrase("Micha\u0142") == "michal"

    def test_zolc_lowercase(self):
        assert normalise_phrase("\u017c\xf3\u0142\u0107") == "zolc"

    def test_ascii_unchanged(self):
        assert normalise_phrase("hello world") == "hello world"

    def test_uppercase_lowercased(self):
        assert normalise_phrase("RUST") == "rust"

    def test_whitespace_collapsed(self):
        assert normalise_phrase("  hybrid  retrieval ") == "hybrid retrieval"

    def test_empty_string(self):
        assert normalise_phrase("") == ""


# ---------------------------------------------------------------------------
# Alias scan -- Polish title matching
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    return tmp_path / "app" / "jarvis.db"


def test_polish_title_matched_in_body(db):
    """Body containing Polish title should match the indexed alias."""
    upsert_note_aliases(
        db, "notes/hybrid.md",
        title="Wyszukiwanie hybrydowe",
        aliases=[],
    )
    hits = scan_body(db, "Najlepsza technika to wyszukiwanie hybrydowe w systemach.")
    paths = [h["path"] for h in hits]
    assert "notes/hybrid.md" in paths


def test_polish_alias_matched_in_body(db):
    """Body containing Polish city name should match stored alias."""
    upsert_note_aliases(
        db, "notes/lodz.md",
        # "Lodz" with Polish diacritics
        title="\u0141\xf3d\u017a",
        aliases=[],
    )
    hits = scan_body(db, "Spotkanie w \u0141\xf3d\u017a w tym tygodniu.")
    paths = [h["path"] for h in hits]
    assert "notes/lodz.md" in paths


def test_ascii_body_matches_polish_alias(db):
    """ASCII body 'lodz' should match normalised alias for Polish name."""
    upsert_note_aliases(
        db, "notes/lodz2.md",
        title="\u0141\xf3d\u017a",
        aliases=[],
    )
    hits = scan_body(db, "The team is in lodz this week.")
    paths = [h["path"] for h in hits]
    assert "notes/lodz2.md" in paths


def test_michal_alias_matched(db):
    """'Micha\u0142 Kowalski' stored alias should match body containing it."""
    upsert_note_aliases(
        db, "notes/person.md",
        title="Notatki o Michale",
        aliases=["Micha\u0142 Kowalski"],
    )
    hits = scan_body(db, "Micha\u0142 Kowalski pracuje nad projektem.")
    paths = [h["path"] for h in hits]
    assert "notes/person.md" in paths


def test_self_match_excluded(db):
    """The note's own path must be excluded from scan results."""
    upsert_note_aliases(
        db, "notes/self.md",
        title="Wyszukiwanie hybrydowe",
        aliases=[],
    )
    hits = scan_body(
        db,
        "Wyszukiwanie hybrydowe is the best approach.",
        exclude_path="notes/self.md",
    )
    paths = [h["path"] for h in hits]
    assert "notes/self.md" not in paths


def test_polish_scan_returns_phrase_field(db):
    """Each hit must include a non-empty 'phrase' field."""
    upsert_note_aliases(
        db, "notes/gesla.md",
        title="g\u0119\u015bl\u0105 ja\u017a\u0144",
        aliases=[],
    )
    hits = scan_body(db, "g\u0119\u015bl\u0105 ja\u017a\u0144 w tym zdaniu.")
    matched = [h for h in hits if h["path"] == "notes/gesla.md"]
    assert matched, "Expected a hit for gesla.md"
    assert "phrase" in matched[0]
    assert matched[0]["phrase"]


def test_multiple_polish_notes_matched(db):
    """Body mentioning multiple Polish titles returns multiple hits."""
    upsert_note_aliases(db, "notes/n1.md", title="Micha\u0142 Nowak", aliases=[])
    # Use just the city name so the 4-char normalised form 'lodz' is indexed
    upsert_note_aliases(db, "notes/n2.md", title="\u0141\xf3d\u017a", aliases=[])
    body = "Micha\u0142 Nowak prowadzi projekt w \u0141\xf3d\u017a."
    hits = scan_body(db, body)
    paths = [h["path"] for h in hits]
    assert "notes/n1.md" in paths
    assert "notes/n2.md" in paths
