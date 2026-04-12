# Step 02 — Frontend Initialization (Vue + Vite)

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 01 — Backend Init](step-01-backend-init.md) | **Next**: [Step 03 — Onboarding](step-03-onboarding-workspace.md) | **Index**: [index-spec.md](../index-spec.md)

---

## Goal

Create a minimal Vue 3 frontend with TypeScript, Vite, Vue Router, and Pinia. It should show a placeholder page and proxy API calls to the backend.

---

## Files to Create

```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── index.html
├── env.d.ts
├── src/
│   ├── main.ts                # App entry point
│   ├── App.vue                # Root component with <RouterView>
│   ├── router/
│   │   └── index.ts           # Vue Router setup
│   ├── stores/
│   │   └── app.ts             # Global app store (Pinia)
│   ├── views/
│   │   └── MainView.vue       # Placeholder main view
│   ├── components/
│   │   └── StatusBar.vue      # Simple top bar with status text
│   ├── services/
│   │   └── api.ts             # API client (fetch wrapper)
│   ├── types/
│   │   └── index.ts           # Shared TypeScript types
│   └── assets/
│       └── styles/
│           └── main.css        # Base styles + CSS reset
└── public/
```

---

## Specification

### 1. Scaffold with Vite

Initialize using `npm create vue@latest` conventions but create files manually to keep full control.

Dependencies:
```json
{
  "dependencies": {
    "vue": "^3.5",
    "vue-router": "^4.4",
    "pinia": "^2.2"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0",
    "typescript": "~5.6",
    "vite": "^6.0",
    "vue-tsc": "^2.0"
  }
}
```

### 2. `vite.config.ts`

- Vue plugin
- Proxy `/api` to `http://127.0.0.1:8000` (the FastAPI backend)
- Resolve `@` alias to `./src`

```typescript
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    }
  }
}
```

### 3. Router (`router/index.ts`)

Two routes for now:
- `/` → redirect to `/main`
- `/main` → `MainView.vue`

Later steps will add `/onboarding`, `/memory`, `/graph`, `/specialists`, `/settings`.

### 4. App Store (`stores/app.ts`)

Pinia store with:
- `isInitialized: boolean` — whether workspace exists
- `backendStatus: 'unknown' | 'online' | 'offline'`
- `checkHealth()` action — calls `GET /api/health`, updates `backendStatus`

### 5. API Service (`services/api.ts`)

- Base URL: empty string (Vite proxy handles `/api` prefix)
- `fetchHealth(): Promise<HealthResponse>` — calls `GET /api/health`
- Typed error class: `ApiError` with `status` and `message`

### 6. `MainView.vue`

Placeholder layout:
- StatusBar at top
- Centered text: "Jarvis" + backend status indicator
- Text input at bottom (non-functional yet)

### 7. `main.css`

- CSS reset (box-sizing, margin, padding)
- Dark background (`#0a0a0f` or similar)
- Light text
- System font stack
- No framework — keep it simple

---

## Key Decisions

- Vite proxy eliminates CORS issues during development
- No Tailwind yet — start with plain CSS to avoid premature dependency
- Router uses `createWebHistory` (not hash mode)
- All API calls go through `services/api.ts` — components never use `fetch` directly

---

## Tests

### Files to Create
```
frontend/
├── vitest.config.ts
└── src/
    └── __tests__/
        ├── App.test.ts              # App mounts correctly
        ├── stores/app.test.ts       # App store + health check
        └── services/api.test.ts     # API client tests
```

Add dev dependencies:
```json
"vitest": "^2.0",
"@vue/test-utils": "^2.4",
"jsdom": "^25.0"
```

### Test Cases

**`App.test.ts`**
- App component mounts without errors
- RouterView is rendered

**`stores/app.test.ts`**
- Initial state: `isInitialized = false`, `backendStatus = 'unknown'`
- `checkHealth()` sets `backendStatus = 'online'` on success
- `checkHealth()` sets `backendStatus = 'offline'` on fetch error

**`services/api.test.ts`**
- `fetchHealth()` returns parsed HealthResponse on 200
- `fetchHealth()` throws ApiError on non-200

### Run
```bash
cd frontend && npx vitest run
```

---

## Definition of Done

- [ ] `npm install && npm run dev` starts on `localhost:5173`
- [ ] MainView placeholder visible in browser
- [ ] StatusBar shows backend status (online/offline)
- [ ] `npm run type-check` passes
- [ ] `npx vitest run` — all tests pass
- [ ] All components use `<script setup lang="ts">`
- [ ] Committed with message `feat: step-02 frontend init`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
