"""Tests for concept-pass improvements (Step 27c)."""

from services.graph_service.concepts import (
    STOPWORDS,
    _bigrams,
    _build_tfidf,
    _fold_pl,
    _repair_hyphenation,
    _tokenise,
)


# ── Hyphenation repair ──────────────────────────────────────


def test_repair_hyphenation_joins_split_words():
    text = "we use imple-\nmentation details"
    out = _repair_hyphenation(text)
    assert "implementation" in out


def test_repair_hyphenation_with_extra_whitespace():
    text = "lan-  \n  guage model"
    out = _repair_hyphenation(text)
    assert "language" in out


def test_repair_hyphenation_leaves_normal_text_alone():
    text = "no hyphenation here at all"
    assert _repair_hyphenation(text) == text


# ── Polish suffix folding ───────────────────────────────────


def test_fold_pl_skips_english_tokens():
    assert _fold_pl("models") == "models"
    assert _fold_pl("training") == "training"


def test_fold_pl_skips_short_tokens():
    assert _fold_pl("łza") == "łza"  # too short to fold


def test_fold_pl_strips_common_suffix():
    # "modelach" has Polish 'ł' nowhere — but 'ą'/'ł' etc. trigger folding.
    # Use a token that does have a Polish diacritic.
    assert _fold_pl("łańcuchami") != "łańcuchami"
    # The result should be shorter than the input
    assert len(_fold_pl("łańcuchami")) < len("łańcuchami")


def test_fold_pl_consolidates_inflections():
    # All three should collapse to the same stem because they share
    # diacritics-bearing root.
    a = _fold_pl("ścieżkami")
    b = _fold_pl("ścieżkach")
    c = _fold_pl("ścieżką")
    assert a == b == c


# ── Tokenisation pipeline ───────────────────────────────────


def test_tokenise_repairs_hyphens_and_lowercases():
    text = "Imple-\nmentation Details"
    tokens = _tokenise(text)
    assert "implementation" in tokens
    assert "details" in tokens


def test_tokenise_drops_short_tokens():
    text = "ed io am of go"
    tokens = _tokenise(text)
    assert tokens == []  # all below the 4-char minimum


# ── Stopwords ───────────────────────────────────────────────


def test_citation_stopwords_dropped():
    for word in ("arxiv", "preprint", "doi", "isbn", "proc", "appendix"):
        assert word in STOPWORDS, f"{word} should be a stopword"


def test_pl_modal_stopwords_dropped():
    for word in ("może", "można", "należy", "trzeba", "również"):
        assert word in STOPWORDS, f"{word} should be a stopword"


# ── Bigram adjacency requirement ────────────────────────────


def test_single_occurrence_bigram_excluded():
    note_tokens = {
        "note:a": ["transformer", "architecture", "training", "evaluation"],
    }
    tfidf = _build_tfidf(note_tokens)
    # A single-occurrence bigram should not appear in the result.
    assert "transformer architecture" not in tfidf["note:a"]


def test_recurring_bigram_included_when_shared():
    note_tokens = {
        "note:a": ["transformer", "architecture", "again", "transformer", "architecture"],
        "note:b": ["transformer", "architecture", "later", "transformer", "architecture"],
    }
    tfidf = _build_tfidf(note_tokens)
    # Bigram occurs twice in each doc and is shared across both notes,
    # so it should pass df>=2 and adjacency>=2.
    assert "transformer architecture" in tfidf["note:a"]
    assert "transformer architecture" in tfidf["note:b"]


def test_bigram_with_stopword_half_excluded():
    note_tokens = {
        "note:a": ["the", "transformer", "the", "transformer"],
        "note:b": ["the", "transformer", "the", "transformer"],
    }
    tfidf = _build_tfidf(note_tokens)
    # "the" is a stopword and should make ("the", "transformer") fail the filter.
    assert "the transformer" not in tfidf["note:a"]


def test_bigrams_helper_generates_adjacent_pairs():
    pairs = _bigrams(["a", "b", "c"])
    assert pairs == [("a", "b"), ("b", "c")]


# ── End-to-end on synthetic mixed corpus ────────────────────


def test_mixed_pl_en_corpus_finds_shared_concept():
    """Three notes sharing a recurring bigram about a topic should
    surface that bigram as a TF-IDF term in all three."""
    note_tokens = {
        "note:en1": [
            "transformer", "architecture", "summary",
            "transformer", "architecture", "training",
            "transformer", "architecture", "evaluation",
        ],
        "note:en2": [
            "large", "transformer", "architecture",
            "transformer", "architecture", "fine",
            "transformer", "architecture", "tuning",
        ],
        "note:pl1": [
            "transformer", "architecture", "polski",
            "transformer", "architecture", "uczenie",
            "transformer", "architecture", "ewaluacja",
        ],
    }
    tfidf = _build_tfidf(note_tokens)
    for nid in ("note:en1", "note:en2", "note:pl1"):
        assert "transformer architecture" in tfidf[nid], (
            f"Expected shared bigram in {nid}, got {sorted(tfidf[nid])}"
        )
