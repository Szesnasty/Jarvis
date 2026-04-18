# MCP Server Refactor — Spec

**Status:** ✅ done (shipped in v0.8.0, PR `feat/mcp-server`)
**Branch:** `feat/mcp-server` (merged to main)
**Owner:** local-only refactor

## Goals

1. **Run locally, no friction.** `jarvis-mcp` is a standalone CLI binary on the user's PATH. No absolute filesystem paths anywhere in client configs.
2. **Easy configuration.** Cursor/Claude/VS Code config is two lines:
   ```json
   { "command": "jarvis-mcp", "args": ["--transport", "stdio"] }
   ```
   No `cwd`, no `PYTHONPATH`, no env required (workspace auto-discovered).
3. **Token-efficient access to Jarvis-built knowledge bases.** Preserve the 25-tool surface (search, notes, graph, jira, sessions, preferences) plus output budget enforcement and continuation tokens.
4. **Modularity.** MCP server is its own top-level package (`mcp_server/`), not buried inside `services/`. It depends on `services/*` (memory, retrieval, graph, jira) but the FastAPI backend does **not** depend on `mcp_server/`. Clean separation.

## Non-goals

- Remote/SSE/HTTP transport — **dropped**.
- PyPI publication — out of scope (local install via bootstrap symlink).
- Smithery listing — out of scope.
- Running MCP server from the web UI — **dropped** (clients spawn it themselves).

## Current state (problems)

| Area | Problem |
|---|---|
| Location | `backend/services/mcp/` — buried in services namespace |
| Tools registry | Single 1025-LOC `tools.py` with 25 tools |
| Dispatcher | Custom `JarvisMCPServer` (~150 LOC) reimplementing what FastMCP does |
| Schema validation | Custom `_validate_args` (~60 LOC) instead of pydantic |
| Stdio transport | Custom `transports/stdio.py` (139 LOC) reimplementing what FastMCP does |
| SSE transport | `transports/sse.py` (197 LOC) + `routers/mcp.py` (`/start`, `/stop`, `/regenerate-token`, etc.) — unused by all real MCP clients |
| Frontend | "MCP server: ON/OFF" toggle — wrong mental model; MCP is launched by the client |
| Snippet generator | Embeds absolute venv path; useless if user moves the repo |
| Workspace discovery | Only via `JARVIS_WORKSPACE` env or default `~/Jarvis`; no config file fallback |

## Target architecture

### Filesystem layout

```
backend/
├── services/                     # business logic, unchanged
│   ├── memory_service.py
│   ├── retrieval/
│   ├── graph_service/
│   └── ...
├── routers/                      # FastAPI routers
│   └── mcp.py                    # SHRUNK: only /info endpoint (read-only)
└── mcp_server/                   # NEW top-level package
    ├── __init__.py
    ├── __main__.py               # CLI entry: jarvis-mcp
    ├── app.py                    # FastMCP() instance + registration
    ├── config.py                 # workspace discovery (env > toml > default)
    ├── middleware/
    │   ├── __init__.py
    │   ├── budget.py             # _enforce_output_budget + continuation cache
    │   ├── audit.py              # log every call to workspace/app/mcp_audit.jsonl
    │   └── gates.py              # write/privacy gates
    └── tools/
        ├── __init__.py           # register_all(mcp)
        ├── search.py             # 3 tools
        ├── notes.py              # 3 tools
        ├── graph.py              # 4 tools
        ├── jira.py               # 6 tools
        ├── sessions.py           # 3 tools
        ├── preferences.py        # 2 tools
        └── workspace.py          # 4 tools (stats, recent activity, etc.)
```

### Entry points (`backend/pyproject.toml`)

```toml
[project.scripts]
jarvis-mcp = "mcp_server.__main__:main"
```

Installed binary: `<venv>/bin/jarvis-mcp`. Bootstrap symlinks it to `~/.local/bin/jarvis-mcp`.

### Workspace discovery (`mcp_server/config.py`)

Resolution order:
1. `--workspace` CLI flag
2. `JARVIS_WORKSPACE` env var
3. `~/.jarvis/config.toml` → `workspace = "/path/to/jarvis"`
4. Default `~/Jarvis`

Bootstrap script writes step 3 at install time, so step 2 (env var) is no longer required.

### FastMCP server (`mcp_server/app.py`)

```python
from mcp.server.fastmcp import FastMCP
from mcp_server.tools import register_all

def build_app(workspace: Path, allow_writes: bool = False) -> FastMCP:
    mcp = FastMCP("jarvis")
    register_all(mcp, workspace=workspace, allow_writes=allow_writes)
    return mcp
```

Each tool module follows the pattern:

```python
# mcp_server/tools/search.py
from mcp.server.fastmcp import FastMCP
from mcp_server.middleware.budget import enforce_budget
from mcp_server.middleware.audit import audit
from services.retrieval.pipeline import retrieve_with_intent

def register(mcp: FastMCP, *, workspace: Path) -> None:
    @mcp.tool(description="Hybrid search ...")
    @audit("jarvis_search_memory", workspace)
    @enforce_budget(max_tokens=4000)
    async def jarvis_search_memory(
        query: str,
        top_k: int = 5,
        scope: Literal["all", "notes", "jira"] = "all",
    ) -> dict:
        _intent, results = await retrieve_with_intent(query, limit=top_k, workspace_path=workspace)
        return {"results": [...]}
```

FastMCP auto-generates JSON schema from type hints + docstring. Pydantic does validation. Decorators apply middleware in order: audit → budget → handler.

### Middleware

| Module | Responsibility | Surface |
|---|---|---|
| `budget.py` | Truncate oversize results, mint continuation tokens, expose `jarvis_continue` tool | `@enforce_budget(max_tokens=N)` decorator |
| `audit.py` | Append JSONL line to `<workspace>/app/mcp_audit.jsonl` per call | `@audit(name, workspace)` decorator |
| `gates.py` | Hide write tools when `allow_writes=False`; block network tools in offline mode | `@requires_write` / `@requires_network` decorators |

### Backend FastAPI (`routers/mcp.py`)

**Shrinks dramatically.** Removed:
- `POST /mcp/start` — clients spawn `jarvis-mcp` themselves
- `POST /mcp/stop` — same
- `POST /mcp/regenerate-token` — no token system (stdio doesn't need auth)
- `GET /mcp/token` — same

Kept (read-only, for the Settings UI):
- `GET /mcp/info` → `{ cli_on_path: bool, cli_path: str | null, workspace: str, tools_count: int, audit_log_path: str }`

### Frontend (`frontend/app/pages/settings.vue` + `useMcp.ts`)

The MCP panel becomes a **configuration helper**, not a process controller:

| Section | What it shows |
|---|---|
| Status | "✅ `jarvis-mcp` installed at `~/.local/bin/jarvis-mcp`" or "⚠️ Not on PATH — run bootstrap" |
| Tools | List of 25 available tools with descriptions, grouped by namespace |
| Snippets | Per-client config (Cursor, Claude Desktop, VS Code, Continue, Zed). All use `{"command": "jarvis-mcp"}` |
| Audit log | Tail of last 20 calls from `mcp_audit.jsonl` |

Removed from the panel:
- Start/Stop button
- Token generator/copy
- Port selector
- "Running" pulsing dot

`useMcp.ts` shrinks to: `refreshInfo()`, `buildClientSnippet(clientId)`, `tailAuditLog()`.

`StatusBar.vue` MCP pill — **removed** (no runtime state to display).

### Bootstrap (`bootstrap/install.sh`)

Adds at end:
```bash
mkdir -p ~/.local/bin
ln -sf "$BACKEND_DIR/.venv/bin/jarvis-mcp" ~/.local/bin/jarvis-mcp

mkdir -p ~/.jarvis
cat > ~/.jarvis/config.toml <<EOF
workspace = "$WORKSPACE_PATH"
EOF

echo "✅ jarvis-mcp installed. Add to your client:"
echo '   { "command": "jarvis-mcp", "args": ["--transport", "stdio"] }'
```

PowerShell equivalent in `install.ps1`.

### Client snippets (`docs/features/mcp-server/clients/*.json`)

All become identical, no placeholders needed:

```json
{
  "mcpServers": {
    "jarvis": {
      "command": "jarvis-mcp",
      "args": ["--transport", "stdio"]
    }
  }
}
```

## Implementation steps (each independently runnable + testable)

### Step 1 — Move + split (no behavior change)

- `git mv backend/services/mcp backend/mcp_server`
- Split `tools.py` (1025 LOC) into 7 namespace files under `mcp_server/tools/`
- Update all imports across backend + tests
- Update `pyproject.toml` script: `jarvis-mcp = "mcp_server.__main__:main"`
- Reinstall: `pip install -e .`
- Run: `pytest tests/test_mcp_*` — all green

### Step 2 — FastMCP

- `pip install mcp` (already a dep? verify)
- Rewrite `mcp_server/app.py` to use FastMCP
- Convert each tool module to `@mcp.tool` decorators + type hints
- Implement `middleware/budget.py` and `middleware/audit.py` as decorators
- Delete `mcp_server/server.py` (own dispatcher) and `mcp_server/transports/stdio.py`
- Update `__main__.py`: `mcp = build_app(workspace); mcp.run()`
- Smoke test: `echo '{"jsonrpc":"2.0",...}' | jarvis-mcp --transport stdio`
- Update tests to test tools directly (without the JSON-RPC layer)

### Step 3 — Drop SSE

- Delete `mcp_server/transports/` entirely
- Delete `mcp_server/auth.py` (token management)
- Shrink `routers/mcp.py` to `GET /mcp/info` only
- Delete `frontend/app/composables/useMcp.ts` start/stop/token methods
- Delete StatusBar MCP pill
- Rewrite settings.vue MCP section as configurator (per spec above)
- Update tests: delete SSE/auth tests, add `/mcp/info` test

### Step 4 — Bootstrap + workspace discovery

- Add `mcp_server/config.py` with discovery logic
- Update `__main__.py` to use new resolver
- Update `bootstrap/install.sh` and `install.ps1`
- Add `tests/test_mcp_config.py` for discovery resolution order
- Update `~/.cursor/mcp.json` to use `{"command": "jarvis-mcp"}` (no path)

### Step 5 — Docs

- Update `docs/features/mcp-server/README.md`: new install instructions, no path placeholders
- Update all `docs/features/mcp-server/clients/*.json` to portable snippets
- Add `docs/features/mcp-server/architecture.md` describing the new layout
- Update `CHANGELOG.md`

## Migration risks

| Risk | Mitigation |
|---|---|
| Test count drops a lot (SSE/auth tests gone) | Document in changelog; add new tests for FastMCP layer |
| Some user already has the old config | README migration note; old config still works via venv-path snippet (kept as fallback in UI) |
| FastMCP type hints don't cover some current tools' schemas | Spot-check each of 25 tools; fall back to manual schema for edge cases |
| `~/.local/bin` not on PATH on some macOS shells | Bootstrap detects + prints export instructions |
| Audit logging via decorator changes file format | Keep current JSONL format byte-compatible |

## Success criteria

- [ ] `jarvis-mcp` runs from any directory with no env, no cwd
- [ ] Cursor/Claude config: 2-line snippet, no paths
- [ ] All 25 tools available, exact same names + behavior
- [ ] Budget enforcement + `jarvis_continue` work as before
- [ ] Audit log in `<workspace>/app/mcp_audit.jsonl` unchanged
- [ ] `mcp_server/` has zero imports from `routers/`, `main.py`, FastAPI
- [ ] `routers/mcp.py` < 50 LOC (was ~190)
- [ ] Total LOC of MCP code drops by ~700 (own dispatcher + transport gone)
- [ ] All existing pytest tests pass (or are intentionally deleted with reason in changelog)
- [ ] Smoke test from Cursor: `jarvis_workspace_stats` returns valid result
