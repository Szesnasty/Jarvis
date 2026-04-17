# Step 23 — User-Controlled Indexing & Model Selection

> **Goal**: Give the user explicit, granular control over **what** gets
> indexed, **how deeply**, and **by which model** — with a strong nudge
> toward local models and transparent cost warnings when an API model
> is chosen. The user must never be surprised by token spend or
> background compute they didn't authorize.

**Status**: ⬜ Not started
**Depends on**: 19b (embeddings), 22c (enrichment pipeline), 21a–d (local models)
**Effort**: ~4 days (backend + frontend)

---

## Core Principles

1. **Pre-step-22 baseline runs without asking** — everything the app
   did before the Jira knowledge layer (step 22) is the implicit
   default that requires zero confirmation:
   - FTS5/BM25 full-text indexing (on every note save)
   - Local embeddings via fastembed (on every note save)
   - Entity extraction + graph rebuild
   These are cheap, local, private, and already battle-tested.
2. **LLM enrichment requires explicit opt-in** — summary,
   classification, risk/ambiguity, relation suggestions (everything
   added in step 22c) never runs until the user actively enables it.
3. **Local-first default** — when the user does opt in to enrichment,
   a local Ollama model is the recommended (and pre-selected) option.
4. **Cost transparency** — if the user picks an API model (Claude,
   GPT, etc.) for enrichment, they see a clear estimate and a
   confirmation dialog before any tokens are spent.
5. **Two independent axes** — embeddings and LLM enrichment are
   separate toggles because they differ in cost, speed, and value.
6. **Scope control** — the user picks *which* sources get processed
   by enrichment, not just on/off globally.
7. **Manual trigger always available** — the user can re-run any
   indexing pass at any time, for any scope.

---

## What Runs Without Asking (the baseline)

These are the same operations the app performed before step 22 was
implemented. They are always-on, local, free, and require no user
confirmation:

| Operation | Trigger | Cost |
|-----------|---------|------|
| Markdown parsing + FTS5/BM25 indexing | every note save | zero (SQLite) |
| Local embeddings (fastembed, CPU) | every note save | zero (ONNX, ~400 MB RAM) |
| Entity extraction (regex + heuristic) | graph rebuild | zero (no model) |
| Graph rebuild (explicit edges) | after entity extraction | zero |

The user can **disable embeddings** via a toggle in Settings if they
want a lighter footprint, but the default is **on** because it's local
and private.

---

## What Requires Explicit Opt-In (step 22c+)

Everything added by the Jira knowledge layer that involves an LLM call:

| Operation | What it does | Why opt-in |
|-----------|-------------|------------|
| Summary generation | LLM writes a 1–2 sentence summary | uses LLM tokens |
| Classification | work_type, business_area, execution_type | uses LLM tokens |
| Risk / ambiguity scoring | risk_level, ambiguity_level | uses LLM tokens |
| Hidden concerns extraction | LLM flags non-obvious issues | uses LLM tokens |
| Relation suggestions | likely_related_issue_keys, paths | uses LLM tokens |
| Soft edge generation | same_topic, likely_dependency edges | uses enrichment output |

None of the above runs until the user explicitly enables enrichment.

---

## Indexing Modes

The user chooses a mode in **Settings → Indexing**:

| Mode | BM25 + Entities | Embeddings | LLM Enrichment | When |
|------|----------------|-----------|----------------|------|
| **Fast** | ✅ always | ❌ off | ❌ off | Classic parsing + BM25 + explicit relations only |
| **Standard** | ✅ always | ✅ local model | ❌ off | Pre-step-22 baseline: full search without LLM cost |
| **Smart** | ✅ always | ✅ local model | ✅ opt-in | Full pipeline: baseline + LLM summary + classification + risk |
| **Manual** | ✅ always | user triggers | user triggers | BM25 always on; embeddings and enrichment only on manual click |

Default for new workspaces: **Standard** (= pre-step-22 behavior).

> **Note**: BM25 indexing and entity extraction always run on note save
> regardless of mode. They are pure local operations with zero cost.

---

## Two Independent Controls

### A. Embeddings

Controls the semantic layer of search (cosine similarity).

| Setting | Values | Default |
|---------|--------|---------|
| `embeddings.enabled` | `true` / `false` | `true` |
| `embeddings.model` | model identifier | `paraphrase-multilingual-MiniLM-L12-v2` |
| `embeddings.auto_embed_on_write` | `true` / `false` | `true` |

- **Always local** — no API embedding models in MVP. The explanation
  is: *"Embeddings run on your CPU, no API key needed, no data leaves
  your machine."*
- Re-embedding only when content hash changes (existing behavior).
- Manual trigger: **"Rebuild embeddings"** button.

### B. LLM Enrichment

Controls the smart layer: summary, classification, risk/ambiguity,
entities, relation suggestions.

| Setting | Values | Default |
|---------|--------|---------|
| `enrichment.enabled` | `true` / `false` | `false` |
| `enrichment.provider` | `local` / `api` | `local` |
| `enrichment.model_id` | model identifier | auto-detected from Ollama |
| `enrichment.base_url` | Ollama URL | `http://localhost:11434` |
| `enrichment.auto_enrich_on_write` | `true` / `false` | `false` |
| `enrichment.scope` | scope rules (see below) | `["all"]` |
| `enrichment.concurrency` | `1`–`4` | `2` |

- When `provider=local`: Ollama model, no cost, no data leaves machine.
- When `provider=api`: user sees the **Cost Warning Dialog** before
  confirmation (see below).

---

## Scope Control

The user can restrict which sources are processed by enrichment and/or
embeddings. Stored in `config.json` under `indexing.scope`:

```json
{
  "indexing": {
    "embeddings_scope": ["all"],
    "enrichment_scope": ["jira/**", "knowledge/**"]
  }
}
```

Scope syntax:
- `"all"` — everything in `memory/`
- `"jira/**"` — only Jira issues
- `"knowledge/**"` — only knowledge base
- `"projects/my-project/**"` — specific project
- `"!attachments/**"` — exclude pattern
- Individual paths: `"daily/2025-01-15.md"`

UI: a multi-select with folder chips + free text glob input.

---

## Cost Warning Dialog

Triggered when:
1. User switches `enrichment.provider` from `local` to `api`, OR
2. User clicks "Index now" with `provider=api`

Dialog content:

```
⚠️ API Model Selected for Enrichment

Model: claude-sonnet-4-20250514
Estimated items to process: 342
Estimated tokens: ~250K input + ~50K output
Estimated cost: ~$1.20

This will send your note/issue content to Anthropic's API.
For privacy and cost, we recommend using a local model instead.

[Switch to Local Model]  [Cancel]  [Proceed with API — I understand the cost]
```

The cost estimate is computed from:
- Number of un-enriched items in scope
- Average prompt size (measured from existing enrichments)
- Model pricing (from a static table or LiteLLM metadata)

---

## Manual Reindex Actions

Available in **Settings → Indexing** and via the command palette:

| Action | What it does |
|--------|-------------|
| **Rebuild all embeddings** | Re-embed every note/chunk (ignores content hash) |
| **Rebuild changed embeddings** | Only re-embed where content hash changed |
| **Run smart enrichment** | Queue all un-enriched items in scope |
| **Re-enrich all** | Force re-enrich everything (ignores cache) |
| **Reindex folder…** | Pick a folder → reindex + re-embed + optionally re-enrich |
| **Reindex Jira issues only** | Queue only `jira/**` items |
| **Clear enrichment cache** | Delete all enrichment results (can rebuild) |

Each action shows a progress indicator: `"Embedding 42/350 notes…"`.

---

## Config Storage

All indexing settings live in `Jarvis/app/config.json` under a new
`indexing` key:

```json
{
  "indexing": {
    "mode": "standard",
    "embeddings": {
      "enabled": true,
      "model": "paraphrase-multilingual-MiniLM-L12-v2",
      "auto_embed_on_write": true
    },
    "enrichment": {
      "enabled": false,
      "provider": "local",
      "model_id": "ollama_chat/qwen3:4b",
      "base_url": "http://localhost:11434",
      "auto_enrich_on_write": false,
      "scope": ["all"],
      "concurrency": 2
    },
    "embeddings_scope": ["all"],
    "enrichment_scope": ["all"]
  }
}
```

Backward compatibility: if `indexing` key is missing, the system
behaves as `standard` mode (= pre-step-22 baseline: embeddings on,
enrichment off). Existing `enrichment.*` keys are migrated into the
new schema on first read.

---

## Backend API

### GET /api/settings/indexing

Returns current indexing configuration.

### PATCH /api/settings/indexing

Update indexing settings. Validates:
- `mode` must be one of `fast|standard|smart|manual`
- `enrichment.provider` must be `local|api`
- `enrichment.concurrency` must be 1–4
- `enrichment.scope` entries must be valid glob patterns

When `enrichment.provider` changes to `api`, response includes
`cost_estimate` so the frontend can show the warning dialog.

### POST /api/settings/indexing/reindex

Trigger a reindex operation.

```json
{
  "action": "rebuild_embeddings_changed",
  "scope": "jira/**"  // optional, defaults to configured scope
}
```

Returns a task ID for progress tracking via WebSocket.

### GET /api/settings/indexing/status

Returns current indexing stats:
- Total notes, embedded count, enriched count
- Queue size, worker status
- Last run timestamps
- Per-folder breakdown

### POST /api/settings/indexing/estimate

Compute cost estimate for a proposed enrichment run.

```json
{
  "provider": "api",
  "model_id": "claude-sonnet-4-20250514",
  "scope": ["jira/**"]
}
```

Returns: `{ "items": 342, "est_tokens_in": 250000, "est_tokens_out": 50000, "est_cost_usd": 1.20 }`.

---

## Frontend: Settings → Indexing Tab

### Layout

```
┌─────────────────────────────────────────────┐
│  Indexing Mode                              │
│  ┌──────┐ ┌──────────┐ ┌───────┐ ┌──────┐  │
│  │ Fast │ │ Standard │ │ Smart │ │Manual│  │
│  └──────┘ └──────────┘ └───────┘ └──────┘  │
│              ↑ default                      │
├─────────────────────────────────────────────┤
│                                             │
│  Embeddings                    [Enabled ✓]  │
│  Model: multilingual-MiniLM-L12-v2   local  │
│  Auto-embed on save: [✓]                    │
│  Scope: [All sources ▾]                     │
│                                             │
│  [Rebuild embeddings ↻]                     │
│                                             │
├─────────────────────────────────────────────┤
│                                             │
│  Smart Enrichment             [Disabled ✗]  │
│  Provider: ◉ Local (Ollama)  ○ API         │
│  Model: qwen3:4b              [Change ▾]   │
│  Auto-enrich on save: [✗]                   │
│  Scope: [Jira issues only ▾]               │
│  Workers: [2 ▾]                             │
│                                             │
│  [Run enrichment ▶]   [Clear cache 🗑]      │
│                                             │
├─────────────────────────────────────────────┤
│                                             │
│  ℹ Stats                                    │
│  Notes: 450  │ Embedded: 420  │ Enriched: 0 │
│  Queue: 0 pending │ Workers: idle           │
│  Last embed: 2026-04-17 10:30               │
│                                             │
└─────────────────────────────────────────────┘
```

### API Model Warning

When user selects "API" as enrichment provider:

1. Yellow warning banner appears inline:
   > ⚠️ API enrichment sends your content to a cloud model. Each item
   > costs tokens. Use local models for free, private enrichment.
2. When "Run enrichment" is clicked with API provider, the **Cost
   Warning Dialog** appears as a modal before proceeding.

### Scope Selector

A dropdown / chip picker:
- **All sources** (default)
- **Jira issues only** (`jira/**`)
- **Knowledge base** (`knowledge/**`)
- **Projects** (`projects/**`)
- **Custom…** (free glob input)

Multiple selections allowed.

---

## Migration

### From current state

1. Existing `enrichment.model_id` / `enrichment.base_url` in
   `config.json` → migrated into `indexing.enrichment.*` on first read.
2. `JARVIS_DISABLE_EMBEDDINGS=1` env var still honored as override.
3. Existing enrichment results stay in the DB — no data loss.
4. If `indexing` key is absent, behaves as `standard` mode
   (= pre-step-22 baseline: BM25 + embeddings + entities, no LLM enrichment).

### Behavior changes

- Enrichment workers no longer auto-start on boot unless
  `enrichment.enabled=true` and `enrichment.auto_enrich_on_write=true`.
- BM25 indexing and entity extraction always run on note save
  regardless of mode — these are zero-cost local operations.
- New notes trigger embedding only when `embeddings.auto_embed_on_write=true`
  (default: true in `standard` mode, so no visible change).

---

## Implementation Sub-steps

| Sub-step | Title | Scope |
|----------|-------|-------|
| 23a | Indexing config backend: settings schema, migration, API endpoints | backend |
| 23b | Indexing config frontend: Settings tab, mode picker, scope selector | frontend |
| 23c | Cost estimation engine: token counting, model pricing, estimate API | backend |
| 23d | Cost warning dialog: modal, provider switch guard, confirmation flow | frontend |
| 23e | Manual reindex actions: rebuild, re-enrich, per-folder, progress WS | backend + frontend |
| 23f | Guard embedding/enrichment writes behind config flags | backend |

---

## Tests

- `test_default_mode_standard`: new workspace defaults to `standard` mode (BM25 + embeddings + entities, no LLM enrichment).
- `test_fast_mode_disables_embeddings`: in `fast` mode, embeddings don't run on write, but BM25 + entities still do.
- `test_standard_mode_is_pre_step22`: in `standard` mode, embeddings + BM25 + entities run automatically, enrichment does NOT.
- `test_smart_mode_enables_enrichment`: in `smart` mode, enrichment also runs on write.
- `test_manual_mode_no_auto_embed`: in `manual` mode, embeddings don't auto-run, but BM25 + entities still do.
- `test_bm25_always_runs`: BM25 indexing runs on every note save regardless of mode.
- `test_entities_always_run`: entity extraction runs on graph rebuild regardless of mode.
- `test_scope_filters_enrichment`: enrichment with `scope=["jira/**"]` only processes Jira notes.
- `test_scope_filters_embeddings`: embedding with `scope=["!attachments/**"]` skips attachments.
- `test_api_provider_returns_estimate`: switching to API provider triggers cost estimate.
- `test_cost_estimate_reasonable`: estimate for 100 items is within expected range.
- `test_reindex_changed_only`: reindex only re-embeds notes with changed content hash.
- `test_reindex_folder`: reindex for `jira/` only processes that folder.
- `test_legacy_migration`: existing `enrichment.*` config keys are migrated correctly.
- `test_env_override_respected`: `JARVIS_DISABLE_EMBEDDINGS=1` overrides config.

---

## Definition of Done

- User can choose indexing mode in Settings UI.
- Embeddings and enrichment have independent on/off toggles.
- Enrichment scope is configurable (all / folder / glob).
- Switching enrichment to API shows cost warning with estimate.
- Manual reindex actions work with progress feedback.
- Default for new workspaces is **Standard** (= pre-step-22 baseline: BM25 + embeddings + entities, no LLM enrichment).
- BM25 indexing and entity extraction always run regardless of mode.
- LLM enrichment never runs without explicit user opt-in.
- All existing tests still pass.
- Feature doc published at `docs/features/indexing-control.md`.
