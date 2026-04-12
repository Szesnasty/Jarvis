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

### Backend — `tests/test_settings_api.py` (~8 tests)
- `test_get_settings_200` → 200 + current settings
- `test_get_settings_no_raw_key` → API key NOT in response
- `test_update_api_key` → key stored in keyring, response has `api_key_set: true`
- `test_update_api_key_empty_rejected` → 422
- `test_update_voice_prefs` → voice preferences persisted
- `test_update_voice_prefs_invalid` → 422 for invalid values
- `test_get_settings_includes_voice_prefs` → voice prefs in response
- `test_settings_survives_restart` → settings file persists

### Backend — `tests/test_ingest_service.py` (~14 tests)
- `test_import_markdown_copies_file` → file in memory/ with same content
- `test_import_markdown_indexed` → appears in SQLite index
- `test_import_markdown_preserves_frontmatter` → existing frontmatter kept
- `test_import_txt_converts_to_md` → `.txt` → `.md` with added frontmatter
- `test_import_txt_content_preserved` → body text intact
- `test_import_pdf_extracts_text` → text extracted to `.md`
- `test_import_pdf_indexed` → appears in search
- `test_import_duplicate_path_renames` → conflict resolution: adds suffix
- `test_import_empty_file_handled` → no crash on empty file
- `test_import_large_file_handled` → >1MB file imported (maybe with warning)
- `test_enrich_adds_summary` → summary field added to frontmatter
- `test_enrich_adds_tags` → tags array added to frontmatter
- `test_enrich_preserves_existing_frontmatter` → existing fields unchanged
- `test_enrich_uses_claude` → Claude API called for enrichment

### Backend — `tests/test_token_tracking.py` (~10 tests)
- `test_log_usage_creates_entry` → usage recorded with timestamp
- `test_log_usage_fields` → has input_tokens, output_tokens, model, cost_estimate
- `test_get_usage_today` → returns today's total
- `test_get_usage_by_day` → returns grouped daily totals
- `test_get_usage_empty` → `{total: 0}` when no usage
- `test_budget_warning_at_80pct` → warning event at 80% of daily budget
- `test_budget_warning_at_100pct` → hard warning at 100%
- `test_budget_configurable` → budget from settings
- `test_usage_log_survives_restart` → persistent storage
- `test_usage_api_endpoint` → `GET /api/usage` returns summary

### Backend — `tests/test_error_handling.py` (~6 tests)
- `test_claude_429_returns_graceful_error` → rate limit → user-friendly message
- `test_claude_500_returns_graceful_error` → server error → retryable message
- `test_claude_timeout_returns_error` → timeout → user-friendly message
- `test_invalid_api_key_returns_auth_error` → 401 → "check your key" message
- `test_ws_disconnect_cleans_up` → no resource leak after disconnect
- `test_ws_reconnect_works` → new connection after drop succeeds

### Frontend — `tests/composables/useKeyboard.test.ts` (~8 tests)
- Space key calls `toggleVoice()` when not in input
- Escape calls `cancelAction()`
- Enter sends message when input focused
- Space does NOT toggle voice when typing in input
- Ctrl+K opens command palette (if applicable)
- Key events fire correct handler functions
- Shortcuts disabled in modal/dialog context
- Shortcuts table matches documented shortcuts

### Frontend — `tests/pages/settings.test.ts` (~8 tests)
- Renders API key field (masked: `••••••••`)
- Renders voice preferences toggles
- Submit API key calls PATCH endpoint
- Submit voice prefs calls PATCH endpoint
- Success shows confirmation toast
- Error shows error message
- Token usage summary displayed
- "Open in Obsidian" button rendered

### Frontend — `tests/composables/useWebSocket.test.ts` (~8 tests)
- Connects to correct WS URL
- Receives and parses JSON messages
- Auto-reconnect on close event
- Reconnect uses exponential backoff (100ms, 200ms, 400ms...)
- Max reconnect attempts before giving up
- `isConnected` ref updates on connect/disconnect
- Events buffered during reconnect, sent after connect
- Manual `close()` does NOT trigger reconnect

### Frontend — `tests/components/ImportDialog.test.ts` (~5 tests)
- File picker accepts .md, .txt, .pdf
- Drag-and-drop zone visible
- Upload progress shown
- Success adds note to memory browser
- Error shows message

### Backend — `tests/test_full_regression.py` (~10 tests: end-to-end smoke)
- `test_health_still_works` → GET /api/health = 200
- `test_workspace_status` → GET /api/workspace/status = 200
- `test_create_and_search_note` → POST note → search finds it
- `test_graph_rebuild_after_note` → note → rebuild → node exists
- `test_session_save_and_load` → save → list → load = same messages
- `test_specialist_crud` → create → get → edit → delete
- `test_preferences_round_trip` → set → get → same value
- `test_settings_update` → PATCH → GET → reflects change
- `test_import_and_find` → import file → search → found
- `test_no_api_key_leak_anywhere` → scan all endpoints for key string

### Regression suite
```bash
cd backend && python -m pytest tests/ -v
cd frontend && npx vitest run
```

### Run
```bash
cd backend && python -m pytest tests/ -v           # ~254 backend tests
cd frontend && npx vitest run                      # ~172 frontend tests
```

**Expected total: ~426 tests — full MVP coverage**

---

## Definition of Done

- [ ] All files listed in this step are created
- [ ] `python -m pytest tests/ -v` — all ~254 backend tests pass (FULL regression)
- [ ] `npx vitest run` — all ~172 frontend tests pass (FULL regression)
- [ ] `test_full_regression.py` — all 10 smoke tests pass
- [ ] Manual: keyboard shortcuts, settings, import, Obsidian link
- [ ] Error handling graceful (rate limits, disconnects, bad input)
- [ ] No API key leakage in any endpoint (verified by scan test)
- [ ] Committed with message `feat: step-10 polish + ingest + settings`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
- [ ] 🎉 MVP complete — 426 tests guard the full app

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
