# Step 02 — Frontend Initialization (Nuxt 3)

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 01 — Backend Init](step-01-backend-init.md) | **Next**: [Step 03 — Onboarding](step-03-onboarding-workspace.md) | **Index**: [index-spec.md](../index-spec.md)

---

## Goal

Create a minimal Nuxt 3 frontend with TypeScript. Nuxt gives us file-based routing, auto-imports, and first-class TS support out of the box. The app should show a placeholder page and proxy API calls to the backend.

---

## Files to Create

```
frontend/
├── package.json
├── nuxt.config.ts              # Nuxt config + API proxy
├── tsconfig.json               # Extends .nuxt/tsconfig.json
├── app.vue                     # Root layout with <NuxtPage>
├── pages/
│   ├── index.vue               # Redirect to /main
│   └── main.vue                # Placeholder main page
├── components/
│   └── StatusBar.vue           # Top bar with backend status
├── composables/
│   ├── useApi.ts               # API client (useFetch wrapper)
│   └── useAppState.ts          # Global app state (replaces Pinia store)
├── types/
│   └── index.ts                # Shared TypeScript types
├── assets/
│   └── css/
│       └── main.css            # Base styles + CSS reset
├── server/
│   └── tsconfig.json
└── public/
```

---

## Specification

### 1. Initialize Nuxt

```bash
npx nuxi@latest init frontend
```

Then customize. Key deps (pinned after install):
```json
{
  "dependencies": {
    "nuxt": "^3.15"
  },
  "devDependencies": {
    "@nuxt/test-utils": "^3.15",
    "@vue/test-utils": "^2.4",
    "vitest": "^2.0",
    "happy-dom": "^15.0"
  }
}
```

### 2. `nuxt.config.ts`

- Proxy `/api` to `http://127.0.0.1:8000` (FastAPI backend) via `routeRules`
- Enable TypeScript strict mode
- Register global CSS
- SSR disabled (SPA mode) — this is a local desktop app

```typescript
export default defineNuxtConfig({
  ssr: false,
  devtools: { enabled: false },
  css: ['~/assets/css/main.css'],
  routeRules: {
    '/api/**': { proxy: 'http://127.0.0.1:8000/api/**' },
  },
  typescript: {
    strict: true,
  },
})
```

### 3. Pages (file-based routing)

- `pages/index.vue` — redirects to `/main` via `navigateTo('/main')`
- `pages/main.vue` — placeholder layout with StatusBar + title

Later steps add: `pages/onboarding.vue`, `pages/memory.vue`, `pages/graph.vue`, `pages/specialists.vue`, `pages/settings.vue`

### 4. Composable: `useAppState()`

Replaces Pinia store — uses Nuxt's `useState()` for SSR-safe shared state:
- `isInitialized: boolean` — whether workspace exists
- `backendStatus: 'unknown' | 'online' | 'offline'`
- `checkHealth()` — calls `GET /api/health`, updates `backendStatus`

### 5. Composable: `useApi()`

Thin wrapper around `$fetch`:
- `fetchHealth(): Promise<HealthResponse>` — calls `GET /api/health`
- Typed error class: `ApiError` with `status` and `message`
- Uses Nuxt's built-in `$fetch` (ohmyfetch) — no manual fetch needed

### 6. `pages/main.vue`

Placeholder layout:
- StatusBar at top (auto-imported component)
- Centered text: "Jarvis" + backend status indicator
- Text input at bottom (non-functional yet)

### 7. `assets/css/main.css`

- CSS reset (box-sizing, margin, padding)
- Dark background (`#0a0a0f`)
- Light text
- System font stack

---

## Key Decisions

- **Nuxt over plain Vue**: file-based routing, auto-imports (no manual imports for composables/components), built-in TypeScript, built-in proxy via `routeRules`
- **SPA mode (`ssr: false`)**: this is a local app, no need for SSR
- **No Pinia**: Nuxt's `useState()` composable is sufficient for shared state in SPA mode
- **`$fetch` over `fetch`**: Nuxt's `$fetch` auto-serializes, has better error handling, works with proxy
- **No Tailwind yet** — start with plain CSS
- All API calls go through `useApi()` composable — components never call `$fetch` directly

---

## Tests

### Files to Create
```
frontend/
├── vitest.config.ts
└── tests/
    ├── components/
    │   └── StatusBar.test.ts
    ├── composables/
    │   ├── useApi.test.ts
    │   └── useAppState.test.ts
    ├── pages/
    │   ├── index.test.ts
    │   └── main.test.ts
    └── setup.ts                 # Global test setup (mocks)
```

### vitest.config.ts
```typescript
import { defineVitestConfig } from '@nuxt/test-utils/config'

export default defineVitestConfig({})
```

### Test Cases (~20 tests)

**`tests/composables/useApi.test.ts`** (6 tests)
- `fetchHealth()` returns `{ status: 'ok', version: '0.1.0' }` on 200
- `fetchHealth()` throws `ApiError` with status code on 500
- `fetchHealth()` throws `ApiError` with message on 404
- `fetchHealth()` throws on network error (fetch rejects)
- `ApiError` has correct `status` and `message` properties
- `ApiError` is instanceof `Error`

**`tests/composables/useAppState.test.ts`** (7 tests)
- Initial `isInitialized` is `false`
- Initial `backendStatus` is `'unknown'`
- `checkHealth()` sets `backendStatus = 'online'` when API returns 200
- `checkHealth()` sets `backendStatus = 'offline'` when API throws
- `checkHealth()` does not change `isInitialized`
- Calling `checkHealth()` twice — latest result wins
- State persists across multiple calls to `useAppState()` (shared via useState)

**`tests/components/StatusBar.test.ts`** (5 tests)
- Renders "Jarvis" label text
- Shows status text from appState
- Applies `.online` CSS class when status is `'online'`
- Applies `.offline` CSS class when status is `'offline'`
- Applies `.unknown` CSS class when status is `'unknown'`

**`tests/pages/main.test.ts`** (5 tests)
- Page mounts without errors
- Renders StatusBar component
- Renders "Jarvis" heading
- Renders text input element
- Input is disabled (placeholder, not functional yet)

**`tests/pages/index.test.ts`** (1 test)
- Visiting `/` redirects to `/main`

### Regression: Backend still works
After step-02, backend tests must still pass:
```bash
cd backend && python -m pytest tests/ -v
```

### Run
```bash
cd frontend && npx vitest run          # ~24 tests
cd backend && python -m pytest -v      # regression (~11 tests)
```

**Expected total: ~35 tests across both stacks**

---

## Definition of Done

- [ ] `npm install && npm run dev` starts on `localhost:3000`
- [ ] Main page placeholder visible in browser
- [ ] StatusBar shows backend status (online/offline)
- [ ] `npx nuxi typecheck` passes
- [ ] `npx vitest run` — all 24 frontend tests pass
- [ ] `cd backend && python -m pytest -v` — all backend tests still pass
- [ ] All components use `<script setup lang="ts">`
- [ ] Committed with message `feat: step-02 frontend init (nuxt)`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
