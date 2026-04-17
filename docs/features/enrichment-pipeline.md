---
title: Enrichment Pipeline
status: active
type: feature
sources:
  - backend/routers/enrichment.py
  - backend/routers/settings.py
  - backend/services/enrichment_service.py
  - backend/services/enrichment/__init__.py
  - backend/services/enrichment/models.py
  - backend/services/enrichment/runtime.py
  - backend/services/enrichment/subjects.py
  - backend/services/enrichment/repository.py
  - backend/services/enrichment/worker.py
  - backend/services/jira_ingest.py
  - backend/models/database.py
  - backend/main.py
  - frontend/app/pages/settings.vue
  - backend/tests/test_enrichment_pipeline.py
depends_on: [jira-ingest, local-models, database]
last_reviewed: 2026-04-17
last_updated: 2026-04-17
---

# Enrichment Pipeline

## Summary

The enrichment pipeline generates structured metadata for content-heavy subjects using a local Ollama model and stores results in SQLite cache tables. It is asynchronous, cache-aware by `(subject_type, subject_id, content_hash, model_id, prompt_version)`, resilient to model/schema failures, and exposed via queue/result APIs for observability and reruns.

## How It Works

Importers (currently Jira ingest) enqueue enrichment work into `enrichment_queue` whenever a subject changes. FastAPI startup launches worker tasks that claim queue rows FIFO, load subject-specific context, build a prompt template, call the local model, and validate strict JSON output.

Validation uses a deterministic normalization step:
- finite enums are mapped to known sets (unknown values remap to `unknown` or safe defaults)
- lists are bounded (`hidden_concerns`, related keys/paths, keywords)
- hallucinated Jira keys are filtered against a same-project whitelist

Each result is stored in `enrichments` with status `ok` or `failed`. Failures never block import; they persist raw model output for debugging and can be requeued through API. The `latest_enrichment` SQL view provides retrieval-friendly access to the newest successful payload per subject.

## Key Files

- `backend/services/enrichment/worker.py` - Worker loop, model call, retry policy, strict parsing and persistence.
- `backend/services/enrichment/repository.py` - Queue operations, cache checks, persistence, status and rerun helpers.
- `backend/services/enrichment/subjects.py` - Jira/note context loading, prompt assembly, and subject hash helpers.
- `backend/services/enrichment/runtime.py` - Model/base-url selection, business area config, battery guardrails.
- `backend/services/enrichment/models.py` - Enrichment schema, queue item type, enums, constants.
- `backend/routers/enrichment.py` - API endpoints: queue status, rerun, and subject lookup.
- `backend/models/database.py` - `enrichments`, `enrichment_queue`, and `latest_enrichment` schema.
- `backend/services/jira_ingest.py` - Enqueues jobs after insert/update.
- `backend/main.py` - Starts/stops enrichment workers in app lifespan.
- `backend/routers/settings.py` - `GET/PATCH /api/settings/enrichment` for battery toggle and model selection.
- `frontend/app/pages/settings.vue` - Sharpen section UI: model dropdown, progress bar, battery toggle, quality dots.

## API / Interface

- `GET /api/enrichment/queue` -> `{ pending, processing, failed_last_hour, completed_total, model_id }`
- `POST /api/enrichment/rerun` -> requeue selected or failed subjects
- `GET /api/enrichment/{subject_type}/{subject_id}` -> latest successful enrichment payload
- `GET /api/settings/enrichment` -> `{ allow_on_battery, on_battery, model_id }`
- `PATCH /api/settings/enrichment` -> update `allow_on_battery` (bool) and/or `model_id` (string); model_id persisted to `~/Jarvis/app/config.json` → `enrichment.model_id`

## Gotchas

- Prompt cache invalidation is controlled by `PROMPT_VERSION`; bumping it forces fresh enrichments for unchanged content.
- Queue dedup uses `(subject_type, subject_id, content_hash)`, so repeated imports do not fan out duplicate work.
- On parse/model failure the pipeline records `status="failed"` instead of raising; operational dashboards must monitor failure rates.
- Battery guard pauses workers on battery power (best-effort detection on macOS/Linux).
- Subject type `note` is intentionally scoped to `memory/projects/**` and `memory/decisions/**` to keep local-model cost bounded.
