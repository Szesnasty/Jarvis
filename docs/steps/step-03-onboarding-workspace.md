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

### Backend — `tests/test_onboarding.py`
- `test_workspace_status_no_workspace` → returns `{"exists": false}`
- `test_create_workspace` → creates folder tree at configured path
- `test_create_workspace_stores_api_key` → key in keyring, not in config.json
- `test_workspace_status_after_creation` → returns `{"exists": true}`
- `test_create_workspace_already_exists` → returns 409 Conflict
- `test_config_json_no_raw_key` → config.json has `api_key_set: true`, no key value

### Frontend — `src/__tests__/views/OnboardingView.test.ts`
- Renders onboarding form when no workspace
- Submit calls API and redirects to `/main`
- Shows error on API failure

### Run
```bash
cd backend && python -m pytest tests/test_onboarding.py -v
cd frontend && npx vitest run src/__tests__/views/OnboardingView.test.ts
```

---

## Definition of Done

- [ ] All files listed in this step are created
- [ ] `python -m pytest tests/test_onboarding.py` — all pass
- [ ] `npx vitest run` — all pass
- [ ] Manual smoke: onboarding flow creates `~/Jarvis/` with correct structure
- [ ] Committed with message `feat: step-03 onboarding + workspace`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
