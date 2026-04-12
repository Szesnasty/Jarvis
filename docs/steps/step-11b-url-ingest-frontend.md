# Step 11b — URL Ingest Frontend

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 11 — URL Ingest Pipeline](step-11-url-ingest.md) | **Next**: — | **Index**: [index-spec.md](../index-spec.md)

---

## Goal

Give users two ways to feed Jarvis with URLs: a dedicated import dialog in Memory view, and smart URL detection in the chat input. Both integrate with the `POST /api/memory/ingest-url` backend.

---

## Files to Create / Modify

### Frontend
```
frontend/app/
├── components/
│   └── LinkIngestDialog.vue   # NEW — URL import dialog
├── composables/
│   └── useApi.ts              # MODIFY — add ingestUrl() method
├── pages/
│   └── memory.vue             # MODIFY — add "Import URL" button + dialog
├── components/
│   └── ChatPanel.vue          # MODIFY — URL detection + inline action
└── types/
    └── index.ts               # MODIFY — add UrlIngestResult type
```

---

## Specification

### A. `LinkIngestDialog` Component

A modal/dialog for importing URLs into memory.

```
┌─────────────────────────────────────────────┐
│  📎 Import from URL                    [✕]  │
│─────────────────────────────────────────────│
│                                             │
│  URL:                                       │
│  ┌─────────────────────────────────────┐    │
│  │ https://...                         │    │
│  └─────────────────────────────────────┘    │
│     🎬 YouTube video detected               │
│     ─── or ───                              │
│     📄 Web article detected                 │
│                                             │
│  Save to folder:                            │
│  ┌──────────────┐                           │
│  │ knowledge  ▾ │                           │
│  └──────────────┘                           │
│                                             │
│  ☐ AI Summary (uses API credits)            │
│                                             │
│  ┌─────────────┐                            │
│  │  💾 Import  │                            │
│  └─────────────┘                            │
│                                             │
│  ── Status ──                               │
│  ✅ Saved: knowledge/yt-dQw4w9WgXcQ.md     │
│     2,450 words · 3 tags                    │
│                                             │
└─────────────────────────────────────────────┘
```

**Props**: `modelValue: boolean` (v-model for open/close)
**Emits**: `imported(result)` — when ingest completes

**Behavior**:
1. User pastes/types URL
2. Debounce 300ms → auto-detect type (client-side regex, same as backend)
3. Show type badge: 🎬 YouTube / 📄 Article / ❌ Invalid
4. User selects folder (dropdown: knowledge, inbox, projects, custom)
5. Optional AI summary toggle
6. Click Import → loading spinner → POST `/api/memory/ingest-url`
7. On success: show green result with path + word count
8. On error: show red message

**Validation**:
- Disable Import button until valid URL detected
- Show error inline for invalid URLs

---

### B. Memory Page Integration

In `memory.vue`, add "Import URL" button next to the existing "Import File":

```vue
<div class="memory__actions">
  <button @click="showFileImport = true">📁 Import File</button>
  <button @click="showUrlImport = true">🔗 Import URL</button>
</div>

<LinkIngestDialog v-model="showUrlImport" @imported="refreshNotes" />
```

---

### C. ChatPanel URL Detection

When user types/pastes a URL in the chat input, show an inline action bar:

```
┌──────────────────────────────────────────────────┐
│ 🔗 https://youtube.com/watch?v=abc123              │
│    [Save to memory]  [Send as message]              │
└──────────────────────────────────────────────────┘
```

**Implementation**:

```typescript
// In ChatPanel.vue or a composable
const URL_RE = /https?:\/\/[^\s]+/

const detectedUrl = computed(() => {
  const match = inputText.value.match(URL_RE)
  return match ? match[0] : null
})

const urlType = computed(() => {
  if (!detectedUrl.value) return null
  const ytMatch = detectedUrl.value.match(
    /(?:youtube\.com\/watch\?.*v=|youtu\.be\/|youtube\.com\/shorts\/)([\w-]{11})/
  )
  return ytMatch ? 'youtube' : 'webpage'
})
```

**Behavior**:
1. Detect URL while typing (computed, not watch — no side effects)
2. If URL detected → show action bar above input
3. "Save to memory" → call `ingestUrl()` → show toast on success
4. "Send as message" → send as normal message (Claude may use `ingest_url` tool)
5. If user just hits Enter → send as normal message (no special behavior)
6. Action bar disappears when URL is removed from input

**Rules**:
- Don't block normal message flow — URL detection is a convenience, not a gate
- Don't auto-ingest — always require explicit user action
- Show inline, don't open a modal (keep chat flow fast)

---

### D. Types

```typescript
// types/index.ts
interface UrlIngestResult {
  path: string
  title: string
  type: 'youtube' | 'article'
  source: string
  word_count: number
  summary?: string
}
```

---

### E. API Integration

```typescript
// composables/useApi.ts
async function ingestUrl(
  url: string,
  folder = 'knowledge',
  summarize = false
): Promise<UrlIngestResult> {
  return post('/api/memory/ingest-url', { url, folder, summarize })
}
```

---

### F. Tests

```
frontend/tests/
├── components/
│   └── LinkIngestDialog.test.ts   # NEW
```

Test cases:
1. Dialog renders with URL input, folder select, summary toggle
2. URL type detection — YouTube URLs show video badge
3. URL type detection — regular URLs show article badge
4. Invalid URLs disable Import button
5. Successful import shows result message
6. Error state shows error message
7. ChatPanel URL detection — computed detects pasted URL
8. ChatPanel URL detection — no false positives on normal text
