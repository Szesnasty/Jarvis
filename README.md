# Jarvis

[![CI](https://github.com/Szesnasty/Jarvis/actions/workflows/ci.yml/badge.svg)](https://github.com/Szesnasty/Jarvis/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Szesnasty/Jarvis/actions/workflows/codeql.yml/badge.svg)](https://github.com/Szesnasty/Jarvis/actions/workflows/codeql.yml)
[![Release](https://img.shields.io/github/v/release/Szesnasty/Jarvis?include_prereleases&label=version)](https://github.com/Szesnasty/Jarvis/releases)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**A personal knowledge operating system that turns notes, files, links, and AI conversations into durable memory.**

Most AI tools give you answers.
Most note apps give you storage.
**Jarvis gives you continuity.**

Jarvis helps you:
- import notes, files, URLs, and YouTube sources into one system
- retrieve context through keyword + semantic + graph search
- turn useful outputs into reusable notes, plans, and summaries
- create custom specialists directly from the UI
- run structured debates between specialists with **Duel Mode**
- search the web via DuckDuckGo when local memory isn't enough
- use Anthropic, OpenAI, or Google models — your choice
- keep your memory local-first and Obsidian-compatible

> **Jarvis is not another AI chat with memory.**
> **It is a personal knowledge system that gets more useful every time you use it.**

<!-- Coming soon: hero screenshot or demo GIF — place image at docs/assets/hero.png -->
![Jarvis hero](./docs/assets/hero.png)

---

## Why this exists

Knowledge work is fragmented. Ideas live in notes. Context lives in files. Research lives in links. Decisions disappear into chat history. Useful AI outputs vanish after the session ends.

That creates real costs:
- repeated thinking
- lost context
- higher AI spend rebuilding context over and over
- no compounding value from what you already know

Jarvis fixes the loop: **input → retrieve → reason → write back → better retrieval next time.**

---

## What makes Jarvis different

### Your memory belongs to you
Local Markdown files are the source of truth. Not a proprietary memory layer. Not a database you can't read.

### Retrieval before reasoning
Jarvis does the expensive work locally first — BM25, semantic search, graph expansion, ranking, compression — then sends only a small, high-signal context to the model. Fewer tokens, lower cost, better answers.

### A real knowledge graph
Notes, people, projects, topics, and sources are connected through a graph that is part of retrieval and reasoning — not just a visualization.

### Multi-provider
Anthropic, OpenAI, and Google models via LiteLLM. Switch models per conversation. No vendor lock-in.

### Specialists from the UI
Create reusable roles — Weekly Planner, Health Guide, Study Coach, Research Assistant — directly from the interface. No prompt engineering required.

### Duel Mode
Pick a topic, pick two specialists. They debate. Jarvis judges. The outcome is saved back into memory. Structured argumentation that produces reusable outputs.

### Web search
When local memory isn't enough, Jarvis searches the web via DuckDuckGo — no extra API keys needed.

### Write-back by design
Useful outputs become notes, summaries, plans, graph links, and durable context. Every useful interaction makes the system better.

### Obsidian-compatible
Your `Jarvis/memory/` folder works as a valid Obsidian vault — plain Markdown, YAML frontmatter, wiki-links, human-readable structure.

---

## How it works in practice

**Imported:** project notes, 2 URLs, 1 YouTube video.

**Asked Jarvis:** *"What should we do next?"*

**Jarvis:**
1. Retrieved relevant notes from memory (BM25 + embeddings)
2. Expanded context through graph links
3. Ranked and compressed candidates
4. Produced a practical plan via Claude
5. Saved the result to `memory/plans/`
6. Updated graph relationships for future use

**Result:** not just a better answer — a better system after the answer.

---

## Why this is not ChatGPT, NotebookLM, or Obsidian

| Tool | What it does well | Where Jarvis differs |
|---|---|---|
| **ChatGPT** | Great general AI assistant | Jarvis writes outputs back into structured, local memory |
| **NotebookLM** | Source-grounded research | Jarvis turns sources into a living memory + graph + specialist system |
| **Obsidian** | Local note-taking and vault management | Jarvis adds retrieval, reasoning, specialists, graph-aware context, and write-back |

**Jarvis is the layer that turns information into working memory.**

---

## Interface

### Chat — your memory-aware assistant
Ask questions, get answers grounded in your own notes. Context is retrieved automatically — you just talk.
![Chat](./docs/assets/chat.png)

### Memory — browse and manage your knowledge
All your notes in one place. Search, filter by folder, edit inline. Everything is plain Markdown — open it in Obsidian anytime.
![Memory](./docs/assets/memory.png)

### Graph — see how your knowledge connects
People, projects, topics, and sources linked visually. Click any node to explore. The graph isn't decoration — it powers retrieval.
![Graph](./docs/assets/graph.png)

### Specialists — custom roles, no code required
Create focused advisors with their own knowledge, rules, and style. A Growth Strategist thinks differently than an Operations Advisor — and that's the point.
![Specialists](./docs/assets/specialists.png)

### Duel Mode — structured debate that produces decisions
Two specialists argue. Jarvis judges. The verdict, scores, and action items are saved to memory. Turn hard decisions into documented reasoning.
![Duel](./docs/assets/duel.png)

### Settings — your setup, your control
API keys, model selection, token budgets, workspace path. Everything stays local.
![Settings](./docs/assets/settings.png)

---

## What works today

- Browser-based UI with chat, memory browser, graph view, settings
- Local workspace with Markdown memory
- File, URL, and YouTube ingest (including PDF)
- Interactive graph visualization (D3-based)
- Graph-guided hybrid retrieval (BM25 + semantic + graph scoring)
- Local embeddings via fastembed (multilingual, no API calls)
- Specialist system with full UI wizard
- Duel Mode with round-based debate and scored verdict
- Multi-provider support (Anthropic, OpenAI, Google)
- Web search via DuckDuckGo (no extra API key)
- Token tracking with budget controls
- Session-to-memory write-back with graph updates
- Secure API key handling
- Obsidian-compatible memory structure

---

## Quick start

### Requirements

- **Node.js 20+** — check: `node --version`
- **Python 3.12 or 3.13** — check: `python3 --version` (macOS/Linux) or `py --version` (Windows)
- **One API key** from any supported provider:
  - [Anthropic](https://console.anthropic.com) (Claude)
  - [OpenAI](https://platform.openai.com/api-keys) (GPT-4o)
  - [Google AI](https://aistudio.google.com/apikey) (Gemini)

> Don't have Node.js or Python? Use a [bootstrap installer](#zero-prereq-bootstrap) — it can download local runtimes automatically, no admin rights needed.

### One command

```bash
git clone https://github.com/Szesnasty/Jarvis.git
cd Jarvis
npm run wake-up-jarvis
```

**That's it. One command to install and start Jarvis.** It will:

1. **Preflight check** — verify Node 20+, npm 9+, Python 3.12–3.13
2. **Backend** — create venv, install Python deps
3. **Frontend** — install Node deps, build production Nuxt bundle
4. **Start both servers** — backend on :8000, frontend on :3000

Open **http://localhost:3000**, paste your API key, create your workspace.

> Aliases: `npm run wake`, `npm start`. Stop with **Ctrl+C**.

<details>
<summary><strong>Zero-prereq bootstrap</strong></summary>

Recommended if you don't have Node.js or Python installed.

**macOS / Linux:**
```bash
bash ./bootstrap/install.sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap\install.ps1
```

Scripts ask for confirmation before downloading local runtimes, then run the same `wake-up-jarvis` flow.

</details>

<details>
<summary><strong>Already installed? Just run it</strong></summary>

```bash
npm run serve
```

Starts both servers without reinstalling. Dev mode with HMR:

```bash
npm run dev
```

</details>

<details>
<summary><strong>All commands</strong></summary>

```bash
# Preflight
npm run preflight          # check versions, no side effects

# Install
npm run install:all        # backend + frontend
npm run install:backend    # backend only
npm run install:frontend   # frontend only

# Production
npm run wake-up-jarvis     # preflight + install + build + serve
npm run wake               # alias
npm start                  # alias
npm run build              # nuxt build → frontend/.output
npm run serve              # serve both servers
npm run serve:backend      # backend only (uvicorn)
npm run serve:frontend     # frontend only

# Development
npm run dev                # HMR frontend + auto-reload backend
npm run dev:backend        # uvicorn --reload
npm run dev:frontend       # nuxt dev
```

</details>

<details>
<summary><strong>Troubleshooting</strong></summary>

#### Any platform
- **Port 8000 or 3000 in use** — find and stop the other process (`lsof -i :8000` on macOS/Linux)
- **Broken venv** — delete `backend/.venv` and re-run `npm run wake-up-jarvis`

#### Windows
- **Install looks stuck during venv creation** — antivirus scanning. Give it 2–5 minutes. Don't Ctrl+C.
- **Too slow?** Add Windows Defender exclusion for `backend\.venv`
- **Scripts disabled** — use `powershell -ExecutionPolicy Bypass -File .\bootstrap\install.ps1`

#### macOS
- **"xcrun: error"** — run `xcode-select --install`
- **Python 3.14+** — not yet supported. Use 3.12 or 3.13.

</details>

---

## Architecture

### Source of truth doctrine

- `Jarvis/memory/` Markdown files = canonical
- SQLite = operational index/cache (rebuildable)
- Graph = derived relationship layer (rebuildable)
- Embeddings = derived semantic layer (rebuildable)

If you delete everything except `memory/`, the system rebuilds itself.

### User workspace (created on first run)

When you create a workspace in the app, Jarvis generates this structure at your chosen location (default: `~/Jarvis/`).
This is **not** the source code — it's your personal data directory.

```
~/Jarvis/
├── app/
│   ├── config.json        # metadata + flags
│   ├── sessions/          # chat session history (JSON)
│   ├── cache/             # retrieval cache
│   ├── logs/              # token usage logs
│   ├── audio/             # voice recordings
│   └── jarvis.db          # SQLite operational DB
├── memory/
│   ├── inbox/             # quick captures
│   ├── daily/             # daily notes
│   ├── projects/          # project notes
│   ├── people/            # people notes
│   ├── areas/             # life areas
│   ├── plans/             # plans & checklists
│   ├── summaries/         # AI-generated summaries
│   ├── knowledge/         # imported sources
│   ├── preferences/       # user rules
│   ├── examples/          # good output examples
│   ├── conversations/     # saved chat sessions (auto-created)
│   └── attachments/       # files, PDFs
├── graph/
│   └── graph.json         # knowledge graph data
└── agents/                # specialist definitions (JSON)
```

### Retrieval pipeline

```
Query → BM25 → Semantic similarity → Graph expansion → Ranking → Compression → Model
```

Only a small, high-signal context reaches the model. Fewer tokens, lower cost, better signal density per dollar of API spend.

---

## Design principles

- Local-first — all data on your machine
- Memory belongs to the user — Markdown, not a proprietary layer
- Derived layers (SQLite, graph, embeddings) must be rebuildable
- Retrieval gets smarter before prompts get bigger
- Useful outputs write back into the system
- Every interaction should make the next one better

---

## Who this is for

Founders. Researchers. Builders. Students. Knowledge workers.
Anyone who thinks in notes and wants continuity, not just output.

> *"I don't need another answer. I need a system that helps me stop losing context."*

---

## Current status

**Working now:** local workspace, memory CRUD, file/URL/YouTube ingest, hybrid retrieval, graph visualization, specialists, Duel Mode, multi-provider LLM, token tracking, session write-back, web search.

**Planned next:** stronger feedback loops, smarter graph enrichment, Council Mode, improved local model support, voice (once quality is reliable).

---

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

Strong areas: retrieval quality, graph UX, specialist templates, ingest pipelines, local model support, Obsidian workflows, onboarding polish.

Open an issue or send a PR.

---

## Contributors

<table>
  <tr>
    <td align="center"><a href="https://github.com/Szesnasty"><img src="https://github.com/Szesnasty.png" width="80" style="border-radius:50%;" /><br /><b>Łukasz Jakubowski</b></a></td>
    <td align="center"><a href="https://github.com/jakubsuplicki"><img src="https://github.com/jakubsuplicki.png" width="80" style="border-radius:50%;" /><br /><b>Jakub Suplicki</b></a></td>
  </tr>
</table>

---

## Security

Found a vulnerability? See [SECURITY.md](SECURITY.md) for responsible disclosure guidelines. Do not open a public issue.

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## Repository structure

```
jarvis/
├── backend/            # FastAPI + SQLite + LiteLLM
│   ├── models/         # Pydantic schemas, DB setup
│   ├── routers/        # API endpoints (chat, memory, graph, specialists…)
│   ├── services/       # Core logic (retrieval, graph, embeddings, ingest…)
│   ├── tests/          # 39 test files, ~7k LOC
│   └── utils/          # Markdown parsing helpers
├── frontend/           # Nuxt 3 + Vue 3 + TypeScript
│   ├── app/
│   │   ├── components/ # 26 Vue components
│   │   ├── composables/# State & logic (chat, duel, graph, voice…)
│   │   └── pages/      # 7 pages (main, memory, graph, specialists…)
│   └── tests/
├── bootstrap/          # Zero-prereq installers (local runtime download)
├── scripts/            # Cross-platform Node launchers
└── docs/               # Project documentation
```

---

**Jarvis is not an AI chat with memory — it is a personal knowledge system that turns notes, files, links, and AI interactions into lasting, reusable intelligence.**
