# Step 27c — Concept Pass Improvements for Mixed PL/EN Corpora

> **Goal**: Tighten `graph_service/concepts.py` so it produces real
> cross-document bridges on a mixed Polish/English corpus of long PDFs.
> Today the pass works on hand-written notes but is washed out by PDF
> noise: hyphenated word halves, ALL-CAPS headers, citation tokens,
> Polish inflections.

**Parent**: [step-27-graph-density.md](step-27-graph-density.md)
**Status**: ⬜ Planned

---

## Targeted issues

1. **PDF hyphenation artefacts.** PDFs break words across lines as
   `imple-\nmentation`. After `pdfplumber` the line break is preserved
   and the token becomes two: `imple` and `mentation`. The current
   `_PDF_FRAGMENTS` set catches some, but not all common stems.
2. **Polish inflections.** `model`, `modelu`, `modele`, `modeli`,
   `modelach` should fold to one concept. Today they compete as
   independent terms, fragmenting the TF-IDF signal.
3. **Citation tokens.** PDF reference lists produce hundreds of
   `et`, `al`, `pp`, `vol`, `no`, `ed`, `eds`, `proc`, `acm`, `ieee`
   tokens that survive the length filter and dominate frequencies.
4. **Bigram quality.** The current bigram filter requires both halves
   to be non-stopword and ≥ 4 chars but does not require the bigram
   to appear ≥ 2 times *adjacent* in the same note. Random adjacency
   from running text leaks through.
5. **Per-folder policy too narrow.** The `_CONCEPT_INCLUDE_FOLDERS`
   set excludes notes whose top folder is a slug from Step 27a
   (`knowledge/hai-ai-index-report-2025/...`) — the slug itself
   isn't in the include list. We must check the **first segment** of
   the path correctly (already done) — but verify after Step 27a
   sub-folders are introduced.

## Design

### 1. Hyphenation repair pre-tokenise

Add a pre-processing step in `_tokenise`:

```python
_HYPHEN_BREAK_RE = re.compile(r"(\w+)-\s*\n\s*(\w+)")

def _repair_hyphenation(text: str) -> str:
    return _HYPHEN_BREAK_RE.sub(r"\1\2", text)
```

Apply before the existing tokeniser. Cheap regex, no language model.

### 2. Polish lemma-lite folding

Polish inflections share a stem; cheap rule-based folding handles 80%
of cases without a real lemmatiser:

```python
_PL_SUFFIXES = (
    "ami", "ach", "om", "ów", "em",
    "ego", "emu", "ymi", "ymi",
    "ie", "ej", "ą", "y", "i", "u", "e", "a", "o",
)

def _fold_pl(token: str) -> str:
    """Conservative suffix stripping for tokens detected as Polish."""
    if not token or len(token) <= 4:
        return token
    if not any(ch in token for ch in "ąćęłńóśźż"):
        return token  # only apply to tokens with Polish diacritics
    for suf in _PL_SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 4:
            return token[: -len(suf)]
    return token
```

Apply after lowercase, before stopword filter. Conservative because we
only fold tokens with Polish diacritics, leaving English untouched.

### 3. Expanded stopword sets

Append to `_STOPWORDS_EN`:

```python
{
    # Citation / bibliography artefacts
    "et", "al", "pp", "vol", "no", "ed", "eds", "proc",
    "acm", "ieee", "arxiv", "preprint", "doi", "isbn",
    "appendix", "supplementary", "supp", "supplemental",
    # Page / figure references
    "fig", "figs", "tbl", "tbls", "eq", "eqs",
    # Common adverbs / connectives missed previously
    "however", "therefore", "thus", "hence", "moreover",
    "furthermore", "additionally", "consequently",
}
```

Append to `_STOPWORDS_PL`:

```python
{
    # Common verbs / connectives missed previously
    "może", "można", "należy", "trzeba", "powinien",
    "powinna", "powinno", "musi", "muszą",
    "również", "również", "także", "jeszcze", "tylko",
    "bardzo", "dużo", "mało", "więcej", "mniej",
    # Citation artefacts
    "rys", "tab", "rozdział", "rozdziale", "rozdziału",
}
```

### 4. Adjacency-required bigrams

In `_build_tfidf`, require each bigram to appear adjacently ≥ 2 times
in *the same note*:

```python
bigram_counts: Counter = Counter(
    (a, b) for a, b in _bigrams(tokens)
    if a not in STOPWORDS and b not in STOPWORDS
       and len(a) >= 4 and len(b) >= 4
)
bigrams = [bg for bg, c in bigram_counts.items() if c >= 2]
```

Single-occurrence bigrams are noise; recurring bigrams encode real
multi-word concepts ("language model", "human feedback").

### 5. Tag-overlap dedup hardened

The existing comment notes "Skip a concept whose label IS already a
graph tag". Verify this is enforced after suffix folding — apply the
folding to the comparison key as well, otherwise `model` (concept) and
`modele` (tag) won't match.

### Tests

Add / extend `backend/tests/test_concepts.py`:

1. `test_repair_hyphenation_joins_split_words` — `"imple-\nmentation"`
   tokenises as `implementation`.
2. `test_fold_pl_collapses_inflections` — `"modele"`, `"modeli"`,
   `"modelach"` all fold to a common stem.
3. `test_fold_pl_skips_english_tokens` — `"models"` unchanged.
4. `test_bigrams_require_two_occurrences` — single-occurrence bigram
   is excluded; ≥ 2 occurrences included.
5. `test_citation_stopwords_dropped` — `et`, `al`, `pp`, `arxiv` never
   appear as concept labels.
6. `test_concept_pass_on_mixed_pl_en_synthetic_corpus` — feed three
   synthetic notes (PL, EN, mixed) sharing the topic "language model"
   under varied inflections; assert ≥ 1 shared concept node connects
   all three.

### Acceptance

- After re-ingesting the four reference PDFs, the concept pass emits
  ≥ 30 `about_concept` edges that span at least two different parent
  PDFs (was ~3).
- No concept node has a label in `{et, al, pp, vol, https, www, arxiv,
  fig, tab}`.
- Existing concept-pass tests still pass.

### Out of scope

- Real lemmatisation (Morfologik / Stempel) — adds a heavy dependency
  for marginal recall gain.
- Cross-language concept folding (English ↔ Polish translation) — too
  noisy without a model.
- Phrase extraction beyond bigrams — trigrams add little signal at
  current corpus sizes.
