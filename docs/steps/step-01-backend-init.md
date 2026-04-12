# Step 01 — Backend Initialization (FastAPI)

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: — | **Next**: [Step 02 — Frontend Init](step-02-frontend-init.md) | **Index**: [index-spec.md](../index-spec.md)

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
  - `cors_origins: list[str] = ["http://localhost:3000"]` — Nuxt dev server
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
- CORS allows only the Nuxt dev server origin
- All routers will be registered in `main.py` via `app.include_router()`
- No database initialization yet — that comes in step 03

---

## Tests

### Files to Create
```
backend/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures (test client, settings)
│   ├── test_health.py           # Health endpoint tests
│   └── test_config.py           # Config loading tests
├── pytest.ini                   # Pytest config
```

### `tests/conftest.py`
```python
import pytest
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

### `tests/test_health.py` (~6 tests)
- `test_health_returns_200` → status code 200
- `test_health_status_ok` → `data["status"] == "ok"`
- `test_health_version_format` → `data["version"]` matches semver pattern
- `test_health_response_schema` → response has exactly {status, version} keys
- `test_cors_allows_nuxt_origin` → OPTIONS with `Origin: http://localhost:3000` → 200 + allow header
- `test_cors_blocks_unknown_origin` → OPTIONS with `Origin: http://evil.com` → no allow-origin header

### `tests/test_config.py` (~5 tests)
- `test_default_workspace_path` → defaults to `~/Jarvis`
- `test_default_host_is_localhost` → `127.0.0.1`
- `test_default_port` → `8000`
- `test_cors_includes_nuxt` → `http://localhost:3000` in cors_origins
- `test_env_override` → setting `JARVIS_API_PORT=9999` overrides default

### `pytest.ini`
```ini
[pytest]
asyncio_mode = auto
```

### Run
```bash
cd backend && python -m pytest tests/ -v
```

**Expected**: ~11 tests pass

---

## Definition of Done

- [ ] File structure matches the tree above
- [ ] `pip install -r requirements.txt` succeeds
- [ ] `python main.py` starts the server on port 8000
- [ ] `curl http://localhost:8000/api/health` returns `{"status": "ok", "version": "0.1.0"}`
- [ ] `python -m pytest tests/ -v` — all tests pass
- [ ] No unused imports, type hints on all functions
- [ ] Committed with message `feat: step-01 backend init`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
