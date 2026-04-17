# Step 22f — Jira-Aware Hybrid Retrieval

> **Goal**: Teach the retrieval pipeline to treat issues as a first-class
> signal — with facets (status / sprint / assignee / risk / business
> area), structured boosts, and context shaping that presents issues
> differently from notes. Reuse the existing three-signal fusion
> (BM25 + cosine + graph) without breaking the current ranking for
> non-Jira workspaces.

**Status**: ⬜ Not started
**Depends on**: 22b, 22c, 22d, 22e, step-19c (hybrid retrieval),
step-20e (retrieval rebalance)
**Effort**: ~3 days

---

## New retrieval inputs

On top of the existing BM25 + cosine + graph signals, retrieval gains
two additive signals:

1. **Enrichment match** — when the query entails a facet value, issues
   matching that facet get a boost.
2. **Facet filter** — an optional hard filter derived from parsed query
   intent or explicit UI filters.

Total weight budget stays at 1.0:

```
baseline:  bm25 0.25, cosine 0.40, graph 0.35
jira-aware: bm25 0.22, cosine 0.33, graph 0.30, enrichment 0.15
```

The `enrichment` weight is active only when the query produces at least
one facet hit; otherwise its mass redistributes proportionally.

---

## Query intent parsing

A small, deterministic parser runs before retrieval and produces a
`QueryIntent`:

```python
@dataclass
class QueryIntent:
    text: str
    facets: FacetFilter           # structured facets (possibly empty)
    wants_issues_only: bool       # "tasks", "tickets", "sprint", etc.
    wants_open_only: bool
    sprint_filter: Optional[str]  # explicit or "this sprint" → active sprint
    assignee_filter: Optional[str]
    business_area_hint: Optional[str]   # from enum keyword in text
    risk_hint: Optional[str]             # "risky", "blockers", "critical"
    keys_in_query: List[str]      # e.g. "ONB-142"
```

Parser is pattern-based (no LLM). It understands:

- Explicit Jira keys anywhere in the query → hard inclusion filter
  (those issues appear in the top-3 of the result even if BM25 misses).
- Status words: `open / closed / done / in progress` → map to
  `status_category`.
- *"this sprint"* / *"current sprint"* → the `sprint_state="active"` set.
- Business-area keywords matching the enrichment enum.
- Words from a curated list (`blockers`, `risky`, `critical`,
  `uncertain`, `unclear`) → risk / ambiguity hints.

All rules are configurable per workspace; defaults ship in
`services/retrieval/intent_rules.py`.

---

## Facet filter

```python
@dataclass
class FacetFilter:
    status_category: Optional[List[str]] = None
    sprint_state:    Optional[List[str]] = None
    sprint_name:     Optional[List[str]] = None
    assignee:        Optional[List[str]] = None
    project_key:     Optional[List[str]] = None
    business_area:   Optional[List[str]] = None
    risk_level:      Optional[List[str]] = None
    ambiguity_level: Optional[List[str]] = None
    work_type:       Optional[List[str]] = None
```

Applied as a SQL pre-filter on the issue candidate set before fusion.
Notes and other subjects are unaffected unless `wants_issues_only=True`,
in which case non-issue candidates are excluded entirely.

---

## Signal details

### Enrichment match signal

For a candidate `C`:

```
if C.subject_type != "jira_issue": return 0.0
score = 0.0
if intent.business_area_hint and C.enrichment.business_area == intent.business_area_hint:
    score += 0.5
if intent.risk_hint == "high-risk" and C.enrichment.risk_level == "high":
    score += 0.3
if "unclear" in intent.keywords and C.enrichment.ambiguity_level == "unclear":
    score += 0.2
return clip01(score)
```

### Boosts (not part of fused weight; applied as +ε after fusion)

- Explicit key mentioned in query → +0.30.
- Candidate is the direct target of a `blocks`/`depends_on` edge from a
  recently-viewed issue → +0.10 (short-term "working set" boost,
  session-scoped).
- Candidate is a sprint `active` member and intent mentions sprint → +0.05.

Hard cap: total boost ≤ 0.4 so pure-lexical wins never vanish.

---

## Context shaping for the LLM

Today context is a concatenation of note excerpts. After this step the
builder produces **sections** so Claude sees structure:

```
<context>
  <issues>                      <!-- only if present -->
    <issue key="ONB-142" status="In Progress" risk="high" area="onboarding">
      <title>Session expires during onboarding wizard</title>
      <summary>{enrichment.summary}</summary>
      <top-snippet>{best matching chunk}</top-snippet>
      <blocked-by>[AUTH-88]</blocked-by>
      <blocks>[ONB-150]</blocks>
      <source>jira</source>
    </issue>
    ...
  </issues>

  <decisions>...</decisions>
  <notes>...</notes>
</context>
```

Token budget split:

- 40 % to issues (if any).
- 30 % to decisions.
- 30 % to notes / PDFs / URLs.

If no issues in the result set, the budget rolls over to notes.

Enrichment `summary` and `actionable_next_step` are included *instead of*
raw description when available — saves tokens, keeps fidelity.

---

## API changes

```
POST /api/retrieval/search
  body: { query, top_k?, facets?, include?, exclude? }
  → { results: [...], signals: {...}, intent: {...}, debug?: {...} }
```

New query params mirror `FacetFilter`. `intent` echoes back the parsed
intent so the UI can show facet chips ("filter applied: status=open").

---

## UX hooks (backend-only now; UI in later step)

- Return a `facets_available` block listing unique values in the result
  set (so the UI can render Jira-Navigator-style filter chips).
- Return a `related_issues` block pre-computed from the graph (top-5
  neighbours of the best hit) — skips a second round trip.

---

## Tests

- `test_intent_parser_key`: `"what blocks ONB-142?"` → `keys_in_query=["ONB-142"]`, `wants_issues_only=True`.
- `test_intent_parser_sprint`: `"what's risky this sprint?"` → `sprint_state=["active"]`, `risk_hint="high-risk"`.
- `test_enrichment_signal_gated`: non-issue candidate gets zero enrichment signal.
- `test_boost_cap`: stacking boosts never exceeds +0.4.
- `test_context_sections`: issues, decisions, notes appear in separate
  XML sections with correct token budgets.
- `test_backcompat_no_issues`: workspace without Jira data produces the
  same results as today (regression guard).
- `test_filter_reduces_candidates`: `facets.status_category=["open"]`
  eliminates closed issues from candidate pool before fusion.

---

## Eval

Extend step-20f eval set with 30 Jira-labelled queries. Track:

- Recall@10 with and without this step enabled.
- Precision@5 on "blocker / related / duplicate" labelled pairs.
- p95 latency (must stay within +50 ms of baseline).

`JARVIS_FEATURE_JIRA_RETRIEVAL=1` gates the new path so we can A/B run.

---

## Definition of done

- Queries about tasks, blockers, sprints and risks return the right
  issues with the correct structured context.
- Non-Jira workspaces see no behaviour change.
- Eval numbers published in `docs/features/jira-retrieval.md`.
