---
title: Preferences & Settings
status: active
type: feature
sources:
  - backend/routers/preferences.py
  - backend/routers/settings.py
  - backend/services/preference_service.py
  - backend/config.py
  - frontend/app/pages/settings.vue
  - frontend/app/composables/usePreferences.ts
depends_on: [workspace-onboarding]
last_reviewed: 2026-04-14
---

# Preferences & Settings

## Summary

Preferences & Settings covers two related but distinct concerns: **user preferences** (arbitrary key/value pairs persisted to disk and injected into Claude's context) and **application settings** (API key management, voice toggles, token usage, and maintenance actions). Both surface in the `/settings` page and are backed by a flat JSON file in the workspace rather than SQLite, so they survive database resets and remain human-readable.

## How It Works

### Two layers, one page

The Settings page (`/settings`) pulls from two separate backend routers on mount:

- `GET /api/settings` — assembles a single view-model from workspace metadata, API key status, and voice preferences stored in `preferences.json`.
- `GET /api/settings/usage` — returns cumulative token totals from `token_tracking`.

These are read-only aggregation endpoints. Mutations go to dedicated sub-routes (`PATCH /api/settings/api-key`, `PATCH /api/settings/voice`).

The raw preferences CRUD (`/api/preferences`) is a separate surface used by composables and the Claude context pipeline, not the settings page directly.

### Preference storage

`preference_service.py` reads and writes a single file: `{workspace}/app/preferences.json`. The format is a flat `{ "key": "value" }` object where all values are strings. There is no schema enforcement beyond the non-empty key check — any string key is accepted.

On write the service does a read-modify-write cycle: it loads the current file, updates the one key, and overwrites the file. This is not atomic, but because preferences are low-frequency writes from a single local process, the risk of a torn write is negligible.

### Preferences as Claude context

`preference_service.format_for_prompt()` converts the full preference map into a bulleted string formatted as `- [key] value`. This is injected into the system prompt by the context builder, giving Claude awareness of the user's declared preferences without requiring a separate retrieval step. If the file is empty or absent, the function returns `None` and nothing is injected.

### Voice preferences are namespaced preferences

Voice toggles (`auto_speak`, `tts_voice`) are stored as regular preference entries with a `voice_` prefix. `PATCH /api/settings/voice` enforces a whitelist of valid keys (`auto_speak`, `tts_voice`) before writing them. The settings view-model strips the prefix when returning them to the frontend so callers see plain `auto_speak` / `tts_voice` fields.

### API key handling

The settings router delegates key storage entirely to `workspace_service._store_api_key()`. The settings page only knows three states via the `key_storage` field: `"keychain"` (OS keystore, preferred), `"file"` (fallback plain-file storage), or `"environment"` (key came from the `ANTHROPIC_API_KEY` env var and cannot be updated via the UI path). The UI renders a visible warning when storage falls back to file mode.

### Runtime configuration

`config.py` exposes a `Settings` pydantic-settings model cached via `@lru_cache`. It reads environment variables prefixed with `JARVIS_` and falls back to defaults (`workspace_path = ~/Jarvis`, port 8000). A lightweight `.env` parser runs at import time before pydantic-settings takes over, using `os.environ.setdefault` so existing env vars always win.

### Frontend composable

`usePreferences.ts` wraps the `/api/preferences` endpoints with an optimistic update pattern: it writes the new value into the local `preferences` ref immediately, calls the API, and reverts to a fresh server fetch if the call fails. This keeps the UI responsive for low-latency feedback while staying consistent on error.

## Key Files

- `backend/routers/preferences.py` — CRUD endpoints for arbitrary key/value preferences; used by composables and internal services.
- `backend/routers/settings.py` — Aggregated settings view, API key update, voice preference update, and token usage endpoints.
- `backend/services/preference_service.py` — Reads, writes, and deletes entries in `preferences.json`; provides `format_for_prompt()` for Claude context injection.
- `backend/config.py` — Pydantic-settings `Settings` model with `JARVIS_`-prefixed env var support and `.env` file bootstrap; singleton via `lru_cache`.
- `frontend/app/pages/settings.vue` — Settings UI: API key management with storage-method transparency, voice toggles, maintenance actions (reindex, graph rebuild), and token usage display.
- `frontend/app/composables/usePreferences.ts` — Thin composable over `/api/preferences` with optimistic update and automatic revert on failure.

## API / Interface

### `GET /api/settings`

Returns a combined view of workspace metadata and current voice preferences.

```typescript
{
  workspace_path: string        // absolute path to Jarvis workspace
  api_key_set: boolean          // whether any key is stored
  key_storage: "keychain" | "file" | "environment"
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

Returns 422 if `api_key` is empty or missing.

### `PATCH /api/settings/voice`

```typescript
// Request body — any subset of valid keys
{ auto_speak?: string, tts_voice?: string }

// Response — full updated voice block
{ auto_speak: string, tts_voice: string }
```

Returns 422 if any key in the body is not in the allowed set.

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

- **Workspace must exist before preferences can be written.** `preference_service.save_preference()` creates `app/` with `mkdir(parents=True, exist_ok=True)`, but the parent `workspace/` directory is assumed to already exist from the onboarding flow. Writing preferences before onboarding completes will silently create a partial directory tree.

## Known Issues

**High — `PATCH /api/settings/api-key` calls a private function with no workspace guard (`settings.py:28-35`).**
The route calls `workspace_service._store_api_key(key, ws)` directly, bypassing any workspace-existence check. If the workspace has not been initialized (or was deleted), `_store_api_key` will attempt to write into a directory tree that may not exist, with no HTTP-level error surfaced to the caller. Additionally, the route accepts a raw `dict` body without a typed Pydantic schema, so the request is not validated at the framework level — a missing or misnamed key produces a 200 with a silently empty key rather than a 422.

**Medium — Voice settings writes are not atomic (`settings.py:38-50`).**
`PATCH /api/settings/voice` iterates over the incoming keys and calls `preference_service.save_preference()` once per key. Each call is an independent read-modify-write on `preferences.json`. If the process crashes or the file system raises an error between two saves (e.g., when updating both `auto_speak` and `tts_voice` simultaneously), the file is left in a partially updated state with no rollback. The two preferences can become inconsistent until the next successful write.

**Medium — No size limit on preference values (`preference_service.py:29`).**
`save_preference` imposes no length constraint on the value string. All stored preferences are included verbatim in every Claude system prompt via `format_for_prompt()`. A single large preference value (e.g., several kilobytes of text saved by accident or via a UI bug) will inflate token usage on every request until it is manually deleted.

**Medium — Custom `.env` parser is redundant and handles edge cases incorrectly (`config.py:8-19`).**
`_load_dotenv()` runs a hand-written `.env` parser before pydantic-settings initializes. Pydantic-settings already supports `.env` files natively via `env_file`. The hand-written parser strips both leading and trailing quotes from values (`strip('"').strip("'")`), which means a value like `'it"s fine'` would be incorrectly stripped. Values containing `=` in the value portion are handled correctly by `partition("=")`, but inline comments are not stripped, so `KEY=value # comment` stores `value # comment` as the value.

**Medium — Swallowed errors in `onMounted` leave UI in a wrong state (`settings.vue:100`, `103-104`).**
Both `$fetch` calls in `onMounted` use empty `catch { /* ignore */ }` blocks. If the settings fetch fails (e.g., backend down), `workspacePath`, `apiKeySet`, and `keyStorage` remain at their zero values — the key shows "Not set" and the storage warning is never rendered. There is no error message, no retry prompt, and no loading indicator. The user sees what looks like a pristine unconfigured state rather than an error, which could lead them to re-enter an API key unnecessarily.

**Low — `auto_speak` stored as a string literal, not a boolean (`settings.vue:99`).**
The settings page correctly handles this by comparing `resp.voice.auto_speak === 'true'` before assigning to the `autoSpeak` boolean ref. However, the `PATCH /api/settings/voice` call sends `String(autoSpeak.value)` — producing `"true"` or `"false"` — which the backend stores as a string. Any future consumer that reads `auto_speak` from preferences and treats it as a boolean without explicit string comparison will get `true` for both `"true"` and `"false"` (since both are non-empty strings).
