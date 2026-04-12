# Step 03 — Onboarding + Workspace Creation

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 02 — Frontend Init](step-02-frontend-init.md) | **Next**: [Step 04 — Memory Service](step-04-memory-service.md) | **Index**: [index-spec.md](../index-spec.md)

---

## Goal

User can enter their Anthropic API key, create the Jarvis workspace, and be redirected to the main view. This is the complete onboarding flow.

---

## Files to Create / Modify

### Backend
```
backend/
├── routers/
│   └── workspace.py           # NEW — workspace init + status endpoints
├── services/
│   └── workspace_service.py   # NEW — creates folder tree, saves config
├── models/
│   └── schemas.py             # MODIFY — add workspace schemas
└── config.py                  # MODIFY — add workspace_path helper
```

### Frontend
```
frontend/src/
├── views/
│   ├── OnboardingView.vue     # NEW — API key input + create workspace
│   └── MainView.vue           # MODIFY — show actual orb placeholder + input
├── components/
│   └── Orb.vue                # NEW — visual state orb (placeholder)
├── router/
│   └── index.ts               # MODIFY — add /onboarding route + guard
├── stores/
│   └── app.ts                 # MODIFY — add workspace state
├── services/
│   └── api.ts                 # MODIFY — add workspace API calls
└── types/
    └── index.ts               # MODIFY — add workspace types
```

---

## Specification

### Backend

#### `POST /api/workspace/init`

Request body:
```json
{
  "api_key": "sk-ant-...",
  "workspace_path": "~/Jarvis"    // optional, defaults to ~/Jarvis
}
```

Behavior:
1. Validate API key format (starts with `sk-ant-` and length > 20)
2. Store API key via `keyring.set_password("jarvis", "anthropic_api_key", key)`. Fallback if keyring unavailable: store in `config.json` with a logged warning.
3. Create full folder structure:
   ```
   Jarvis/
   ├── app/
   │   ├── config.json
   │   ├── sessions/
   │   ├── cache/
   │   ├── logs/
   │   └── audio/
   ├── memory/
   │   ├── inbox/
   │   ├── daily/
   │   ├── projects/
   │   ├── people/
   │   ├── areas/
   │   ├── plans/
   │   ├── summaries/
   │   ├── knowledge/
   │   ├── preferences/
   │   ├── examples/
   │   └── attachments/
   ├── graph/
   └── agents/
   ```
4. Write `config.json`:
   ```json
   {
     "version": "0.1.0",
     "created_at": "2026-04-12T...",
     "api_key_set": true,
     "workspace_path": "/Users/user/Jarvis"
   }
   ```
5. Initialize empty SQLite database at `Jarvis/app/jarvis.db` (just create file + schema, details in step 04)
6. Return `{"status": "ok", "workspace_path": "/Users/user/Jarvis"}`

#### `GET /api/workspace/status`

Returns:
```json
{
  "initialized": true,
  "workspace_path": "/Users/user/Jarvis",
  "api_key_set": true
}
```

If workspace doesn't exist yet: `{"initialized": false}`

#### API Key Retrieval (internal)

`workspace_service.get_api_key() -> str | None` — retrieves from keyring, used by Claude service later. Never exposed via API endpoint.

---

### Frontend

#### `OnboardingView.vue`

Layout:
- Centered card on dark background
- Jarvis logo / title at top
- Input field: "Anthropic API key" (type=password)
- Optional: workspace path input (advanced, collapsed by default)
- Button: "Create Jarvis Workspace"
- Loading state while creating
- Error display if creation fails
- On success: redirect to `/main`

#### Router guard

- On app load, call `GET /api/workspace/status`
- If `initialized === false` → redirect to `/onboarding`
- If `initialized === true` → redirect to `/main`
- Store result in `appStore.isInitialized`

#### `MainView.vue` (update)

After onboarding, show:
- `StatusBar` at top
- `Orb` component centered (static placeholder — just a glowing circle)
- Text input at bottom with placeholder "Talk to Jarvis..."
- Input is non-functional yet (no Claude API wired)

#### `Orb.vue`

- A CSS-animated circle/sphere
- Accepts `state` prop: `'idle' | 'listening' | 'thinking' | 'speaking'`
- For now, always in `idle` state
- Visual: subtle pulse animation, accent color glow

---

## Key Decisions

- API key stored via `keyring` package — OS-level security (macOS Keychain, Windows Credential Locker, Linux Secret Service)
- Fallback: if `keyring` fails (e.g., headless Linux), store in `config.json` but log warning
- Workspace path defaults to `~/Jarvis` — user can override if needed
- SQLite file created here but schema populated in step 04
- No API key validation against Anthropic (that comes in step 05)

---

## Acceptance Criteria

- [ ] Opening app with no workspace → redirected to `/onboarding`
- [ ] Entering API key + clicking create → folder tree appears on disk at `~/Jarvis/`
- [ ] `config.json` exists and contains `"api_key_set": true` (not the raw key)
- [ ] API key retrievable via `keyring.get_password("jarvis", "anthropic_api_key")`
- [ ] After creation → redirected to `/main` with Orb visible
- [ ] Refreshing page with existing workspace → goes straight to `/main`
- [ ] `GET /api/workspace/status` returns correct state

---

## Tests

### Backend — `tests/test_workspace_service.py` (~12 tests)
- `test_workspace_not_exists_initially` → service returns `False`
- `test_create_workspace_creates_dirs` → creates `memory/`, `app/`, `agents/`, `.trash/`
- `test_create_workspace_creates_config` → `config.json` exists in `app/`
- `test_config_contains_api_key_set_true` → config has `api_key_set: true`
- `test_config_does_not_contain_raw_key` → raw API key string NOT in config.json
- `test_api_key_stored_in_keyring` → retrievable via `keyring.get_password()`
- `test_workspace_exists_after_creation` → service returns `True`
- `test_create_workspace_twice_raises` → second call raises `WorkspaceExistsError`
- `test_workspace_path_from_settings` → uses `Settings.workspace_path`
- `test_create_workspace_with_empty_key_raises` → empty string → `ValueError`
- `test_create_workspace_with_whitespace_key_raises` → whitespace → `ValueError`
- `test_workspace_folder_permissions` → created dirs are user-only readable

### Backend — `tests/test_workspace_api.py` (~8 tests)
- `test_get_status_no_workspace` → 200 + `{"exists": false}`
- `test_post_init_creates_workspace` → 201 + workspace created
- `test_post_init_returns_structure` → response includes created folder list
- `test_get_status_after_init` → 200 + `{"exists": true}`
- `test_post_init_duplicate` → 409 Conflict
- `test_post_init_missing_api_key` → 422 validation error
- `test_post_init_empty_api_key` → 422 validation error
- `test_api_key_not_in_any_response` → scan all response bodies for key absence

### Frontend — `tests/pages/onboarding.test.ts` (~8 tests)
- Renders API key input field
- Renders "Create Workspace" button
- Button disabled when input empty
- Button enabled when input has text
- Submit sends POST to `/api/workspace/init`
- Success → redirects to `/main`
- API error → shows error message, no redirect
- Network error → shows connection error message

### Frontend — `tests/composables/useAppState.test.ts` additions (~3 tests)
- `isInitialized` becomes `true` after workspace init succeeds
- `checkWorkspaceStatus()` calls GET `/api/workspace/status`
- Initial load: if workspace exists → skip onboarding

### Regression suite (~35 previous tests)
```bash
cd backend && python -m pytest tests/ -v          # ALL backend tests
cd frontend && npx vitest run                      # ALL frontend tests
```

### Run
```bash
cd backend && python -m pytest tests/ -v           # ~31 backend tests
cd frontend && npx vitest run                      # ~35 frontend tests
```

**Expected total: ~66 tests**

---

## Definition of Done

- [ ] All files listed in this step are created
- [ ] `python -m pytest tests/ -v` — all ~31 backend tests pass (including step 01 regression)
- [ ] `npx vitest run` — all ~35 frontend tests pass (including step 02 regression)
- [ ] Manual smoke: onboarding flow creates `~/Jarvis/` with correct structure
- [ ] API key never appears in any REST response
- [ ] Committed with message `feat: step-03 onboarding + workspace`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
