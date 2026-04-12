# Step 01 — Backend Initialization (FastAPI)

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: — | **Next**: [Step 02 — Frontend Init](step-02-frontend-init.md) | **Index**: [step-00-index.md](step-00-index.md)

---

## Goal

Create a minimal FastAPI backend that starts, serves a health endpoint, and has the correct project structure ready for future modules.

---

## Files to Create

```
backend/
├── main.py                  # FastAPI app factory + CORS
├── config.py                # Settings via pydantic-settings
├── requirements.txt         # Python dependencies
├── routers/
│   └── __init__.py
├── services/
│   └── __init__.py
├── models/
│   ├── __init__.py
│   └── schemas.py           # Shared Pydantic models (start with HealthResponse)
└── utils/
    └── __init__.py
```

---

## Specification

### 1. `requirements.txt`

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
pydantic-settings>=2.0
aiosqlite>=0.20.0
anthropic>=0.40.0
keyring>=25.0
python-multipart>=0.0.9
```

### 2. `config.py`

- Use `pydantic-settings.BaseSettings` to load config from environment variables
- Fields:
  - `workspace_path: Path = Path.home() / "Jarvis"` — where user data lives
  - `api_host: str = "127.0.0.1"`
  - `api_port: int = 8000`
  - `cors_origins: list[str] = ["http://localhost:5173"]` — Vite dev server
- Singleton getter: `get_settings() -> Settings`
- No API key in settings — that goes through keyring (later in step 03)

### 3. `main.py`

- Create `FastAPI` app with title `"Jarvis API"`
- Add CORS middleware using origins from config
- Register a single route `GET /api/health` returning `{"status": "ok", "version": "0.1.0"}`
- `if __name__ == "__main__"` block with `uvicorn.run()`

### 4. `models/schemas.py`

- `HealthResponse(BaseModel)` with `status: str` and `version: str`

---

## Key Decisions

- Backend runs on `127.0.0.1:8000` — local only, not exposed to network
- CORS allows only the Vite dev server origin
- All routers will be registered in `main.py` via `app.include_router()`
- No database initialization yet — that comes in step 03

---

## Acceptance Criteria

- [ ] `cd backend && pip install -r requirements.txt` succeeds
- [ ] `python main.py` starts the server on port 8000
- [ ] `curl http://localhost:8000/api/health` returns `{"status": "ok", "version": "0.1.0"}`
- [ ] No unused imports, type hints on all functions
- [ ] File structure matches the tree above
