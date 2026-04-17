# Step 22c — Local-Model Enrichment Pipeline

> **Goal**: For every Jira issue (and, generically, every chunk-heavy
> source), produce a structured enrichment record — work type, business
> area, execution type, risk, ambiguity, summary, actionable next step —
> using a local Ollama model. Cache by `content_hash` so nothing is
> recomputed for unchanged inputs.

**Status**: ⬜ Not started
**Depends on**: 22a, 21a–d (local models), step-19b (embeddings — for
`likely_dependencies` in 22d)
**Effort**: ~3 days

---

## Design principles

1. **Generic subject, Jira is the first user.** The enrichment record
   schema is defined once and reused for issues, notes, decisions and
   ingested documents. Only the prompt template is subject-specific.
2. **Strict JSON schema.** The local model is asked for JSON only,
   validated with Pydantic, with one retry at lower temperature. On
   second failure the enrichment is stored as `status="failed"` with the
   raw output for debugging — the import does not fail.
3. **Cached by content + model.** Key =
   `(subject_type, subject_id, content_hash, model_id, prompt_version)`.
   Changing the prompt version invalidates old enrichments automatically.
4. **Queued and bounded.** A background worker processes a bounded queue.
   Import returns as soon as Markdown + DB rows are written. Enrichment
   catches up asynchronously.
5. **Observable.** Every enrichment carries a cost record (tokens,
   duration, model). A settings page shows the queue depth and failure
   rate.

---

## Schema

```sql
CREATE TABLE IF NOT EXISTS enrichments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type     TEXT NOT NULL,     -- "jira_issue" | "note" | "url" | "pdf"
    subject_id       TEXT NOT NULL,     -- issue_key, note path, etc.
    content_hash     TEXT NOT NULL,
    model_id         TEXT NOT NULL,     -- "ollama_chat/qwen3:4b"
    prompt_version   INTEGER NOT NULL,
    status           TEXT NOT NULL,     -- "pending" | "ok" | "failed"
    payload          TEXT NOT NULL,     -- JSON below, or {} if failed
    raw_output       TEXT,              -- only when failed
    tokens_in        INTEGER,
    tokens_out       INTEGER,
    duration_ms      INTEGER,
    created_at       TEXT NOT NULL,
    UNIQUE(subject_type, subject_id, content_hash, model_id, prompt_version)
);

CREATE INDEX IF NOT EXISTS idx_enrich_subject ON enrichments(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_enrich_status  ON enrichments(status);
```

Denormalised "latest enrichment" view used by retrieval:

```sql
CREATE VIEW IF NOT EXISTS latest_enrichment AS
SELECT e.*
FROM enrichments e
JOIN (
    SELECT subject_type, subject_id, MAX(created_at) AS mx
    FROM enrichments WHERE status='ok' GROUP BY 1,2
) l
ON e.subject_type = l.subject_type
AND e.subject_id = l.subject_id
AND e.created_at = l.mx;
```

---

## Enrichment payload (v1)

```json
{
  "summary": "string, ≤ 280 chars, plain prose",
  "actionable_next_step": "string, ≤ 200 chars",
  "work_type":      "bug | feature | refactor | research | ops | blocker | maintenance | unknown",
  "business_area":  "onboarding | billing | auth | analytics | growth | infra | support | unknown",
  "execution_type": "implementation | decision | investigation | dependency | follow_up | unknown",
  "risk_level":       "low | medium | high",
  "ambiguity_level":  "clear | partial | unclear",
  "hidden_concerns":  ["string", …],               // ≤ 5
  "likely_related_issue_keys": ["ONB-141", …],     // ≤ 10, only keys the model has seen
  "keywords":         ["string", …]                 // 3–8, used later for soft edges
}
```

Enums are *finite and validated*. Values outside the enum → remapped to
`unknown` (logged, counted in metrics).

`business_area` enum is configurable per workspace in
`memory/jira/_config.json` under `business_areas:` so teams can rename or
extend categories. The prompt is built from that config — never hardcoded.

---

## Pipeline

```
┌─────────────────┐
│ jira_ingest.py  │ writes issue, pushes (subject_id, hash) into queue
└────────┬────────┘
         │
         ▼
┌──────────────────┐
│ enrichment_queue │ SQLite-backed FIFO, dedup by (type, id, hash)
└────────┬─────────┘
         │  asyncio worker, concurrency=2
         ▼
┌──────────────────────────────┐
│ enrichment_service.enrich()  │
│  1. build_prompt(subject)    │  ← subject-specific template
│  2. call_local_model()       │  ← via llm_service / ollama
│  3. parse_json_strict()      │  ← Pydantic, repair, retry once
│  4. store_record()           │
└──────────────────────────────┘
```

### Prompt template (Jira)

Kept in `backend/services/enrichment/prompts/jira_issue_v1.txt`. The
template version is the `prompt_version` column — bump it to invalidate
the cache across a workspace.

Key prompt rules:

- JSON-only output, no prose, no markdown fences.
- Inputs capped at ~1800 tokens of issue text (title + description +
  selected comments). Use the chunking service from 20a to pick the top
  chunks by positional + length heuristic to fit budget.
- Provide the enum lists literally in the prompt.
- Provide a whitelist of **known issue keys from the same project** (max
  80, truncated) for `likely_related_issue_keys`. The model cannot
  propose keys it was not shown, preventing hallucinations.

### Model choice

- Default: workspace "everyday" preset (`qwen3:4b` per step-21a).
- Override per workspace in config (`enrichment.model_id`).
- A hardware probe at first run downgrades to `qwen3:1.7b` if RAM < 12 GB.
- Temperature 0.2 first attempt, 0.0 on retry.

### Throttling and back-pressure

- Bounded queue (default 10 000 entries); `POST /api/jira/import` returns
  `202` even when queue is near full, but emits a warning event.
- Per-model concurrency from `ollama_service` hardware profile.
- Stop condition on battery power (macOS / Linux) to avoid pegging the CPU.

---

## API

```
GET  /api/enrichment/queue
  → { pending, processing, failed_last_hour, model_id }

POST /api/enrichment/rerun
  body: { subject_type?, subject_ids?, reason }
  → 202 { queued }

GET  /api/enrichment/{subject_type}/{subject_id}
  → latest enrichment payload (or 404)
```

No direct "write enrichment" endpoint. Enrichments are always produced
through the pipeline so the cache invariant holds.

---

## Generalisation to non-Jira

The same pipeline runs on any `subject_type`. For v1 we enable two
subjects:

- `jira_issue` (this step)
- `note` (opt-in, limited to `memory/projects/**` and
  `memory/decisions/**` to keep cost low)

Notes skip `likely_related_issue_keys` and gain
`likely_related_note_paths` instead. The payload schema is otherwise
identical — this is what unlocks cross-source retrieval in 22f.

---

## Tests

- `test_enrichment_schema_enforced`: model returns garbage → row is
  stored with `status="failed"` and the import is unaffected.
- `test_cache_hit_no_model_call`: second enrichment of the same
  `(subject, hash, model, prompt_version)` does zero model calls.
- `test_prompt_version_invalidates`: bumping prompt_version re-enriches.
- `test_enum_mapping`: out-of-enum values map to `unknown`, never raise.
- `test_hallucinated_keys_filtered`: model invents `FOO-999` not in the
  whitelist → filtered out.
- `test_battery_stop` (manual tag): queue pauses when battery power
  detected.

---

## Definition of done

- Importing a 500-issue export populates the queue, and every issue ends
  up with a validated enrichment within reasonable time on the workspace
  model.
- Failed enrichments are visible in `/api/enrichment/queue` and the
  Settings UI.
- Re-importing changes nothing when `content_hash` is unchanged.
- `docs/features/enrichment-pipeline.md` authored.
