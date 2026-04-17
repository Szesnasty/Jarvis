---
title: Jira Ingest
status: active
type: feature
sources:
  - backend/routers/jira.py
  - backend/services/jira_ingest.py
  - backend/models/database.py
depends_on: [memory, database, enrichment-pipeline]
last_reviewed: 2026-04-17
last_updated: 2026-04-17
---

# Jira Ingest

## Summary

The Jira ingest feature imports XML/CSV exports into the Jarvis workspace as Markdown source files and a rebuildable SQLite index. It is idempotent by content hash, writes Markdown first (source of truth), updates normalized issue tables for fast queries, and now schedules asynchronous enrichment jobs for changed issues.

## How It Works

`POST /api/jira/import` streams the uploaded file to a temporary file with strict extension and size checks. The service auto-detects XML vs CSV and parses issues in streaming mode, which keeps memory usage stable even for large exports.

For each issue, the importer computes a canonical hash that excludes noisy fields (for example volatile update metadata) and compares it with the indexed hash in SQLite. Unchanged issues are skipped. Changed issues are written to `memory/jira/{PROJECT}/{KEY}.md` using atomic write-then-rename semantics, then upserted into SQLite tables (`issues`, labels/components/sprints/links/comments).

After each inserted or updated issue row, the importer enqueues a 22c enrichment job keyed by `(subject_type, subject_id, content_hash)`. This keeps import latency low while the local-model enrichment catches up in the background worker.

## Key Files

- `backend/routers/jira.py` - Upload endpoint and list/query endpoints with request validation.
- `backend/services/jira_ingest.py` - Streaming parsers, Markdown rendering, content-hash idempotency, upsert logic, and enrichment queue handoff.
- `backend/models/database.py` - Jira ingest tables and indexes used by the importer.

## API / Interface

- `POST /api/jira/import` - Ingest XML/CSV upload and return import counters.
- `GET /api/jira/imports` - List import batches with status/duration counters.
- `GET /api/jira/issues` - Paginated issue listing for UI filtering.

## Gotchas

- Issue keys are strictly validated to prevent path traversal and malformed links.
- XML parsing uses `defusedxml` and rejects DTD/entity expansion payloads.
- Imports enqueue enrichment asynchronously; the ingest response can be successful even if later enrichment fails for some issues.
- Markdown remains canonical. If the DB is lost, issue notes under `memory/jira/` are still intact.
