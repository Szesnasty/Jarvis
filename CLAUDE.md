# JARVIS — Full Project Plan

## 1. What Is Jarvis

Jarvis is a **voice-first personal memory, planning, and knowledge system**.

It is **not**:
- A coding tool
- A Claude Code wrapper
- A generic chatbot with memory

It **is**:
- A voice interface to the user's own local memory
- A personal operating system / second brain / voice memory cockpit
- Built on local Markdown files, compatible with Obsidian
- Powered by Claude API
- Extended with a knowledge graph layer
- Customizable through user-created specialists

**Core thesis**: AI doesn't remember "on its own" — it works on memory that **belongs to the user**.

---

## 1a. Source of Truth Doctrine

**This is a hard rule for the entire codebase:**

- **Source of truth = Markdown files in `Jarvis/memory/`**
- **SQLite = operational index and cache, never the canonical store.** If SQLite is deleted, it must be fully rebuildable from Markdown files.
- **Graph = derived layer, rebuildable from memory.** If `graph.json` is deleted, it can be regenerated.
- **Config = `Jarvis/app/config.json`** for metadata and flags only.

Every write operation that affects user knowledge must end with a Markdown file on disk. SQLite and graph are acceleration layers, not storage layers.

---

## 2. Target Users

- People organizing life, projects, and plans
- People who take lots of notes and want to connect them
- People who want a personal assistant for health, learning, travel, relationships
- Obsidian users (optional power-up)
- Anyone who wants full control over their data and knowledge structure

---

## 3. Key Use Cases

### A. Weekly Planning
User says: "Plan my week based on recent notes."
System searches local memory, considers projects/relations, creates a plan, saves it.

### B. Brain Dump → Plan
User dumps chaotic thoughts. System transcribes, organizes, creates a checklist, splits into today/week/later.

### C. Conversational Memory Recall
User asks: "What did I decide about vacations?" / "What did I promise Michał?"
System searches memory + graph, returns concise answer.

### D. Working with User's Knowledge Sources
User adds health notes, PDFs, checklists, articles. Then asks: "What do my materials say about sleep and energy?"

### E. Custom Specialists
User creates specialists (Health Guide, Weekly Planner, Study Coach, etc.) with own sources, rules, style, examples, and tools.

---

## 4. Confirmed Product Decisions

1. Not a coding app
2. Not based on Claude Code
3. Main engine: **Claude API** (Messages API)
4. Interface runs **in the browser**
5. User provides only: **Anthropic API key** + microphone permission
6. **API key security**: Do not store Anthropic API key in plain text if avoidable. Prefer OS keychain integration (e.g., `keyring` Python package). `config.json` stores only a flag `api_key_set: true`, not the key itself. Fallback for MVP: environment variable or encrypted local storage.
7. Memory: local, Markdown-based, Obsidian-compatible
8. Obsidian: optional, not required
9. Knowledge graph layer: yes
10. Voice: important from the start
11. User-created specialists from UI: yes
12. Token-efficient architecture: yes
13. No over-engineered agent framework on start

---

## 5. Tech Stack (MVP)

### Frontend
- **Nuxt 3** (Vue 3 + file-based routing + auto-imports)
- **TypeScript** (strict mode)
- **Nitro** (built-in dev proxy to backend)
- **useState()** composable for shared state (no Pinia needed)
- CSS: simple scoped CSS (start minimal)

### Backend
- **Python 3.12+**
- **FastAPI** (HTTP + WebSocket)
- **SQLite** (operational DB via `aiosqlite`)
- **Anthropic Python SDK** (`anthropic`)
- File I/O for Markdown memory

### Voice
- **Web Speech API** (browser-native STT) — no extra API key needed
- **Browser SpeechSynthesis** (TTS) for MVP — upgrade later if needed
- Fallback: Anthropic or other TTS if quality is insufficient

**Voice abstraction rule**: Voice layer must be abstracted behind interfaces (`STTProvider`, `TTSProvider`). Browser-native STT/TTS is the MVP default. Future providers (Whisper local, Kokoro.js, Piper, cloud TTS) can replace implementation without changing app flow. No voice provider should be hardwired into components.

### Knowledge Graph
- Lightweight local graph stored as JSON
- Visualized with **D3.js** or **vis-network** in browser
- No heavy graph DB on start

### Communication
- REST API for CRUD operations
- WebSocket for streaming Claude responses and voice state sync

---

## 6. Repository Structure

```
jarvis/
├── docs/
│   └── JARVIS-PLAN.md          # Initial plan
├── backend/
│   ├── main.py                  # FastAPI entry point
│   ├── requirements.txt
│   ├── config.py                # App configuration
│   ├── routers/
│   │   ├── chat.py              # Chat / Claude API endpoints
│   │   ├── memory.py            # Memory CRUD endpoints
│   │   ├── graph.py             # Graph query endpoints
│   │   ├── specialists.py       # Specialist CRUD endpoints
│   │   ├── workspace.py         # Workspace setup endpoints
│   │   └── voice.py             # Voice-related endpoints
│   ├── services/
│   │   ├── claude.py            # Claude API wrapper
│   │   ├── memory_service.py    # Memory read/write/search
│   │   ├── graph_service.py     # Graph operations
│   │   ├── specialist_service.py# Specialist management
│   │   ├── retrieval.py         # Hybrid retrieval pipeline
│   │   ├── context_builder.py   # Build minimal context for Claude
│   │   ├── session_service.py   # Session history + conversation save
│   │   ├── ingest.py            # File ingest (fast + smart)
│   │   └── tools.py             # Tool definitions + execution
│   ├── models/
│   │   ├── schemas.py           # Pydantic models
│   │   └── database.py          # SQLite setup + models
│   └── utils/
│       └── markdown.py          # Markdown parsing helpers
├── frontend/
│   ├── package.json
│   ├── nuxt.config.ts
│   ├── tsconfig.json
│   ├── app.vue                    # Root layout
│   ├── pages/
│   │   ├── index.vue              # Redirect to /main
│   │   ├── main.vue
│   │   ├── onboarding.vue
│   │   ├── memory.vue
│   │   ├── graph.vue
│   │   ├── specialists.vue
│   │   └── settings.vue
│   ├── components/
│   │   ├── Orb.vue
│   │   ├── ChatPanel.vue
│   │   ├── TranscriptBar.vue
│   │   ├── VoiceButton.vue
│   │   ├── StatusBar.vue
│   │   └── SpecialistCard.vue
│   ├── composables/
│   │   │   ├── useVoice.ts
│   │   │   ├── useChat.ts
│   │   │   └── useWebSocket.ts
│   │   ├── services/
│   │   │   └── api.ts           # HTTP + WS client
│   │   └── assets/
│   │       └── styles/
│   │           └── main.css
│   └── public/
└── README.md
```

---

## 7. Workspace Structure (User Data)

Created on first run at a user-chosen location (default: `~/Jarvis/`):

```
Jarvis/
├── app/
│   ├── config.json              # Metadata + flags (no raw API key)
│   ├── sessions/                # Chat session history
│   ├── cache/                   # Retrieval cache
│   ├── logs/                    # System logs
│   ├── audio/                   # Voice recordings
│   └── jarvis.db                # SQLite operational DB
├── memory/
│   ├── inbox/                   # Quick captures
│   ├── daily/                   # Daily notes / journals
│   ├── projects/                # Project notes
│   ├── people/                  # People notes
│   ├── areas/                   # Life areas
│   ├── plans/                   # Plans & checklists
│   ├── summaries/               # AI-generated summaries
│   ├── knowledge/               # Knowledge sources
│   ├── preferences/             # User rules & preferences
│   ├── examples/                # Good answer examples
│   └── attachments/             # Files, PDFs, images
├── graph/
│   ├── graph.json               # Graph data
│   ├── GRAPH_REPORT.md          # Graph report
│   └── graph.html               # Visual graph
└── agents/                      # Specialist definitions
```

---

## 8. Logical Architecture

```
┌─────────────────────────────────────────────┐
│                  BROWSER                     │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Voice    │  │  Chat    │  │  Memory   │  │
│  │  Input/   │  │  Panel   │  │  Browser  │  │
│  │  Output   │  │          │  │  + Graph  │  │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       │              │              │         │
│       └──────────────┼──────────────┘         │
│                      │                        │
│              HTTP / WebSocket                 │
└──────────────────────┬────────────────────────┘
                       │
┌──────────────────────┴────────────────────────┐
│              LOCAL BACKEND (FastAPI)           │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │           JARVIS CORE (Orchestrator)    │  │
│  │                                         │  │
│  │  • Receives user message                │  │
│  │  • Runs hybrid retrieval                │  │
│  │  • Selects tools                        │  │
│  │  • Calls Claude API                     │  │
│  │  • Streams response                     │  │
│  │  • Saves results to memory              │  │
│  └───────┬──────────┬──────────┬───────────┘  │
│          │          │          │               │
│  ┌───────▼───┐ ┌────▼────┐ ┌──▼──────────┐   │
│  │  Memory   │ │ Graph   │ │ Specialists │   │
│  │  Service  │ │ Service │ │ Service     │   │
│  └───────┬───┘ └────┬────┘ └─────────────┘   │
│          │          │                         │
│  ┌───────▼──────────▼─────────────────────┐   │
│  │         LOCAL FILE SYSTEM              │   │
│  │  Jarvis/memory/  Jarvis/graph/         │   │
│  │  Jarvis/agents/  Jarvis/app/           │   │
│  └────────────────────────────────────────┘   │
│                                               │
│  ┌────────────────────────────────────────┐   │
│  │         SQLite (jarvis.db)             │   │
│  │  • Note index & metadata               │   │
│  │  • Session history                      │   │
│  │  • Search cache                         │   │
│  │  • Graph relations (denormalized)       │   │
│  └────────────────────────────────────────┘   │
└───────────────────────────────────────────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   Claude API    │
              │  (Messages API) │
              └─────────────────┘
```

---

## 9. Hybrid Retrieval Pipeline

```
User query
    │
    ▼
1. Structural search (SQLite)
   → folders, tags, note types, dates, frontmatter, entities
    │
    ▼
2. Graph expansion
   → neighbor notes, related entities, linked projects/people
    │
    ▼
3. (Optional) Vector similarity
   → semantic search as fallback/supplement
    │
    ▼
4. Context assembly
   → rank, deduplicate, trim to token budget
    │
    ▼
5. Claude synthesis
   → small, curated context → model generates answer
```

**Goal**: Do as much as possible locally. Send minimal context to Claude. Save tokens.

---

## 10. MVP Tools (Backend)

| Tool                      | Description                                |
|---------------------------|--------------------------------------------|
| `search_notes(query)`     | Search memory by keyword/tag/date          |
| `open_note(path)`         | Read a specific note                       |
| `write_note(path, content)` | Create or overwrite a note              |
| `append_note(path, content)` | Append content to existing note         |
| `create_plan(context)`    | Generate a plan from context               |
| `summarize_context(context)` | Summarize given context                 |
| `query_graph(question)`   | Query knowledge graph                      |
| `save_preference(rule)`   | Save user preference/rule                  |
| `create_specialist(config)` | Create a new specialist                  |

Claude selects tools via tool_use. Backend executes them locally.

---

## 11. Teaching Jarvis (No Fine-tuning)

Users teach Jarvis through:

1. **Sources** — adding materials to `memory/knowledge/`
2. **Rules** — preferences saved in `memory/preferences/`
3. **Examples** — good outputs saved in `memory/examples/`
4. **Conversational feedback** — "make it shorter", "use my sources first"
5. **Manual graph strengthening** — linking topics, assigning sources to specialists

All teaching is:
- Controllable
- Debuggable
- Reversible
- Cheaper than model training

---

## 12. File Ingest Pipeline

### Fast Ingest (no AI)
- Read file
- Extract text
- Parse metadata
- Split into sections/chunks
- Create index entries
- Add explicit relations

### Smart Enrich (optional AI)
- Generate summary
- Extract entities
- Suggest relations
- Classify document
- Enrich graph

These are separate steps. Fast ingest can run on hundreds of files without any API calls.

---

## 13. Specialist System

Specialists are **behavior/knowledge/tool profiles**, not heavy agent systems.

**A specialist is not a separate autonomous agent runtime. It is a constrained configuration profile used by Jarvis Core.** There is no separate process, no task queue, no independent memory. Jarvis Core loads the specialist config, adjusts its system prompt, narrows its tool access and knowledge scope, and responds accordingly.

Each specialist has:
- Name
- Role description
- Assigned knowledge sources
- Response style
- Rules
- Tool permissions
- Example outputs

Stored as JSON in `Jarvis/agents/{specialist-id}.json`.

### UI Creation Flow
1. Name → 2. Role → 3. Sources → 4. Style → 5. Rules → 6. Tools → 7. Examples

### Usage Model (MVP)
1. User activates specialist manually: "Use Health Guide"
2. Jarvis suggests specialist: "This looks health-related. Use Health Guide?"
3. (Later) Automatic routing

---

## 14. Voice Architecture (MVP)

### Input
- Browser **Web Speech API** (SpeechRecognition) — no extra API key
- Push-to-talk or click-to-talk
- Abstracted behind `STTProvider` interface
- Future upgrade: `faster-whisper` on backend (toggle in settings)

### Output
- Browser **SpeechSynthesis API** — no extra API key
- Abstracted behind `TTSProvider` interface
- Future upgrade: **Kokoro.js** (in-browser, natural voice, Apache-2.0) or **Piper TTS** (backend, has Polish voices)

### States
- `idle` — waiting
- `listening` — recording user speech
- `thinking` — processing / calling Claude
- `speaking` — playing response audio

### Flow
1. User clicks mic / holds push-to-talk
2. Browser STT transcribes speech
3. Transcript sent to backend via WebSocket
4. Backend runs retrieval + Claude
5. Response streamed back
6. Browser speaks response via TTS
7. Transcript shown in UI

### Conversation Save Model

After each conversation, the system saves:
- **Raw transcript** → `app/sessions/{session-id}.json`
- **Summary** → `memory/summaries/{date}-{topic}.md` (optional, AI-generated)
- **Action items** → `memory/inbox/` or `memory/plans/` as new notes
- **Extracted entities** → added to graph
- **Linked notes** → updated with new references

This happens automatically in the background after the user finishes a session.

---

## 15. Onboarding Flow

### User does:
1. Enters Anthropic API key
2. Grants microphone permission
3. Clicks "Create Jarvis Workspace"

### System does:
1. Creates `Jarvis/` folder structure
2. Initializes SQLite database
3. Saves config
4. Creates initial graph structure
5. Redirects to main view

No manual vault setup. No extra installs. No multiple API keys.

---

## 16. UI Layout (Main View)

```
┌─────────────────────────────────────────┐
│  [Status Bar]         [Settings] [Mem]  │
├─────────────────────────────────────────┤
│                                         │
│              ┌───────┐                  │
│              │  ORB  │                  │
│              │ (state│                  │
│              │ visual│                  │
│              └───────┘                  │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │     Latest Jarvis response      │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌─────────────────────────────────┐    │
│  │     Transcript bar              │    │
│  └─────────────────────────────────┘    │
│                                         │
│  ┌────────┐  ┌──────────────────┐       │
│  │  🎤    │  │  Type message... │       │
│  └────────┘  └──────────────────┘       │
│                                         │
│  [Specialists]  [Recent]  [Graph]       │
└─────────────────────────────────────────┘
```

---

## 17. Key Constraints

- **Simplicity first** — MVP over perfection
- **Local-first** — all user data on their machine
- **Token-efficient** — minimal context sent to Claude
- **No lock-in** — Markdown files, JSON config, SQLite
- **No extra API keys** — only Anthropic key required for MVP
- **Incremental** — each phase delivers usable functionality
- **No over-engineering** — no heavy agent framework, no enterprise graph DB

---

## 18. Product Differentiators

1. Memory belongs to the user (local files)
2. Obsidian-compatible
3. Explicit knowledge graph
4. User teaches system via sources, rules, examples, feedback
5. Voice is a first-class interface to a real memory system
6. User creates specialists from UI without code
7. Token-efficient hybrid retrieval

**One-line pitch**: _Jarvis is not an AI chat with memory — it's a voice interface to your personal knowledge system._

---

## 19. Non-goals for MVP

The MVP should explicitly **not** attempt:
- Autonomous background agents
- Multi-user collaboration
- Cloud sync
- Heavy vector database infrastructure
- Advanced permissions model
- Marketplace for specialists
- Always-on wake word detection
- Mobile apps
- External integrations beyond local files and Claude API
- Complex graph inference pipelines
- Fine-tuning or model training
- Real-time collaboration
- Plugin/extension system

Anything not listed in Phases 1–8 is out of scope until those phases are complete.

---

## 20. Execution Preference

Start with the **thinnest working vertical slice**:

1. Onboarding (API key + workspace creation)
2. Text chat with Claude (no voice yet)
3. Local memory read/write (Markdown files)
4. Save chat results to memory
5. Basic retrieval (search notes → build context → Claude answers)

Only after this end-to-end flow works, add:
- Voice
- Graph
- Specialists
- UI polish

**Prefer a working end-to-end slice over broad scaffolding.** Each phase should produce something the user can actually use.

<!-- codument:start -->
## Documentation Maintenance

### Documentation is automatic — not a separate step
When you write or modify source files, you MUST create or update documentation as part of the same task. Do not ask the user whether to document. Do not defer to a skill. Just do it inline.

### Definition of Done
A task is NOT complete until:
1. Code works and tests pass
2. `docs/.registry.json` is checked for affected source files
3. New source files are registered in `docs/.registry.json`
4. Corresponding feature docs are created or updated (not scaffolded — real content)
5. Dependent features flagged if interface changed
6. `last_updated` set on all touched docs and registry entries

### Plan → Implement → Document
When implementing a planned feature, the plan is not "done" until documentation exists. Writing code and writing docs are one action, not two.

### Documentation Registry
The file `docs/.registry.json` maps source files to their documentation.
Always check it before and after modifying source files.

### Documentation Structure
- Feature docs: `docs/features/{name}.md`
- Concept docs: `docs/concepts/{name}.md`
- ADRs: `docs/architecture/decisions/{NNN}-{title}.md`
- All filenames: lowercase kebab-case
<!-- codument:end -->
