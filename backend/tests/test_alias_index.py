"""Tests for the Smart Connect alias index (Step 25 PR 3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from services.alias_index import (
    MIN_PHRASE_CHARS,
    normalise_phrase,
    scan_body,
    upsert_note_aliases,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "alias.db"


def test_normalise_strips_polish_diacritics() -> None:
    assert normalise_phrase("Mój Dzień") == "moj dzien"
    assert normalise_phrase("  Łódź   Główna  ") == "lodz glowna"


def test_normalise_handles_empty() -> None:
    assert normalise_phrase("") == ""
    assert normalise_phrase("   ") == ""


def test_short_phrases_dropped(db_path: Path) -> None:
    written = upsert_note_aliases(
        db_path, "notes/x.md", title="ab", aliases=["xyz"], headings=["a", "Hi"],
    )
    # All phrases below MIN_PHRASE_CHARS — nothing written.
    assert written == 0
    assert MIN_PHRASE_CHARS == 4


def test_upsert_replaces_existing_rows(db_path: Path) -> None:
    upsert_note_aliases(
        db_path, "notes/p.md", title="Hybrid Retrieval", aliases=["RAG pipeline"],
    )
    written = upsert_note_aliases(
        db_path, "notes/p.md", title="Hybrid Retrieval", aliases=["RAG pipeline", "vector search"],
    )
    assert written == 3  # title + 2 aliases

    hits = scan_body(db_path, "We use the vector search engine here.")
    assert any(h["phrase"] == "vector search" for h in hits)


def test_scan_body_finds_alias_with_polish_chars(db_path: Path) -> None:
    upsert_note_aliases(
        db_path,
        "people/lodz.md",
        title="Łódź Główna",
        aliases=["Łódź"],
    )

    body = "Spotkaliśmy się w Łódź Główna wczoraj."
    hits = scan_body(db_path, body, exclude_path="other.md")

    assert any(h["path"] == "people/lodz.md" for h in hits)
    titles = [h["phrase"] for h in hits if h["path"] == "people/lodz.md"]
    assert any("lodz glowna" in p or p == "lodz" for p in titles)


def test_scan_body_excludes_self(db_path: Path) -> None:
    upsert_note_aliases(
        db_path, "notes/me.md", title="Hybrid Retrieval Pipeline",
    )
    hits = scan_body(
        db_path,
        "I documented the Hybrid Retrieval Pipeline here.",
        exclude_path="notes/me.md",
    )
    assert hits == []


def test_scan_body_returns_count_of_occurrences(db_path: Path) -> None:
    upsert_note_aliases(db_path, "notes/r.md", title="RAG pipeline")
    body = "The RAG pipeline is great. The RAG pipeline rocks. RAG pipeline!"
    hits = scan_body(db_path, body)
    assert len(hits) == 1
    assert hits[0]["count"] == 3


def test_ngram_matching_handles_multiword_alias(db_path: Path) -> None:
    upsert_note_aliases(
        db_path, "k/note.md", title="Knowledge Graph", aliases=["graph layer"],
    )
    hits = scan_body(db_path, "We extended the graph layer significantly.")
    assert any(h["phrase"] == "graph layer" for h in hits)


def test_slugify_preserves_polish_titles() -> None:
    """Step 25 PR 3 §9 — _slugify must NFKD-normalise rather than collapse."""
    from services.ingest import _slugify

    assert _slugify("Mój dzień") == "moj-dzien"
    assert _slugify("Łódź Główna") == "lodz-glowna"
    assert _slugify("Notatka — tytuł") == "notatka-tytul"
    # Empty-only after stripping must not raise.
    assert _slugify("") == ""
