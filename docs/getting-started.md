---
title: Getting Started
last_reviewed: 2026-04-14
---

## Prerequisites

- **Python 3.12+** with pip
- **Node.js 18+** with npm (or Bun)
- **Anthropic API key** — the only external API key needed

## Setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Optionally create `backend/.env` for configuration:

```env
JARVIS_WORKSPACE_PATH=~/Jarvis       # default
JARVIS_API_HOST=127.0.0.1            # default
JARVIS_API_PORT=8000                 # default
```

All settings are prefixed with `JARVIS_` and read via pydantic-settings.

### Frontend

```bash
cd frontend
npm install        # or: bun install
npm run postinstall  # runs nuxt prepare
```

## Development

### Run both servers

Terminal 1 — backend:
```bash
cd backend
python main.py
# FastAPI on http://127.0.0.1:8000, auto-reload enabled
```

Terminal 2 — frontend:
```bash
cd frontend
npm run dev
# Nuxt on http://localhost:3000, proxies /api → backend
```

### First run

1. Open `http://localhost:3000`
2. You'll be redirected to the onboarding page
3. Enter your Anthropic API key (stored in OS keychain or fallback file)
4. Click "Create Jarvis Workspace" — creates `~/Jarvis/` with all subdirectories
5. Redirected to the main view — start chatting

### Run tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

### Project structure

```
jarvis/
├── backend/          # FastAPI (Python)
│   ├── main.py       # App entry point
│   ├── config.py     # Settings (JARVIS_ env prefix)
│   ├── routers/      # HTTP + WebSocket endpoints
│   ├── services/     # Business logic
│   ├── models/       # SQLite + Pydantic schemas
│   └── tests/
├── frontend/         # Nuxt 3 (Vue + TypeScript)
│   ├── app/
│   │   ├── pages/        # File-based routing
│   │   ├── components/   # Vue components
│   │   ├── composables/  # Shared state + logic
│   │   └── types/
│   └── tests/
└── docs/             # Feature documentation
```

See [overview.md](overview.md) for architecture details and [docs/features/](features/) for per-feature documentation.
