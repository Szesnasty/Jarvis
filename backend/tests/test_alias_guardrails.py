"""Tests for alias guardrails and weak_aliases — Step 26b."""

from __future__ import annotations

import pytest

from services.alias_index import (
    _phrase_passes_guardrails,
    upsert_note_aliases,
    scan_body,
    normalise_phrase,
)


# ---------------------------------------------------------------------------
# _phrase_passes_guardrails
# ---------------------------------------------------------------------------

class TestPhraseGuardrails:
    def test_too_short_rejected(self, tmp_path):
        assert not _phrase_passes_guardrails("ab")

    def test_exactly_min_length_accepted(self):
        assert _phrase_passes_guardrails("test")  # 4 chars

    def test_allowlist_jwt_accepted(self):
        assert _phrase_passes_guardrails("jwt")

    def test_allowlist_aws_accepted(self):
        assert _phrase_passes_guardrails("aws")

    def test_stopword_ai_rejected(self):
        assert not _phrase_passes_guardrails("ai")

    def test_stopword_memory_rejected(self):
        assert not _phrase_passes_guardrails("memory")

    def test_stopword_only_phrase_rejected(self):
        # Both tokens are stopwords
        assert not _phrase_passes_guardrails("data model")

    def test_mixed_phrase_accepted(self):
        # "AI" is stopword but "assistant" is content word
        assert _phrase_passes_guardrails("ai assistant")

    def test_all_stopwords_multi_rejected(self):
        assert not _phrase_passes_guardrails("ai api")

    def test_long_phrase_accepted(self):
        assert _phrase_passes_guardrails("hybrid retrieval pipeline")


# ---------------------------------------------------------------------------
# upsert_note_aliases — guardrail enforcement via DB
# ---------------------------------------------------------------------------

@pytest.fixture
def db(tmp_path):
    return tmp_path / "app" / "jarvis.db"


def test_short_phrase_not_indexed(db):
    written = upsert_note_aliases(db, "notes/a.md", title="AB", aliases=[])
    # "ab" is 2 chars — should be dropped
    rows = _read_all(db)
    assert not any(r[0] == "ab" for r in rows)


def test_allowlist_jwt_indexed(db):
    written = upsert_note_aliases(db, "notes/j.md", title="JWT", aliases=[])
    rows = _read_all(db)
    assert any(r[0] == "jwt" for r in rows)


def test_stopword_ai_not_indexed(db):
    upsert_note_aliases(db, "notes/ai.md", title="AI", aliases=[])
    rows = _read_all(db)
    assert not any(r[0] == "ai" for r in rows)


def test_stopword_memory_not_indexed(db):
    upsert_note_aliases(db, "notes/mem.md", title="memory", aliases=[])
    rows = _read_all(db)
    assert not any(r[0] == "memory" for r in rows)


def test_ai_assistant_indexed(db):
    upsert_note_aliases(db, "notes/assist.md", title="AI assistant", aliases=[])
    rows = _read_all(db)
    assert any("ai assistant" in r[0] for r in rows)


def test_data_model_two_stopwords_not_indexed(db):
    upsert_note_aliases(db, "notes/dm.md", title="data model", aliases=[])
    rows = _read_all(db)
    assert not any(r[0] == "data model" for r in rows)


def test_frequency_cap_blocks_11th_note(db):
    """11th note trying to index the same phrase should be blocked."""
    phrase = "retrieval pipeline"
    for i in range(10):
        upsert_note_aliases(db, f"notes/n{i}.md", title=phrase, aliases=[])

    # 11th note
    upsert_note_aliases(db, "notes/n10.md", title=phrase, aliases=[])
    rows = _read_all(db)
    paths_with_phrase = [r[1] for r in rows if r[0] == normalise_phrase(phrase)]
    assert "notes/n10.md" not in paths_with_phrase


def test_frequency_cap_confirmed_before_insert(db):
    """After blocking, the DB state must not contain the blocked note's phrase."""
    phrase = "shared topic"
    for i in range(10):
        upsert_note_aliases(db, f"notes/s{i}.md", title=phrase, aliases=[])

    upsert_note_aliases(db, "notes/blocked.md", title=phrase, aliases=[])
    rows = _read_all(db)
    # Confirm the blocked note never appears for this phrase
    for row in rows:
        if row[0] == normalise_phrase(phrase):
            assert row[1] != "notes/blocked.md"


# ---------------------------------------------------------------------------
# weak_aliases indexing
# ---------------------------------------------------------------------------

def test_weak_alias_indexed_with_correct_kind(db):
    upsert_note_aliases(
        db, "notes/w.md",
        title="Knowledge graph",
        aliases=[],
        weak_aliases=["retrieval"],
    )
    rows = _read_all(db)
    weak_rows = [r for r in rows if r[2] == "weak_alias"]
    assert any(r[0] == "retrieval" for r in weak_rows)


def test_weak_alias_stopword_not_indexed(db):
    upsert_note_aliases(
        db, "notes/ws.md",
        title="Knowledge base",
        aliases=[],
        weak_aliases=["ai"],  # stopword — should be blocked by guardrails
    )
    rows = _read_all(db)
    assert not any(r[0] == "ai" for r in rows)


# ---------------------------------------------------------------------------
# weak_alias does not produce a standalone suggestion
# ---------------------------------------------------------------------------

def test_weak_alias_alone_no_suggestion(tmp_path):
    """A weak_alias hit in isolation must not emit a SuggestedLink."""
    from services.connection_service import (
        _alias_signal,
        _merge_candidates,
    )
    import sqlite3

    db = tmp_path / "app" / "jarvis.db"
    (tmp_path / "app").mkdir(parents=True, exist_ok=True)
    upsert_note_aliases(
        db, "notes/target.md",
        title="Target Note",
        aliases=[],
        weak_aliases=["retrieval"],
    )

    # A note that mentions "retrieval" in its body
    alias_scores, matched = _alias_signal.__wrapped__("notes/source.md", {}, "retrieval pipeline", tmp_path) \
        if hasattr(_alias_signal, "__wrapped__") else ({}, [])

    # Direct test via _merge_candidates: only alias signal fires, score 0.35
    result = _merge_candidates(
        bm25_scores={},
        note_emb_scores={},
        chunk_emb_scores={},
        alias_scores={"notes/target.md": (0.35, "retrieval")},
        mode="aggressive",  # even in aggressive mode, weak-alias alone is blocked
    )
    assert not any(item[0] == "notes/target.md" for item in result)


def test_weak_alias_plus_bm25_produces_suggestion():
    """weak_alias + bm25 together should emit a SuggestedLink."""
    from services.connection_service import _merge_candidates

    result = _merge_candidates(
        bm25_scores={"notes/target.md": 0.8},
        note_emb_scores={},
        chunk_emb_scores={},
        alias_scores={"notes/target.md": (0.35, "retrieval")},
        mode="fast",
    )
    assert any(item[0] == "notes/target.md" for item in result)


def test_weak_alias_contribution_less_than_strong():
    """weak_alias (0.35) should produce lower score than strong alias (1.0) with same other signals."""
    from services.connection_service import score_candidate

    weak = score_candidate(bm25=0.5, alias=0.35)
    strong = score_candidate(bm25=0.5, alias=1.0)
    assert weak < strong


def test_weak_alias_alone_cannot_reach_strong_tier():
    """A candidate driven only by weak_alias can never reach 'strong' tier."""
    from services.connection_service import _merge_candidates, SCORE_STRONG

    result = _merge_candidates(
        bm25_scores={},
        note_emb_scores={},
        chunk_emb_scores={},
        alias_scores={"notes/t.md": (0.35, "x")},
        mode="aggressive",
    )
    # Should be empty (weak alone is blocked) or if somehow included, not strong
    for item in result:
        if item[0] == "notes/t.md":
            assert item[4] != "strong"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_all(db):
    import sqlite3
    if not db.exists():
        return []
    with sqlite3.connect(str(db)) as conn:
        return conn.execute("SELECT phrase_norm, note_path, kind FROM alias_index").fetchall()
