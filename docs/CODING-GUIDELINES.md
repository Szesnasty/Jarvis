# Jarvis — Coding Guidelines

> **Every spec file and every line of code in this project must follow these rules.**
> When in doubt, choose the simpler option.

---

## Navigation

- [JARVIS-PLAN.md](JARVIS-PLAN.md) — Full project plan
- [index-spec.md](index-spec.md) — Master implementation tracking

---

## 1. General Principles

### 1.1 Simplicity Over Cleverness
- Write code that a junior developer can read and understand
- No clever one-liners if a 3-line version is clearer
- No premature abstraction — extract only when you see real duplication (rule of 3)

### 1.2 Small Files, Single Responsibility
- **Python**: one module = one responsibility, ideally < 150 lines
- **Vue**: one component = one visual/logical unit, ideally < 200 lines of `<script>` + `<template>`
- If a file grows beyond these limits, split it

### 1.3 Descriptive Names
- Variables, functions, and files must describe their purpose
- No abbreviations except universally known ones (`id`, `url`, `db`, `config`)
- Bad: `proc_d()`, `tmp`, `x`, `mgr`
- Good: `process_daily_notes()`, `unprocessed_count`, `note_path`, `memory_service`

### 1.4 Early Return Pattern
- Always handle error/edge cases first, then the happy path
- Avoid deep nesting — flatten with early returns

```python
# BAD
def get_note(path):
    if path:
        if path.exists():
            if path.suffix == '.md':
                return path.read_text()
            else:
                raise ValueError("Not markdown")
        else:
            raise FileNotFoundError()
    else:
        raise ValueError("No path")

# GOOD
def get_note(path: Path) -> str:
    if not path:
        raise ValueError("No path")
    if not path.exists():
        raise FileNotFoundError(f"Note not found: {path}")
    if path.suffix != '.md':
        raise ValueError(f"Not a markdown file: {path}")
    return path.read_text()
```

### 1.5 No Dead Code
- No commented-out code in commits
- No unused imports
- No placeholder functions that do nothing

### 1.6 Fail Loudly at Boundaries, Trust Internally
- Validate inputs at API/router level (system boundary)
- Inside services, trust that data is already validated — don't double-check
- Use Pydantic models for all API input/output validation

---

## 2. Python / FastAPI Rules

### 2.1 Project Structure
```
backend/
  main.py              # App factory + startup, nothing else
  config.py            # Settings via pydantic-settings
  routers/             # One file per resource/domain
  services/            # Business logic, one file per domain
  models/              # Pydantic schemas + DB models
  utils/               # Pure utility functions (no state, no side effects)
```

### 2.2 Typing
- All function signatures must have type hints
- Use `str`, `int`, `Path`, `list[str]`, `dict[str, Any]` — not `typing.List`, `typing.Dict`
- Return types are mandatory

```python
# GOOD
def search_notes(query: str, limit: int = 10) -> list[NoteMetadata]:
    ...

# BAD
def search_notes(query, limit=10):
    ...
```

### 2.3 Async
- All route handlers: `async def`
- All I/O operations (file, DB, HTTP): use async variants
- Use `aiosqlite` for SQLite, `httpx` or `anthropic` async client for HTTP
- Never call blocking I/O inside an async function without `run_in_executor`

### 2.4 Router Pattern
```python
# routers/memory.py
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/memory", tags=["memory"])

@router.get("/notes")
async def list_notes(folder: str = "") -> list[NoteMetadata]:
    notes = await memory_service.list_notes(folder)
    return notes
```

- Routers: thin — validate input, call service, return response
- Services: all business logic
- Routers never import other routers

### 2.5 Error Handling
- Use `HTTPException` in routers only
- Services raise domain exceptions (custom or built-in)
- Routers catch service exceptions and convert to HTTP responses

```python
# services/memory_service.py
class NoteNotFoundError(Exception):
    pass

async def get_note(path: str) -> NoteContent:
    full_path = resolve_note_path(path)
    if not full_path.exists():
        raise NoteNotFoundError(f"Note not found: {path}")
    return await read_note(full_path)

# routers/memory.py
@router.get("/notes/{path:path}")
async def get_note(path: str):
    try:
        return await memory_service.get_note(path)
    except NoteNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")
```

### 2.6 Dependencies
- Use FastAPI's dependency injection for shared resources (DB, config, etc.)
- Never use global mutable state — pass dependencies explicitly

### 2.7 Naming Conventions
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions and variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: prefix with `_` (single underscore)

### 2.8 Imports
- Standard library first, then third-party, then local — separated by blank lines
- Absolute imports only (no relative imports)

---

## 3. Vue 3 / TypeScript Rules

### 3.1 Component Style
- Always use `<script setup lang="ts">` (Composition API)
- Never use Options API
- Order in `.vue` file: `<script setup>` → `<template>` → `<style>`

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Note } from '@/types'

const props = defineProps<{
  note: Note
}>()

const isExpanded = ref(false)
const title = computed(() => props.note.title || 'Untitled')
</script>

<template>
  <div class="note-card" @click="isExpanded = !isExpanded">
    <h3>{{ title }}</h3>
    <p v-if="isExpanded">{{ note.content }}</p>
  </div>
</template>

<style scoped>
.note-card {
  /* styles */
}
</style>
```

### 3.2 Component Size
- One component = one responsibility
- If template > 80 lines, split into child components
- If script > 100 lines, extract logic into composable

### 3.3 Composables
- Extract reusable stateful logic into `composables/useXxx.ts`
- Composable = function that returns reactive state + methods
- Name pattern: `useVoice`, `useChat`, `useWebSocket`

```typescript
// composables/useVoice.ts
export function useVoice() {
  const state = ref<'idle' | 'listening' | 'thinking' | 'speaking'>('idle')
  const transcript = ref('')

  function startListening() {
    // ...
  }

  function stopListening() {
    // ...
  }

  return { state, transcript, startListening, stopListening }
}
```

### 3.4 Typing
- All props must be typed with `defineProps<{ ... }>()`
- All emits must be typed with `defineEmits<{ ... }>()`
- All refs must have explicit type when not obvious: `ref<string>('')`
- API responses must have TypeScript interfaces
- No `any` except at system boundaries (external API responses that are genuinely unknown)

### 3.5 State Management (Pinia)
- One store per domain: `app`, `chat`, `voice`, `memory`
- Stores hold only shared state — local component state stays in the component
- Actions handle async logic, getters are computed derivations

```typescript
// stores/chat.ts
export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)

  async function sendMessage(content: string) {
    isLoading.value = true
    try {
      // ...
    } finally {
      isLoading.value = false
    }
  }

  return { messages, isLoading, sendMessage }
})
```

### 3.6 API Calls
- All API calls go through `services/api.ts` — components never call `fetch` directly
- Use typed request/response interfaces
- Handle errors at the call site, not inside the API service

```typescript
// services/api.ts
const BASE_URL = '/api'

export async function fetchNotes(folder: string): Promise<Note[]> {
  const response = await fetch(`${BASE_URL}/memory/notes?folder=${folder}`)
  if (!response.ok) {
    throw new ApiError(response.status, await response.text())
  }
  return response.json()
}
```

### 3.7 Naming Conventions
- Components: `PascalCase.vue` (`ChatPanel.vue`, `VoiceButton.vue`)
- Composables: `camelCase.ts` with `use` prefix (`useVoice.ts`)
- Stores: `camelCase.ts` (`chat.ts`)
- Types/interfaces: `PascalCase` (`NoteMetadata`, `ChatMessage`)
- Variables, functions: `camelCase`
- CSS classes: `kebab-case`

### 3.8 Template Rules
- Use `v-if` / `v-else` — avoid `v-show` unless performance-critical
- Always use `:key` on `v-for`
- Prefer `@click` over `v-on:click`
- Max 3 attributes on single line, then multiline

```html
<!-- Single line OK -->
<button class="btn" @click="save" :disabled="isLoading">Save</button>

<!-- Multiline when many attrs -->
<input
  v-model="searchQuery"
  type="text"
  placeholder="Search notes..."
  class="search-input"
  @keydown.enter="search"
/>
```

---

## 4. Shared Rules

### 4.1 Git Commits
- One logical change per commit
- Format: `type: short description`
- Types: `feat`, `fix`, `refactor`, `docs`, `style`, `test`, `chore`
- Examples: `feat: add workspace initialization endpoint`, `fix: handle empty note path`

### 4.2 No Magic Numbers/Strings
```python
# BAD
if len(context) > 4096:
    ...

# GOOD
MAX_CONTEXT_TOKENS = 4096
if len(context) > MAX_CONTEXT_TOKENS:
    ...
```

### 4.3 Configuration
- All configurable values in `config.py` (backend) or environment variables
- Never hardcode paths, URLs, API endpoints, or limits inline

### 4.4 File Organization Heuristic
- If you need to scroll to find a function → file is too long → split it
- If you import from more than 5 local modules → maybe your module does too much
- If a function takes more than 4 parameters → consider a dataclass/model

### 4.5 Comments
- Don't comment *what* — the code should be clear enough
- Comment *why* when the reason isn't obvious
- Use docstrings only for public API functions that other modules call

### 4.6 Testing
- Test files mirror source structure: `services/memory_service.py` → `tests/test_memory_service.py`
- Test function names describe behavior: `test_search_notes_returns_empty_list_when_no_match`
- No testing of implementation details — test behavior/output
- **Every step must end with passing tests before commit**

#### Backend (pytest)
- Framework: `pytest` + `pytest-anyio` + `httpx` (for async FastAPI testing)
- Config: `pytest.ini` at `backend/` root
- Test client via `httpx.AsyncClient` with `ASGITransport`
- Use fixtures in `conftest.py` for shared setup (app, client, tmp workspace)
- Mark async tests with `@pytest.mark.anyio`
- Naming: `test_<function>_<scenario>` e.g. `test_create_note_sets_frontmatter`
- Run: `cd backend && python -m pytest -v`

```python
# tests/conftest.py pattern
import pytest
from httpx import ASGITransport, AsyncClient
from main import create_app

@pytest.fixture
async def client(tmp_path):
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

#### Frontend (vitest)
- Framework: `vitest` + `@vue/test-utils` + `jsdom`
- Config: `vitest.config.ts` at `frontend/` root
- Test location: `src/__tests__/` mirroring `src/` structure
- Use `mount()` for component tests from `@vue/test-utils`
- Use `vi.fn()` / `vi.mock()` for mocking
- Naming: `describe('ComponentName')` + `it('does X when Y')`
- Run: `cd frontend && npx vitest run`

```typescript
// src/__tests__/components/Example.test.ts pattern
import { mount } from '@vue/test-utils'
import Example from '@/components/Example.vue'

describe('Example', () => {
  it('renders title', () => {
    const wrapper = mount(Example, { props: { title: 'Hello' } })
    expect(wrapper.text()).toContain('Hello')
  })
})
```

---

## 5. Source of Truth Reminder

These rules apply everywhere in this project:

1. **Markdown files in `Jarvis/memory/` are the source of truth** — never SQLite
2. **SQLite is a cache/index** — if deleted, it must be rebuildable
3. **Graph is a derived layer** — if deleted, it can be regenerated
4. **API key never stored in plain text** — use OS keychain where possible
5. **Voice layer is behind interfaces** — never hardwire a specific provider

---

## 6. Spec File Convention

Every step file in `docs/steps/` must:

1. Link to this guidelines file and [index-spec.md](index-spec.md) at the top
2. Link to previous/next step
3. List exact files to create or modify
4. Include **## Tests** section with specific test files + test cases
5. Include **## Definition of Done** checklist (code, tests pass, committed, index updated)
6. Not exceed one logical milestone per file
