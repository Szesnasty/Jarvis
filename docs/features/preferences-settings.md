---
title: Preferences & Settings
status: active
type: feature
sources:
  - backend/routers/preferences.py
  - backend/routers/settings.py
  - backend/services/preference_service.py
  - backend/services/token_tracking.py
  - backend/config.py
  - frontend/app/pages/settings.vue
  - frontend/app/composables/usePreferences.ts
depends_on: [workspace-onboarding]
last_reviewed: 2026-04-14
last_updated: 2026-04-14
---

# Preferences & Settings

## Summary

Preferences & Settings covers two related but distinct concerns: **user preferences** (arbitrary key/value pairs persisted to disk and injected into Claude's context) and **application settings** (API key management, voice toggles, token budget, token usage, and maintenance actions). Both surface in the `/settings` page and are backed by a flat JSON file in the workspace rather than SQLite, so they survive database resets and remain human-readable.

## How It Works

### Two layers, one page

The Settings page (`/settings`) pulls from two separate backend routers on mount:

- `GET /api/settings` — assembles a single view-model from workspace metadata, API key status, and voice preferences stored in `preferences.json`.
- `GET /api/settings/usage` — returns cumulative token totals from `token_tracking`.
- `GET /api/settings/budget` — returns the current daily token budget, today's usage against it, and warning level.

These are read-only aggregation endpoints. Mutations go to dedicated sub-routes (`PATCH /api/settings/api-key`, `PATCH /api/settings/voice`, `PATCH /api/settings/budget`).

The raw preferences CRUD (`/api/preferences`) is a separate surface used by composables and the Claude context pipeline, not the settings page directly.

### Preference storage

`preference_service.py` reads and writes a single file: `{workspace}/app/preferences.json`. The format is a flat `{ "key": "value" }` object where all values are strings. There is no schema enforcement beyond the non-empty key check — any string key is accepted.

On write the service does a read-modify-write cycle: it loads the current file, updates the one key, and overwrites the file. This is not atomic, but because preferences are low-frequency writes from a single local process, the risk of a torn write is negligible.

### Preferences as Claude context

`preference_service.format_for_prompt()` converts the full preference map into a bulleted string formatted as `- [key] value`. This is injected into the system prompt by the context builder, giving Claude awareness of the user's declared preferences without requiring a separate retrieval step. If the file is empty or absent, the function returns `None` and nothing is injected.

### Voice preferences are namespaced preferences

Voice toggles (`auto_speak`, `tts_voice`) are stored as regular preference entries with a `voice_` prefix. `PATCH /api/settings/voice` enforces a whitelist of valid keys (`auto_speak`, `tts_voice`) before writing them. The settings view-model strips the prefix when returning them to the frontend so callers see plain `auto_speak` / `tts_voice` fields.

### API key handling

The settings router delegates key storage entirely to `workspace_service._store_api_key()`. The settings page only knows three states via the `key_storage` field: `"keyring"` (OS keystore, preferred), `"file"` (fallback plain-file storage), or `"environment"` (key came from the `ANTHROPIC_API_KEY` env var and cannot be updated via the UI path). The UI renders a visible warning when storage falls back to file mode.

#### Status indicator

The API key section header includes a status badge that shows "Connected" (green with a pulsing dot) or "Not configured" (red). Below the header, a status row gives a secondary confirmation: when a key is present it shows "Key stored securely" followed by the storage method in plain English ("via system credential store", "via environment variable", or "via local file"); when absent it shows "No API key configured — Chat and AI features are disabled".

The input field and submit button are contextual: when a key is already set, the placeholder reads "Paste new key to replace..." and the button reads "Replace"; otherwise the placeholder is the key prefix hint "sk-ant-..." and the button reads "Set Key".

#### Backend verification

`get_workspace_status()` in `workspace_service.py` no longer trusts the `api_key_set` flag in `config.json` alone. On every call it executes `get_api_key()` against the actual storage backend (keyring, environment variable, or file) and sets `api_key_set` based on whether a key is actually retrievable. This prevents the UI from showing "Connected" after a key is deleted from the OS keychain without going through the Jarvis settings page.

When `PATCH /api/settings/api-key` stores a new key it also writes `api_key_set: true` back into `config.json` to keep the flag consistent with reality. This write is non-critical: if `config.json` is missing or malformed, the error is silently swallowed and the live verification path in `get_workspace_status()` will still return the correct state.

### Runtime configuration

`config.py` exposes a `Settings` pydantic-settings model cached via `@lru_cache`. It reads environment variables prefixed with `JARVIS_` and falls back to defaults (`workspace_path = ~/Jarvis`, port 8000). A lightweight `.env` parser runs at import time before pydantic-settings takes over, using `os.environ.setdefault` so existing env vars always win.

### Token budget

The daily token budget controls how many tokens Jarvis may consume in a single UTC day before chat is blocked. The budget value is stored as the preference key `daily_token_budget` in `preferences.json` (string-encoded integer). A value of `0` means unlimited.

`token_tracking.get_daily_budget()` reads the preference at check time, falling back to `DEFAULT_DAILY_BUDGET` (100,000 tokens) if the key is absent or unparseable. `check_budget()` compares today's cumulative usage against the budget and returns a warning level:

| Level | Condition |
|---|---|
| `ok` | Usage below 80% of budget |
| `warning` | Usage between 80% and 99% of budget |
| `exceeded` | Usage at or above 100% of budget |

When the budget is `0` (unlimited), `check_budget()` always returns level `ok` with `percent: 0`.

The settings page exposes this as a full dashboard:

- **Usage gauge** -- a progress bar with color transitions (cyan at normal, amber at warning, red when exceeded) and an animated striped overflow indicator if usage exceeds 100%.
- **Budget slider + numeric input** -- range 0 to 2,000,000 in steps of 50,000. Changes are persisted on slider release or input change via `PATCH /api/settings/budget`.
- **Preset buttons** -- 50K, 100K, 250K, 500K, 1M, and Unlimited (0). Clicking a preset immediately saves.
- **All-time stats** -- total tokens, request count, and estimated cost pulled from `GET /api/settings/usage`.
- **14-day history sparkline** -- a bar chart of daily token totals from `GET /api/settings/usage/history`, with a dashed line showing the current budget limit and red bars for days that exceeded it.

The estimated cost hint uses a blended rate of roughly $9 per million tokens (averaged across input at $3/MTok and output at $15/MTok).

### Frontend composable

`usePreferences.ts` wraps the `/api/preferences` endpoints with an optimistic update pattern: it writes the new value into the local `preferences` ref immediately, calls the API, and reverts to a fresh server fetch if the call fails. This keeps the UI responsive for low-latency feedback while staying consistent on error.

## Key Files

- `backend/routers/preferences.py` — CRUD endpoints for arbitrary key/value preferences; used by composables and internal services.
- `backend/routers/settings.py` — Aggregated settings view, API key update, voice preference update, budget read/write, and token usage endpoints.
- `backend/services/preference_service.py` — Reads, writes, and deletes entries in `preferences.json`; provides `format_for_prompt()` for Claude context injection.
- `backend/services/token_tracking.py` — JSONL-based token usage logging, daily/all-time aggregation, and budget enforcement via `check_budget()` and `get_daily_budget()`.
- `backend/config.py` — Pydantic-settings `Settings` model with `JARVIS_`-prefixed env var support and `.env` file bootstrap; singleton via `lru_cache`.
- `frontend/app/pages/settings.vue` — Settings UI: API key section with connected/not-configured status badge and storage-method detail row, contextual input placeholder and button label, file-storage warning, voice toggles, maintenance actions (reindex, graph rebuild), and token usage and budget dashboard with gauge, slider, presets, all-time stats, and 14-day history sparkline.
- `frontend/app/composables/usePreferences.ts` — Thin composable over `/api/preferences` with optimistic update and automatic revert on failure.

## API / Interface

### `GET /api/settings`

Returns a combined view of workspace metadata and current voice preferences.

```typescript
{
  workspace_path: string        // absolute path to Jarvis workspace
  api_key_set: boolean          // verified by actually reading the stored key, not trusting a flag
  key_storage: "keyring" | "file" | "environment"
  voice: {
    auto_speak: string          // "true" | "false" (string, not boolean)
    tts_voice: string           // "default" or a voice name
  }
}
```

### `PATCH /api/settings/api-key`

```typescript
// Request body
{ api_key: string }

// Response
{ api_key_set: true }
```

Returns 422 if `api_key` is empty or missing. On success, stores the key via `_store_api_key()` and then attempts to write `api_key_set: true` into `config.json` to keep the flag consistent. The config write failure is silently ignored — status correctness is guaranteed by the live verification in `get_workspace_status()`.

### `PATCH /api/settings/voice`

```typescript
// Request body — any subset of valid keys
{ auto_speak?: string, tts_voice?: string }

// Response — full updated voice block
{ auto_speak: string, tts_voice: string }
```

Returns 422 if any key in the body is not in the allowed set.

### `GET /api/settings/budget`

Returns the current daily budget status including today's usage against the limit.

```typescript
{
  daily_budget: number     // 0 = unlimited
  used_today: number       // tokens consumed today (UTC)
  percent: number          // usage as percentage of budget (0 when unlimited)
  level: "ok" | "warning" | "exceeded"
}
```

### `PATCH /api/settings/budget`

```typescript
// Request body
{ daily_token_budget: number }   // 0 = unlimited, must be >= 0

// Response
{ daily_token_budget: number }
```

Returns 422 if `daily_token_budget` is missing, non-integer, or negative.

### `GET /api/settings/usage` / `GET /api/settings/usage/today` / `GET /api/settings/usage/history`

Delegate entirely to `token_tracking`. See the chat feature docs for the token tracking schema.

### `GET /api/preferences`

Returns the full `preferences.json` as `Record<string, string>`.

### `PATCH /api/preferences`

```typescript
// Request body (PreferenceSetRequest schema)
{ key: string, value: string }

// Response — full updated preferences map
Record<string, string>
```

Returns 400 if `key` is empty.

### `DELETE /api/preferences/{key}`

Always returns `{ status: "deleted" }`, even if the key did not exist.

## Gotchas

- **All preference values are strings.** The `auto_speak` voice preference is stored as the string `"true"` or `"false"`, not a boolean. The settings page must compare `resp.voice.auto_speak === 'true'` explicitly — a plain truthiness check on a non-empty string would always evaluate to `true`.

- **`format_for_prompt()` returns `None`, not an empty string**, when no preferences exist. Callers in the context builder must guard for `None` before concatenating.

- **`DELETE /api/preferences/{key}` is silently idempotent.** A delete on a non-existent key returns a 200 success rather than 404. This is intentional but callers should not rely on the response to confirm the key ever existed.

- **`lru_cache` on `get_settings()` means runtime env var changes are invisible.** If `JARVIS_WORKSPACE_PATH` changes after the first import, the cached `Settings` instance will still hold the original value. A process restart is required to pick up the new value.

- **The `.env` parser uses `os.environ.setdefault`**, which means values already present in the environment at startup will never be overridden by the `.env` file. This is by design (container/system env takes precedence), but it can surprise developers who edit `.env` and expect it to take effect over a pre-existing shell export.

- **The daily budget is advisory, not a hard gate at the API level.** `check_budget()` returns a status, but it is up to the caller (the chat router) to decide whether to block requests when `level` is `"exceeded"`. The settings page warns the user but does not disable the send button itself -- the backend enforces the block.

- **Budget resets are UTC-based.** The "today" window is determined by `datetime.now(timezone.utc)`, not the user's local timezone. A user in UTC-5 will see their budget reset at 7 PM local time.

- **`get_daily_budget()` does a lazy import of `preference_service`** to avoid circular imports. This means the first call in a process incurs the import overhead, though it is negligible.

- **Workspace must exist before preferences can be written.** `preference_service.save_preference()` creates `app/` with `mkdir(parents=True, exist_ok=True)`, but the parent `workspace/` directory is assumed to already exist from the onboarding flow. Writing preferences before onboarding completes will silently create a partial directory tree.

- **`api_key_set` is verified live on every `GET /api/settings` call.** `get_workspace_status()` calls `get_api_key()` each time to confirm the key is actually present in storage, not just flagged in `config.json`. On systems where the OS keyring is slow or locked (e.g., a headless server without a session unlock), this check adds latency to every settings page load.

- **The storage method string is `"keyring"`, not `"keychain"`.** `get_key_storage_method()` returns `"keyring"` when the key is found via the `keyring` Python package. The UI maps this value to the human-readable label "via system credential store". Comparing against `"keychain"` in any client code will silently fail to match.
