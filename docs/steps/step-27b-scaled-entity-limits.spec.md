# Step 27b — Length-Scaled Entity Caps

> **Goal**: Replace fixed per-note entity caps with size-scaled caps so
> a 30-page section keeps more entities than a 200-word memo. Long-tail
> entities currently silently dropped become real graph nodes, which
> in turn become bridges between sections (Step 27a).

**Parent**: [step-27-graph-density.md](step-27-graph-density.md)
**Status**: ⬜ Planned

---

## Current behaviour

`backend/services/graph_service/entity_edges.py`:

```python
MAX_PERSONS_PER_NOTE  = 50
MAX_ORGS_PER_NOTE     = 50
MAX_PROJECTS_PER_NOTE = 25
MAX_PLACES_PER_NOTE   = 25
_MAX_CO_MENTION_PAIRS_PER_NOTE = 100
```

These caps were chosen for hand-written notes (≤ 2 KB). For PDF-derived
sections of 5–20 KB they cut the long tail aggressively.

## Design

### Scaled caps

Replace the constants with a `compute_caps(body_len: int) -> dict`
helper:

```python
BASE_CAPS = {"person": 50, "org": 50, "project": 25, "place": 25}
HARD_CAPS = {"person": 200, "org": 200, "project": 100, "place": 100}

def compute_caps(body_len: int) -> dict[str, int]:
    """Scale linearly from BASE at 2KB up to HARD at 40KB."""
    if body_len <= 2_000:
        return dict(BASE_CAPS)
    if body_len >= 40_000:
        return dict(HARD_CAPS)
    ratio = (body_len - 2_000) / (40_000 - 2_000)
    return {
        k: int(BASE_CAPS[k] + ratio * (HARD_CAPS[k] - BASE_CAPS[k]))
        for k in BASE_CAPS
    }
```

Hard caps prevent a pathological 1 MB note from exploding the graph.

### Co-mention pair cap

```python
def compute_co_mention_cap(body_len: int) -> int:
    if body_len <= 2_000:
        return 100
    if body_len >= 40_000:
        return 400
    ratio = (body_len - 2_000) / (40_000 - 2_000)
    return int(100 + ratio * 300)
```

### Wiring

`apply_extracted_entities()` already receives `body`. Compute caps once
at the top of the function and replace the static lookup of
`PER_TYPE_CAPS[t]` with the scaled dict. Same for `_emit_co_mentions`.

No callers change — the function signature stays the same.

### Logging

When a cap is *hit* (i.e. extraction returned more entities than the
cap), log at DEBUG with `note_id`, `entity_type`, `extracted`, `cap`.
Helps tuning without spamming INFO.

### Tests

Extend `backend/tests/test_entity_edges.py` (or create if absent):

1. `test_caps_scale_with_body_length` — small/medium/huge body produces
   monotonically increasing caps, never above HARD_CAPS.
2. `test_caps_clamped_to_hard_cap` — body_len = 1 MB returns HARD_CAPS.
3. `test_co_mention_pair_cap_scales` — same shape.
4. `test_existing_short_note_unchanged` — short body still yields the
   original 50/50/25/25 caps (regression guard).

### Acceptance

- A synthetic 20 KB note with 120 distinct people produces ≥ 100
  `person:` nodes (was 50).
- Short notes (< 2 KB) keep the existing 50/50/25/25 behaviour exactly.
- All existing tests pass.

### Out of scope

- Per-folder or per-tag override knobs.
- Changing entity *quality* thresholds — confidence floors are
  unchanged.
- Changing how entities are extracted (still spaCy + regex from
  `entity_extraction.py`).
