---
title: Project Overview
last_reviewed: 2026-04-14
---

## What this project is

Jarvis is a voice-first personal memory, planning, and knowledge system. It provides a browser-based interface to a local Markdown knowledge base, powered by Claude API for conversational retrieval and planning. All user data stays on disk as Markdown files — SQLite and graph layers are derived indexes that can be rebuilt from scratch.

## Architecture

```
Browser (Nuxt 3, SPA)  ──HTTP/WS──▶  FastAPI backend  ──▶  Claude API
       │                                    │
       └── Voice (Web Speech API)           ├── SQLite (index/cache)
                                            ├── Markdown files (source of truth)
                                            └── graph.json (derived knowledge graph)
```

**Frontend** — Nuxt 3 SPA with Vue 3 composables. No SSR. Communicates with the backend via REST (CRUD) and a single WebSocket (chat streaming). Voice uses browser-native Web Speech API behind provider interfaces.

**Backend** — FastAPI with 8 routers and ~15 services. Orchestrates retrieval, Claude API calls, tool execution, and file I/O. The chat endpoint streams Claude responses over WebSocket, executes tool calls server-side, and loops back for multi-turn tool use (up to 5 rounds).

**Data flow** — User message → hybrid retrieval (FTS5 + graph neighbors) → context assembly → Claude API → streamed response + optional tool calls (write notes, create plans, query graph) → results saved to Markdown files → SQLite re-indexed.

## Key technologies

| Layer | Technology |
|-------|-----------|
| Frontend framework | Nuxt 4.4 / Vue 3.5 / TypeScript (strict) |
| Frontend build | Vite, Nitro dev proxy to backend |
| Backend framework | FastAPI (Python 3.12+) |
| AI | Anthropic Claude API (Messages API with tool_use) |
| Database | SQLite via aiosqlite (FTS5 for search) |
| Graph | JSON file, visualized with force-graph + Three.js |
| Voice | Web Speech API (STT + TTS), abstracted behind provider interfaces |
| Testing | Vitest (frontend), pytest (backend) |
| Markdown | marked + DOMPurify for rendering |

## Feature documentation

All feature docs are in [docs/features/](features/) and the concept doc is in [docs/concepts/](concepts/). The registry at [docs/.registry.json](../.registry.json) maps source files to their documentation.

| Feature | Doc |
|---------|-----|
| App Shell & Navigation | [app-shell.md](features/app-shell.md) |
| Chat & Claude Integration | [chat.md](features/chat.md) |
| Knowledge Graph | [knowledge-graph.md](features/knowledge-graph.md) |
| Memory System | [memory.md](features/memory.md) |
| Planning Service | [planning.md](features/planning.md) |
| Preferences & Settings | [preferences-settings.md](features/preferences-settings.md) |
| Hybrid Retrieval Pipeline | [retrieval.md](features/retrieval.md) |
| Session Management | [sessions.md](features/sessions.md) |
| Specialist System | [specialists.md](features/specialists.md) |
| Voice System | [voice.md](features/voice.md) |
| Workspace & Onboarding | [workspace-onboarding.md](features/workspace-onboarding.md) |
| Database Layer (concept) | [database.md](concepts/database.md) |
