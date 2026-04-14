---
title: Workspace & Onboarding
status: active
type: feature
sources:
  - backend/routers/workspace.py
  - backend/services/workspace_service.py
  - frontend/app/pages/onboarding.vue
depends_on: [database, settings-config]
last_reviewed: 2026-04-14
last_updated: 2026-04-14
---

## Summary

Workspace & Onboarding handles the one-time setup required before Jarvis can be used: collecting the Anthropic API key, creating the local directory structure, and recording that setup is complete. It runs exactly once — on subsequent starts, the app detects an existing workspace and skips straight to the main view.

## How It Works

The onboarding flow is a single-page form (`onboarding.vue`) that collects the API key and calls `POST /api/workspace/init`. On success it sets the shared `isInitialized` flag and navigates to `/main`.

On the backend, `create_workspace` in `workspace_service.py` does all the work in a fixed sequence:

1. Validates the API key is non-empty after stripping whitespace.
2. Checks that `{workspace}/app/config.json` does not already exist. If it does, a `WorkspaceExistsError` is raised immediately — no partial writes happen.
3. Creates the full directory tree (16 subdirectories under `app/`, `memory/`, `graph/`, and `agents/`) using `mkdir(parents=True, exist_ok=True)`.
4. Stores the API key via `_store_api_key`, which tries OS keychain first (`keyring`) and falls back to a plaintext `app/api_key.json` file if no keyring is available.
5. Writes `app/config.json` with version, creation timestamp, and `api_key_set: true`. The raw key is never written to `config.json`.

`GET /api/workspace/status` is the check used at startup. It reads `app/config.json` and returns whether the workspace is initialized, the path, and whether `api_key_set` is true. The app shell calls this on mount to decide whether to route the user to onboarding or directly to the main view.

The API key retrieval priority (used by the rest of the backend when making Claude API calls) is: environment variable `ANTHROPIC_API_KEY` → OS keyring → `app/api_key.json` file.

## Key Files

- `backend/routers/workspace.py` — Exposes the two HTTP endpoints (`/status`, `/init`) and maps service errors to appropriate HTTP status codes.
- `backend/services/workspace_service.py` — All workspace logic: directory creation, API key storage with keyring/file fallback, config read/write, and the key retrieval chain used across the rest of the backend.
- `frontend/app/pages/onboarding.vue` — Single-screen form, password-type input for the API key, calls `useApi().initWorkspace()`, and redirects to `/main` on success.

## API / Interface

```
GET /api/workspace/status
→ WorkspaceStatusResponse
  {
    initialized: boolean
    workspace_path?: string   // only when initialized
    api_key_set?: boolean     // only when initialized
  }

POST /api/workspace/init
Body: WorkspaceInitRequest { api_key: string }
→ 201 WorkspaceInitResponse { status: "ok", workspace_path: string }
→ 409 if workspace already exists
→ 422 if api_key is empty
```

Helper functions available to the rest of the backend (imported directly from `workspace_service`):

```python
get_api_key(workspace_path?) -> Optional[str]
get_key_storage_method(workspace_path?) -> Literal["environment", "keyring", "file", "none"]
workspace_exists(workspace_path?) -> bool
```

## Gotchas

- **Workspace existence is determined solely by `app/config.json`** — not by checking directories or the database. If that file is manually deleted, the system treats the workspace as uninitialized and will try to re-create it, but the old directories will already exist. `mkdir(exist_ok=True)` means this is safe, but a previously stored keyring entry will be overwritten with whatever key is submitted in the new onboarding run.

- **Keyring fallback writes the API key in plaintext.** On Unix the file is restricted to `0o600`, but on Windows no permission restriction is applied. Users on headless Linux systems or Docker containers without a keyring daemon will silently fall back to the file. `get_key_storage_method()` can be called to surface which method is active — the settings page uses this to show key storage transparency.

- **The frontend error message for any non-network failure** is whatever the backend sends in the `detail` field. A 409 surfaces as "Workspace already exists" and a 422 as the ValueError message. Any true network/connection failure (backend not running) falls through to the generic "Connection error. Is the backend running?" string in the catch block.

- **No SQLite initialization happens here.** The workspace directories are created by this service, but the database is initialized at backend startup via `main.py`'s lifespan handler. Onboarding guarantees the file structure and config exist; the DB is ready as soon as the backend process finishes starting.
