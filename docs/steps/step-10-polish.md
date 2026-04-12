# Step 10 — Polish, Obsidian, Caching, Ingest

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 09 — Specialists](step-09-specialists.md) | **Next**: — (MVP complete) | **Index**: [index-spec.md](../index-spec.md)

---

## Goal

Polish the MVP to production quality. Add Obsidian integration helper, token usage optimization, file ingest pipeline, and visual refinements.

---

## Sub-tasks

This step covers multiple independent improvements. Each can be implemented in any order.

---

### A. Orb / HUD Visual Polish

**Files**: `frontend/src/components/Orb.vue`, `main.css`

Current orb is a placeholder. Upgrade to:
- Smooth CSS-only animated orb with gradient
- State transitions with easing (idle → listening → thinking → speaking)
- Subtle particle or ring effects (CSS `box-shadow` animations, no canvas)
- Premium feel: glass morphism or soft glow aesthetic
- Dark theme consistency across all views

**Rules**:
- No canvas/WebGL — CSS only
- No heavy animation libraries
- Must work at 60fps on mid-range hardware
- Orb size responsive to viewport

---

### B. Improved UX + Responsiveness

**Files**: Multiple component files, `main.css`

- Keyboard shortcut: `Space` to toggle voice (when input not focused)
- Keyboard shortcut: `Escape` to cancel current action
- `Enter` to send message, `Shift+Enter` for newline
- Loading skeletons for note lists and graph
- Toast notifications for: note saved, specialist activated, error
- Responsive layout: works on 1024px+ screens (no mobile yet, but no broken layouts)
- Smooth page transitions between views
- Empty states: helpful messages when no notes / no specialists / empty graph

---

### C. Settings View

**Files**: `frontend/src/views/SettingsView.vue`, backend endpoints

Settings page with:
- **API key**: show masked key, button to update
- **Workspace path**: display current path
- **Voice settings**: toggle auto-speak, select TTS voice (from browser voices)
- **Reindex memory**: button to trigger full SQLite reindex
- **Rebuild graph**: button to trigger graph rebuild
- **Export config**: download `config.json`
- **Danger zone**: reset workspace (with confirmation)

---

### D. Obsidian Integration Helper

**Files**: `frontend/src/components/ObsidianHelper.vue`, backend utility

Provide a helper that:
1. Detects if Obsidian is installed (check for `obsidian://` URI scheme support)
2. Shows button: "Open memory in Obsidian"
3. On click: opens `obsidian://open?vault=Jarvis` (if vault is registered) or shows instructions
4. Instructions panel explaining:
   - Open Obsidian → "Open folder as vault" → select `Jarvis/memory/`
   - Recommended Obsidian plugins: Graph view, Tags, Daily notes
5. Note compatibility check: verify all notes have valid frontmatter

**No Obsidian dependency anywhere** — this is purely a convenience helper.

---

### E. Token Usage Optimization

**Files**: `backend/services/context_builder.py`, `claude.py`, `session_service.py`

Improvements:
1. **Token counting**: use `anthropic.count_tokens()` or tiktoken to track context size
2. **Context budget**: hard limit of 3000 tokens for context, 1000 for preferences + specialist
3. **Smart truncation**: truncate individual notes at section boundaries, not mid-sentence
4. **Session compression**: after 10 messages, summarize older messages into a single context block
5. **Cache**: store recent retrieval results in SQLite cache with TTL (5 minutes)
6. **Metrics**: log token usage per request to `app/logs/token_usage.jsonl`

```python
# Token budget allocation
TOTAL_BUDGET = 4000  # tokens for non-response content
CONTEXT_BUDGET = 2500
PREFERENCES_BUDGET = 500
SPECIALIST_BUDGET = 500
HISTORY_BUDGET = 500  # for compressed older messages
```

---

### F. File Ingest Pipeline

**Files**: `backend/services/ingest.py`, `backend/routers/memory.py` (new endpoint)

Two-stage ingest for importing files into Jarvis memory:

#### Fast Ingest (no AI)

```python
async def fast_ingest(file_path: Path, target_folder: str) -> IngestResult:
    """Import a file into memory without AI. Returns metadata."""
    # 1. Detect file type
    # 2. Extract text (Markdown passthrough, PDF via pdfplumber, TXT direct)
    # 3. Generate frontmatter: title from filename, date, source path
    # 4. Split into sections if large (>2000 words → multiple notes)
    # 5. Save to memory/{target_folder}/
    # 6. Update SQLite index
    # 7. Update graph with new note nodes
    ...
```

Supported MVP formats: `.md`, `.txt`, `.pdf` (via `pdfplumber`)

#### Smart Enrich (optional AI)

```python
async def smart_enrich(note_path: str) -> EnrichResult:
    """Use Claude to enhance an ingested note. Requires API call."""
    # 1. Read note
    # 2. Ask Claude to: generate summary, extract entities, suggest tags
    # 3. Update frontmatter with new tags/entities
    # 4. Save summary as linked note
    # 5. Update graph
    ...
```

**Smart enrich is always opt-in** — never runs automatically.

#### Ingest API

`POST /api/memory/ingest` — multipart file upload
- `file`: the file to ingest
- `folder`: target memory folder (default: `knowledge`)
- `enrich`: boolean, whether to run smart enrich (default: false)

#### Frontend

Add "Import file" button to MemoryView:
- File picker (accept: .md, .txt, .pdf)
- Target folder selector
- Optional: "AI Enrich" toggle
- Progress indicator

---

### G. Error Handling Hardening

**Files**: Multiple backend + frontend files

Backend:
- Global exception handler for unhandled exceptions → proper JSON error response
- Structured logging to `app/logs/jarvis.log` (rotation, max 10MB)
- Graceful handling of Claude API errors: rate limit, invalid key, timeout
- File system error handling: disk full, permission denied, missing files

Frontend:
- Global error boundary component
- API error interceptor with user-friendly messages
- Offline detection: show banner when backend unreachable
- WebSocket reconnection with exponential backoff

---

## Key Decisions

- Visual polish is CSS-only — no heavy dependencies
- Token optimization is measurement-driven — log first, optimize based on data
- Ingest pipeline is conservative: fast ingest by default, AI enrich only on request
- PDF support via `pdfplumber` (add to `requirements.txt`)
- Obsidian is a helper, never a requirement
- Error handling is defensive but not paranoid — trust internal data, validate at boundaries

---

## Acceptance Criteria

- [ ] Orb animations are smooth and visually polished
- [ ] Keyboard shortcuts work (Space for voice, Escape to cancel, Enter to send)
- [ ] Settings view allows updating API key and voice preferences
- [ ] "Open in Obsidian" button works when Obsidian is installed
- [ ] Token usage logged and stays within budget
- [ ] Import .md, .txt, .pdf into memory via UI
- [ ] Smart enrich produces summary + tags for imported files
- [ ] Error messages are user-friendly, not stack traces
- [ ] App handles Claude API rate limits gracefully
- [ ] App reconnects WebSocket automatically after disconnect

---

## Tests

### Backend — `tests/test_settings_api.py`
- `test_get_settings` → 200 + current settings (no raw key)
- `test_update_api_key` → key stored in keyring
- `test_update_voice_prefs` → preferences persisted

### Backend — `tests/test_ingest_service.py`
- `test_import_markdown` → file copied + indexed
- `test_import_txt` → converted to .md + indexed
- `test_import_pdf` → text extracted + indexed
- `test_enrich_note` → summary + tags added to frontmatter

### Backend — `tests/test_token_tracking.py`
- `test_log_token_usage` → usage recorded in log
- `test_get_usage_summary` → returns totals by day
- `test_budget_warning` → warning event when approaching limit

### Frontend — `src/__tests__/composables/useKeyboard.test.ts`
- Space key toggles voice
- Escape cancels current action
- Enter sends message
- Shortcuts disabled when input focused (except Enter)

### Frontend — `src/__tests__/views/SettingsView.test.ts`
- Renders settings form
- Submit updates settings via API
- API key field masked

### Frontend — `src/__tests__/composables/useWebSocket.test.ts`
- Auto-reconnect after disconnect
- Reconnect with exponential backoff
- Events buffered during reconnect

### Run
```bash
cd backend && python -m pytest tests/test_settings_api.py tests/test_ingest_service.py tests/test_token_tracking.py -v
cd frontend && npx vitest run
```

---

## Definition of Done

- [ ] All files listed in this step are created
- [ ] `python -m pytest` — full suite passes
- [ ] `npx vitest run` — full suite passes
- [ ] Manual: keyboard shortcuts, settings, import, Obsidian link
- [ ] Error handling graceful (rate limits, disconnects)
- [ ] Committed with message `feat: step-10 polish + ingest + settings`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
- [ ] 🎉 MVP complete

---

## After This Step

**MVP is complete.**

The system supports:
- Voice and text conversation with Claude
- Local Markdown memory with search
- Knowledge graph with visualization
- Custom specialists
- File ingest
- Session persistence
- Obsidian compatibility

Future directions (post-MVP):
- Better TTS (Kokoro.js, Piper)
- Better STT (local Whisper)
- Vector search layer
- AI-inferred graph relations
- Mobile-friendly layout
- Multi-language support
- Specialist marketplace / sharing
