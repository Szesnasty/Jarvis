"""Concept extraction pass: TF-IDF-derived topical bridges.

Personal notes can share people via mentions, and reference papers can
share authors — but the highest-signal connection between two long-form
documents is **shared topic**: two papers about LLMs both talking about
"reinforcement learning from human feedback" should connect, even when
they share no co-authors.

This pass mines unigrams + bigrams across all note bodies, scores them
with TF-IDF, and emits the top-K most distinctive terms per note as
``concept:`` nodes with ``about_concept`` edges. Concepts shared across
notes become real graph bridges that retrieval and the chat layer can
walk.

Design constraints
------------------
* No external dependencies (no sklearn) — small handwritten TF-IDF.
* Pure additive: produces edges only; never deletes other passes' work.
* All edges carry ``origin="concept"`` so :meth:`Graph.remove_edges_by_origin`
  cleans them on rebuild.
* Run ONCE per rebuild after frontmatter+entity passes have populated
  the graph; results land in ``graph.json`` like everything else.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Tuple

from utils.markdown import parse_frontmatter

from services.graph_service.models import Edge, Graph

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Tokenisation                                                                 #
# --------------------------------------------------------------------------- #

# Strict alphabetic tokeniser — drops numbers, punctuation, Markdown syntax.
# Polish/English diacritics retained so terms like "łańcuch" don't collapse.
# Min length 4: drops common PDF line-break artifacts ("pre", "ing", "tion",
# "ed", "ble") that are hyphenated word halves rather than real terms.
_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-ÞĄĆĘŁŃÓŚŹŻẞßà-öø-ÿąćęłńóśźż]{4,30}")

# Word fragments that survive the length filter but are clearly broken
# halves of hyphenated words from PDF text extraction.
_PDF_FRAGMENTS: FrozenSet[str] = frozenset({
    "tion", "tions", "ment", "ments", "ness", "ence", "ance",
    "able", "ible", "ical", "ious", "ative", "ivity",
    "ize", "ized", "ization", "ising",
    "https", "http", "www", "com", "org", "edu", "arxiv",
})

# Stopwords we never want as concept anchors.
_STOPWORDS_EN: FrozenSet[str] = frozenset({
    "the", "and", "that", "this", "these", "those", "with", "from", "into",
    "have", "has", "had", "been", "were", "are", "was", "will", "would",
    "could", "should", "may", "might", "must", "can", "shall", "does",
    "did", "doing", "done", "having", "being", "such", "than", "then",
    "they", "them", "their", "theirs", "there", "here", "where", "when",
    "what", "which", "while", "whose", "whom", "about", "above", "after",
    "again", "all", "also", "another", "any", "anyway", "as", "at", "back",
    "because", "become", "becomes", "been", "before", "between", "both",
    "but", "by", "down", "during", "each", "etc", "even", "every", "for",
    "however", "if", "in", "is", "it", "its", "itself", "just", "like",
    "made", "make", "many", "more", "most", "much", "must", "no", "not",
    "now", "of", "off", "on", "once", "one", "only", "or", "other", "others",
    "our", "ours", "out", "over", "own", "per", "rather", "so", "some",
    "still", "such", "thus", "to", "too", "two", "under", "until", "up",
    "upon", "us", "use", "used", "uses", "using", "very", "via", "way",
    "we", "well", "without", "yes", "you", "your",
    # Common paper / Markdown structural words
    "abstract", "introduction", "background", "discussion", "conclusion",
    "appendix", "figure", "table", "section", "chapter", "page", "paper",
    "papers", "show", "shows", "shown", "example", "examples", "based",
    "above", "below", "thus", "however", "therefore", "moreover", "since",
    "given", "however", "thus", "therefore", "moreover", "result", "results",
    "method", "methods", "approach", "approaches", "model", "models",
    "study", "studies", "work", "works", "various", "different", "several",
    "general", "specific", "particular", "different", "important", "high",
    "low", "large", "small", "good", "better", "best", "first", "second",
    "third", "next", "previous", "current", "new", "old", "recent",
    "non", "also", "additional", "across", "among", "within", "without",
    "set", "sets", "form", "forms", "type", "types", "level", "levels",
    "kind", "kinds", "case", "cases", "term", "terms", "issue", "issues",
    "task", "tasks", "step", "steps", "process", "processes", "main",
    "side", "sides", "part", "parts", "whole", "full", "total", "single",
    "multi", "multiple", "various", "varied", "data", "value", "values",
    "score", "scores", "rate", "rates", "test", "tests", "tested", "input",
    "output", "inputs", "outputs", "training", "trained", "learn", "learned",
    "learning", "lower", "upper", "left", "right", "top", "bottom",
    "show", "shows", "shown", "see", "fig", "section", "table", "tables",
    "let", "lets", "say", "says", "said", "called", "name", "names",
    "called", "include", "includes", "included", "including",
    "report", "reports", "reported", "reporting", "consider", "considered",
    "given", "give", "gives", "found", "find", "finds", "find",
    "make", "makes", "made", "making", "want", "wants", "wanted",
    "need", "needs", "needed", "needing", "year", "years", "today",
    "discuss", "discusses", "discussed",
    # AI/ML uberterms — too generic to be useful as concepts
    "ai", "ml", "nlp", "dl", "rl", "language", "intelligence", "neural",
    "machine",
    # Step 27c — citation / bibliography artefacts that survive tokenisation
    # of PDF reference lists and otherwise dominate TF-IDF.
    "arxiv", "preprint", "doi", "isbn", "proc", "proceedings", "conf",
    "acm", "ieee", "springer", "elsevier",
    "appendix", "supplementary", "supp", "supplemental",
    "fig", "figs", "tbl", "tbls", "eq", "eqs", "ref", "refs",
    # Step 27c — connectives that survive the length filter (5+ chars)
    "hence", "furthermore", "additionally", "consequently", "meanwhile",
    "otherwise", "likewise", "nevertheless", "nonetheless",
})

_STOPWORDS_PL: FrozenSet[str] = frozenset({
    "oraz", "jest", "być", "był", "była", "było", "były", "ich", "jego",
    "jej", "ich", "tym", "tej", "tym", "tej", "tego", "temu", "tymi",
    "który", "która", "które", "którzy", "którego", "której", "którym",
    "jak", "ale", "lub", "czy", "tak", "nie", "się", "nas", "nam", "ja",
    "ty", "on", "ona", "ono", "my", "wy", "oni", "one", "więc", "potem",
    "tutaj", "teraz", "wtedy", "kiedy", "gdzie", "dlaczego", "kto", "co",
    "który", "które", "który", "tych", "tymi", "tymi", "tymi", "po", "do",
    "od", "ze", "za", "na", "we", "przy", "pod", "nad", "bez", "obok",
    "według", "podczas", "przez", "wobec", "zamiast", "wzdłuż",
    # Step 27c — modal verbs and connectives missed previously
    "może", "można", "należy", "trzeba", "powinien",
    "powinna", "powinno", "musi", "muszą",
    "również", "także", "jeszcze", "tylko",
    "bardzo", "dużo", "mało", "więcej", "mniej",
    "rozdział", "rozdziale", "rozdziału", "rys", "tab",
})

STOPWORDS = _STOPWORDS_EN | _STOPWORDS_PL | _PDF_FRAGMENTS


# Step 27c — PDF text extractors preserve hyphenated line breaks
# (e.g. ``imple-\nmentation``). Stitch them back together before
# tokenising so the resulting term competes with non-broken occurrences.
_HYPHEN_BREAK_RE = re.compile(r"(\w+)-\s*\n\s*(\w+)")


def _repair_hyphenation(text: str) -> str:
    """Join words split across lines by PDF text extractors."""
    return _HYPHEN_BREAK_RE.sub(r"\1\2", text)


# Step 27c — conservative Polish suffix folding. Only applied to tokens
# that contain at least one Polish diacritic, so English (``models``,
# ``modeling``) is untouched. This is not a real lemmatiser — it covers
# the ~80 % case where simple suffix stripping consolidates ``modele``,
# ``modeli``, ``modelach`` to one stem and is good enough to make TF-IDF
# stop fragmenting the same concept across inflected forms.
_PL_DIACRITICS = frozenset("ąćęłńóśźż")
_PL_SUFFIXES: Tuple[str, ...] = (
    "ami", "ach", "ego", "emu", "ymi", "imi", "om", "ów", "em",
    "ie", "ej", "ą", "ę", "y", "i", "u", "e", "a", "o",
)


def _fold_pl(token: str) -> str:
    """Strip a common Polish suffix when the token contains diacritics."""
    if len(token) <= 4:
        return token
    if not any(ch in token for ch in _PL_DIACRITICS):
        return token
    for suf in _PL_SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 4:
            return token[: -len(suf)]
    return token


def _tokenise(text: str) -> List[str]:
    """Return lowercase tokens passing the alpha+length filters.

    Step 27c — hyphenation is repaired before tokenisation, and
    Polish-diacritic tokens are folded to a common stem.
    """
    repaired = _repair_hyphenation(text)
    return [_fold_pl(m.group(0).lower()) for m in _TOKEN_RE.finditer(repaired)]


def _bigrams(tokens: List[str]) -> List[Tuple[str, str]]:
    """Adjacent-token bigrams. Used for compound-concept candidates."""
    return list(zip(tokens, tokens[1:]))


# Bigrams encode more meaning per token than unigrams ("language model" vs
# "language" + "model"). Boost their TF-IDF score so they compete fairly
# with the much-more-frequent unigrams.
_BIGRAM_BOOST = 2.5


# --------------------------------------------------------------------------- #
# TF-IDF                                                                       #
# --------------------------------------------------------------------------- #


def _build_tfidf(
    note_tokens: Dict[str, List[str]],
) -> Dict[str, Dict[str, float]]:
    """Per-note TF-IDF for unigrams + bigrams. Stopwords removed.

    Returns ``{note_id: {term: tfidf, ...}, ...}``. Term keys are
    space-joined (``"language model"``) for bigrams or single words.
    """
    n_docs = max(len(note_tokens), 1)
    df: Counter = Counter()
    note_terms: Dict[str, Counter] = {}

    for note_id, tokens in note_tokens.items():
        # Unigrams
        unigrams = [t for t in tokens if t not in STOPWORDS]
        # Bigrams — step 27c: require adjacent occurrence ≥ 2 times in the
        # same note. Single-occurrence bigrams from running prose are
        # noise; recurring bigrams encode real multi-word concepts
        # ("language model", "human feedback").
        bigram_counts: Counter = Counter()
        for a, b in _bigrams(tokens):
            if (
                a not in STOPWORDS
                and b not in STOPWORDS
                and len(a) >= 4
                and len(b) >= 4
            ):
                bigram_counts[(a, b)] += 1
        bigrams = [bg for bg, c in bigram_counts.items() if c >= 2]
        terms_in_doc: Counter = Counter()
        terms_in_doc.update(unigrams)
        # Bigram TF uses the actual within-doc frequency, not 1.
        for bg in bigrams:
            terms_in_doc[f"{bg[0]} {bg[1]}"] = bigram_counts[bg]
        note_terms[note_id] = terms_in_doc
        # Per-doc presence
        for term in terms_in_doc:
            df[term] += 1

    # Upper bound for "ubiquitous term" filtering. The 0.6×N rule from
    # large-corpus IR doesn't make sense when there are only a handful of
    # docs — a term shared by 2 of 2 notes IS the bridge we want, not a
    # stopword. Disable max-df entirely below 5 docs; relax to 0.8×N up
    # to ~30 docs; tighten to 0.6×N afterwards.
    if n_docs < 5:
        max_df = n_docs + 1
    elif n_docs < 30:
        max_df = max(int(0.8 * n_docs), n_docs - 1)
    else:
        max_df = max(int(0.6 * n_docs), 5)

    tfidf: Dict[str, Dict[str, float]] = {}
    for note_id, term_counts in note_terms.items():
        total = sum(term_counts.values()) or 1
        scores: Dict[str, float] = {}
        for term, count in term_counts.items():
            doc_freq = df[term]
            if doc_freq < 2 or doc_freq > max_df:
                continue  # only-here terms (no bridging) + ubiquitous stopword-likes
            tf = count / total
            idf = math.log((n_docs + 1) / (doc_freq + 1)) + 1
            score = tf * idf
            if " " in term:
                score *= _BIGRAM_BOOST
            scores[term] = score
        tfidf[note_id] = scores
    return tfidf


# --------------------------------------------------------------------------- #
# Per-folder policy                                                            #
# --------------------------------------------------------------------------- #


# Folders where concept extraction adds value (rich prose). Conversation
# transcripts and inbox quick captures are too short / off-topic to feed
# into corpus-level statistics meaningfully.
_CONCEPT_INCLUDE_FOLDERS = frozenset({
    "knowledge", "projects", "areas", "summaries", "preferences", "examples",
})


def _should_extract_concepts(rel_path: str, fm: Dict, body_token_count: int) -> bool:
    """Per-note opt-in/out for the concept pass."""
    explicit = fm.get("extract_concepts")
    if explicit is False:
        return False
    if explicit is True:
        return True
    folder = rel_path.split("/", 1)[0] if "/" in rel_path else ""
    if folder not in _CONCEPT_INCLUDE_FOLDERS:
        return False
    # Below this token count there's no statistical mass to mine from
    return body_token_count >= 60


# --------------------------------------------------------------------------- #
# Public entry point                                                           #
# --------------------------------------------------------------------------- #


CONCEPT_NODE_TYPE = "concept"
CONCEPT_EDGE_TYPE = "about_concept"
ABOUT_CONCEPT_BASE_WEIGHT = 0.6
# Top-K per note. Tuned to surface enough overlap in a small corpus
# (2–10 notes) without flooding the graph in a 100+ note corpus. The
# orphan-pruning step at the end removes single-note concepts so a
# slightly generous K is safe.
TOP_K_PER_NOTE = 15
# Skip a concept whose label IS already a graph tag — the tag edge already
# covers the same connection and a separate concept node duplicates it.
def _existing_tag_labels(graph: Graph) -> set:
    return {n.label.lower() for n in graph.nodes.values() if n.type == "tag"}


def rebuild_concept_edges(
    workspace_path: Path,
    graph: Graph,
    memory_path: Optional[Path] = None,
) -> int:
    """Mine TF-IDF concepts across the corpus and add concept nodes/edges.

    Mutates ``graph`` in place. Removes any existing concept-pass edges
    (origin == "concept") before re-emitting so the pass is idempotent.

    Returns the number of edges added.
    """
    mem = memory_path or (workspace_path / "memory")
    if not mem.exists():
        return 0

    # Drop previous concept-pass artifacts first
    graph.remove_edges_by_origin("concept")
    # Remove orphaned concept nodes left over from previous runs (no remaining
    # edges touching them after the line above).
    referenced = set()
    for e in graph.edges:
        referenced.add(e.source)
        referenced.add(e.target)
    for nid in [n.id for n in graph.nodes.values() if n.type == CONCEPT_NODE_TYPE]:
        if nid not in referenced:
            graph.nodes.pop(nid, None)

    # Collect tokenised bodies for each note that opts in
    note_tokens: Dict[str, List[str]] = {}
    note_metadata: Dict[str, Dict] = {}
    note_nodes = [n for n in graph.nodes.values() if n.type == "note"]

    for node in note_nodes:
        rel_path = node.id[5:]
        filepath = mem / rel_path
        if not filepath.exists():
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
            fm, body = parse_frontmatter(content)
        except Exception:
            continue
        tokens = _tokenise(body)
        if not _should_extract_concepts(rel_path, fm, len(tokens)):
            continue
        note_tokens[node.id] = tokens
        note_metadata[node.id] = fm

    if len(note_tokens) < 2:
        # TF-IDF needs at least two documents to have any IDF signal worth using
        logger.info("Concept pass skipped: only %d eligible notes", len(note_tokens))
        return 0

    tfidf = _build_tfidf(note_tokens)
    tag_labels = _existing_tag_labels(graph)

    edges_added = 0
    for note_id, scores in tfidf.items():
        if not scores:
            continue
        ranked = sorted(scores.items(), key=lambda x: -x[1])
        kept = 0
        for term, score in ranked:
            if kept >= TOP_K_PER_NOTE:
                break
            if term in tag_labels:
                continue  # already a tag edge
            concept_id = f"{CONCEPT_NODE_TYPE}:{term}"
            graph.add_node(concept_id, CONCEPT_NODE_TYPE, term)
            # Score is unbounded; squash to [0.4, 0.95] so it sits between
            # mentions (0.8) and similar_to (variable). The relative ordering
            # within a note is preserved.
            weight = round(min(0.95, ABOUT_CONCEPT_BASE_WEIGHT + min(score, 0.4)), 3)
            graph.edges.append(Edge(
                source=note_id,
                target=concept_id,
                type=CONCEPT_EDGE_TYPE,
                weight=weight,
                origin="concept",
            ))
            edges_added += 1
            kept += 1

    if edges_added:
        # Drop low-bridging concepts: a concept that touches only one note
        # adds no graph value (it's already represented by the note's
        # frontmatter / similar_to neighbours). Sweep these in a final pass.
        #
        # Exception: very small corpora (< 5 eligible notes) are dominated
        # by single-note concepts because there's not enough cross-doc mass
        # for shared terms to dominate. Pruning everything leaves the graph
        # naked. For those workspaces we keep the top concepts per note as
        # standalone topical anchors so the user sees the topical landscape.
        small_corpus = len(note_tokens) < 5
        min_degree = 1 if small_corpus else 2
        concept_degree: Counter = Counter()
        for e in graph.edges:
            if e.type != CONCEPT_EDGE_TYPE:
                continue
            cid = e.target if e.target.startswith(f"{CONCEPT_NODE_TYPE}:") else e.source
            concept_degree[cid] += 1
        orphan_concepts = {cid for cid, deg in concept_degree.items() if deg < min_degree}
        if orphan_concepts:
            kept_edges: List[Edge] = []
            for e in graph.edges:
                if e.type == CONCEPT_EDGE_TYPE and (
                    e.source in orphan_concepts or e.target in orphan_concepts
                ):
                    continue
                kept_edges.append(e)
            removed = len(graph.edges) - len(kept_edges)
            graph.edges = kept_edges
            for cid in orphan_concepts:
                graph.nodes.pop(cid, None)
            edges_added -= removed
            logger.info(
                "Concept pass: pruned %d single-note concepts (no bridging value)",
                len(orphan_concepts),
            )

    logger.info(
        "Concept pass: %d about_concept edges across %d notes",
        edges_added, len(note_tokens),
    )
    return edges_added
