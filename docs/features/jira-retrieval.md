---
title: Jira-Aware Hybrid Retrieval
status: active
type: feature
sources:
  - backend/services/retrieval/__init__.py
  - backend/services/retrieval/pipeline.py
  - backend/services/retrieval/intent.py
  - backend/services/retrieval/intent_parser.py
  - backend/routers/retrieval_search.py
  - backend/services/context_builder.py
depends_on: [retrieval, enrichment, knowledge-graph]
last_reviewed: 2025-07-27
last_updated: 2025-07-27
---

# Jira-Aware Hybrid Retrieval

## Summary

Step 22f extends the hybrid retrieval pipeline with Jira-aware capabilities: a deterministic query intent parser, enrichment-based scoring (4th signal), post-fusion boosts for explicit issue keys, facet pre-filtering, and structured context shaping that presents issues in XML sections separate from notes and decisions. Feature-gated via `JARVIS_FEATURE_JIRA_RETRIEVAL=1`.

## How It Works

### Query Intent Parsing

`intent_parser.parse_intent(query)` is a pattern-based (no LLM) parser that extracts structured signals:

- **Issue keys**: regex `[A-Z]{2,10}-\d{1,6}` — e.g. `ONB-142`, `AUTH-88`
- **Status words**: maps `open/closed/done/in progress` → `status_category` values
- **Sprint references**: `"this sprint" / "current sprint"` → `sprint_filter="active"`
- **Business area keywords**: matches against `DEFAULT_BUSINESS_AREAS` enum
- **Risk/ambiguity hints**: curated word lists (`blockers`, `risky`, `critical`, `unclear`)
- **Assignee**: `"assigned to X"` pattern
- **Issue intent**: words like `task`, `ticket`, `bug`, `sprint` → `wants_issues_only`

Returns a `QueryIntent` dataclass with a `FacetFilter` for hard filtering and soft hints for scoring.

### Enrichment Match Signal (4th signal)

When active (Jira retrieval enabled + query has Jira signals + enrichments exist), a 4th signal joins the weighted fusion:

| Condition | Score |
|-----------|-------|
| Business area matches intent hint | +0.5 |
| Risk level matches "high-risk" hint | +0.3 |
| Ambiguity matches "unclear" hint | +0.2 |

Weights shift from `bm25=0.25, cosine=0.40, graph=0.35` to `bm25=0.22, cosine=0.33, graph=0.30, enrichment=0.15`.

### Post-Fusion Boosts

Applied additively after fusion, capped at 0.40:

| Boost | Value |
|-------|-------|
| Explicit key in query | +0.30 |
| Sprint active member + sprint intent | +0.05 |

### Facet Pre-Filtering

`FacetFilter` fields (status_category, sprint_state, assignee, project_key, etc.) are applied as hard filters on issue candidates before fusion. Non-issue candidates always pass through unless `wants_issues_only=True`.

### Structured Context Sections

When enabled, `context_builder.py` groups results into XML sections:

```xml
<context>
  <issues>
    <issue key="ONB-142" status="In Progress" risk="high" area="onboarding">
      <title>...</title>
      <summary>{enrichment summary}</summary>
      <top-snippet>{best chunk}</top-snippet>
      <next-step>{enrichment actionable_next_step}</next-step>
      <source>jira</source>
    </issue>
  </issues>
  <decisions>...</decisions>
  <notes>...</notes>
</context>
```

Token budget: issues 40%, decisions 30%, notes 30%. Unused budget rolls over.

## Key Files

| File | Purpose |
|------|---------|
| `backend/services/retrieval/__init__.py` | Package init, re-exports `retrieve()` and `retrieve_with_intent()` |
| `backend/services/retrieval/pipeline.py` | Core fusion pipeline with 4-signal scoring |
| `backend/services/retrieval/intent.py` | `QueryIntent` and `FacetFilter` dataclasses |
| `backend/services/retrieval/intent_parser.py` | Deterministic pattern-based intent parser |
| `backend/routers/retrieval_search.py` | `POST /api/retrieval/search` endpoint |
| `backend/services/context_builder.py` | Extended with `_build_structured_context()` |

## API

### POST /api/retrieval/search

```json
{
  "query": "what blocks ONB-142?",
  "top_k": 5,
  "facets": {
    "status_category": ["To Do", "In Progress"],
    "project_key": ["ONB"]
  }
}
```

Response:
```json
{
  "results": [...],
  "intent": {
    "text": "what blocks ONB-142?",
    "wants_issues_only": true,
    "keys_in_query": ["ONB-142"],
    "has_jira_signals": true,
    ...
  },
  "result_count": 3
}
```

## Feature Gate

Set `JARVIS_FEATURE_JIRA_RETRIEVAL=1` to enable. Without this flag:
- Intent parsing still runs (cheap) but enrichment signal and boosts are skipped
- Context builder uses legacy flat format
- No behavioral change for non-Jira workspaces

## Gotchas

- Sprint filtering currently treats any sprinted issue as "active" since frontmatter stores sprint name only, not state
- Enrichment signal only fires for `jira_issue` subject types — notes never receive enrichment scores
- `_apply_facet_filter` queries frontmatter JSON from SQLite, which is fast but not indexed — acceptable for typical candidate set sizes (≤15)
