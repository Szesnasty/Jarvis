# Step 24a — MCP Server Backend

> **Goal**: Implement the MCP server module that exposes Jarvis tools to
> external AI clients via stdio and SSE transports. Wire it into the
> existing privacy kill-switch and add observability.

**Status**: ⬜ Not started
**Parent**: [Step 24 — MCP Server overview](step-24-mcp-server.spec.md)
**Depends on**: 04, 08, 22a–f, feat/privacy-offline-mode
**Effort**: ~2 days

---

## What this step covers

| Feature | Description |
|---|---|
| `services/mcp/` package | Server, tools, transports, runner |
| **18 tools** across 6 namespaces | Memory, notes, graph, Jira, sessions, metadata + 3 opt-in writes |
| Cost-class budgets | Every tool declares `cost_class` and `max_output_tokens` |
| Continuation tokens | Heavy results truncate with `continuation_token` instead of dumping |
| stdio transport | For Claude Desktop / Cursor `command:` entries |
| SSE transport | For HTTP clients, started/stopped via API |
| Token auth (SSE) | Per-workspace bearer token in `app/mcp_token` |
| Privacy gate integration | Reuses `services.privacy` for any future cloud-bound tools |
| Lifecycle endpoints | `POST /api/mcp/start`, `POST /api/mcp/stop`, `GET /api/mcp/status` |
| Observability | `app/logs/mcp.jsonl` append-only log with token-cost estimates |
| Tests | Tool execution, auth, transports, privacy interaction, write opt-in |

---

## File layout

```
backend/
  services/
    mcp/
      __init__.py
      server.py              # NEW — Server class, transport-agnostic
      tools.py               # NEW — tool definitions + handlers
      auth.py                # NEW — token generation + verification
      logging.py             # NEW — JSONL append logger
      runner.py              # NEW — entrypoint: python -m services.mcp
      transports/
        stdio.py             # NEW
        sse.py               # NEW (starlette/uvicorn over loopback)
  routers/
    mcp.py                   # NEW — start/stop/status HTTP API
  models/
    database.py              # MODIFY — verify WAL; add `_ro_connect()` helper
  tests/
    test_mcp_tools.py        # NEW
    test_mcp_auth.py         # NEW
    test_mcp_privacy.py      # NEW
  pyproject.toml             # MODIFY — add `mcp[cli]>=0.5` (or fastmcp)
```

The `services/mcp/` package is **self-contained**: it imports from
existing services but nothing imports from it (except `routers/mcp.py`
and the runner). This keeps the blast radius small.

---

## Tool catalogue

**18 tools across 6 namespaces.** All read-only by default; the three
write tools require `mcp.allow_writes=true` in `config.json` and are
hidden from `tools/list` otherwise. Every tool declares `cost_class`
and `max_output_tokens`. Heavy results truncate with a
`continuation_token` so the agent decides whether to pay for more.

### Namespace summary

| Namespace | Tools | Reuses |
|---|---|---|
| `jarvis_search_*` | `memory`, `notes`, `jira` | `services.retrieval.pipeline.retrieve_with_intent` |
| `jarvis_note_*` | `read`, `list`, `outline` | `services.memory_service.{get_note,list_notes}` |
| `jarvis_graph_*` | `query`, `neighbors`, `entity_detail`, `path_between` | `services.graph_service.queries.*` |
| `jarvis_jira_*` | `describe_issue`, `list_issues`, `blockers_of`, `depends_on`, `sprint_risk`, `cluster_by_topic` | `services.tools.jira_tools.*` |
| `jarvis_session_*` | `recent`, `recent_decisions`, `tool_history` | `services.session_service.{list_sessions,load_session}` |
| `jarvis_meta_*` | `get_preferences`, `list_specialists`, `workspace_stats` | `services.preference_service`, `services.specialist_service` |
| **Opt-in writes** | `save_preference`, `append_note`, `summarize_and_save` | `services.preference_service`, `services.memory_service.append_note`, `services.tools.executor._execute_summarize` |

### `jarvis_search_memory`

```json
{
  "description": "Hybrid search (BM25 + semantic + reranker, graph-aware) over the user's notes and Jira issues. Returns top-k chunks with paths and scores. Use this BEFORE pasting raw notes into the prompt.",
  "cost_class": "medium",
  "max_output_tokens": 4000,
  "input_schema": {
    "type": "object",
    "required": ["query"],
    "properties": {
      "query":  { "type": "string", "minLength": 1, "maxLength": 500 },
      "top_k":  { "type": "integer", "minimum": 1, "maximum": 20, "default": 5 },
      "scope":  { "type": "string", "enum": ["all", "notes", "jira"], "default": "all" },
      "facets": {
        "type": "object",
        "description": "Frontmatter facets to filter on (e.g. project, status, type).",
        "additionalProperties": { "type": "string" }
      }
    },
    "additionalProperties": false
  }
}
```

Maps to: `services.retrieval.pipeline.retrieve_with_intent(query, top_k, source_filter, facets)`.

Output:

```json
{
  "results": [
    {
      "path": "memory/jira/ONB/ONB-142.md",
      "title": "ONB-142 — Session expires during onboarding wizard",
      "snippet": "…the session timeout in OAuth flow drops the user…",
      "score": 0.87,
      "source": "jira",
      "chunk_id": "ONB-142#description"
    }
  ],
  "meta": { "jarvis_session_url": "http://127.0.0.1:3000/search?q=…&via=mcp" }
}
```

### `jarvis_search_notes`

Same shape as `search_memory` but `source_filter="notes"` is locked.
Useful when an agent only wants knowledge-base hits (skips Jira clutter).

### `jarvis_search_jira`

Same shape, `source_filter="jira"` locked. Adds an optional `status`
facet for the common case ("find open issues about X").

### `jarvis_note_read`

```json
{
  "description": "Read a single note by its workspace-relative path. Returns frontmatter + body, optionally truncated.",
  "cost_class": "cheap",
  "max_output_tokens": 4000,
  "input_schema": {
    "type": "object",
    "required": ["path"],
    "properties": {
      "path":      { "type": "string", "maxLength": 500 },
      "max_chars": { "type": "integer", "minimum": 200, "maximum": 50000, "default": 8000 },
      "include_frontmatter": { "type": "boolean", "default": true }
    },
    "additionalProperties": false
  }
}
```

Maps to: `services.memory_service.get_note(path)`. Reuses
`_validate_path` so traversal is impossible.

### `jarvis_note_list`

```json
{
  "description": "List notes in a folder, optionally filtered by tag, type, or modified date. Returns paths + titles only — cheap directory listing.",
  "cost_class": "cheap",
  "max_output_tokens": 2000,
  "input_schema": {
    "type": "object",
    "properties": {
      "folder":         { "type": "string", "default": "", "maxLength": 200 },
      "tag":            { "type": "string", "maxLength": 50 },
      "type":           { "type": "string", "maxLength": 50 },
      "modified_after": { "type": "string", "format": "date" },
      "limit":          { "type": "integer", "minimum": 1, "maximum": 200, "default": 50 }
    },
    "additionalProperties": false
  }
}
```

Maps to: `services.memory_service.list_notes(...)`.

### `jarvis_note_outline`

```json
{
  "description": "Return only the headings + frontmatter of a note. Use this to navigate a long note before deciding which section to read in full.",
  "cost_class": "cheap",
  "max_output_tokens": 1000,
  "input_schema": {
    "type": "object",
    "required": ["path"],
    "properties": {
      "path": { "type": "string", "maxLength": 500 }
    },
    "additionalProperties": false
  }
}
```

New thin helper: parses headings (`^#{1,6} `) and returns them with line
numbers. ~50 LOC in `services.memory_service`.

### `jarvis_graph_query`

```json
{
  "description": "Query the knowledge graph around an entity (person, project, Jira key, concept). Returns neighbors with edge types.",
  "cost_class": "cheap",
  "max_output_tokens": 2000,
  "input_schema": {
    "type": "object",
    "required": ["entity"],
    "properties": {
      "entity":        { "type": "string", "maxLength": 200 },
      "relation_type": { "type": "string", "maxLength": 50 },
      "depth":         { "type": "integer", "minimum": 1, "maximum": 3, "default": 1 }
    },
    "additionalProperties": false
  }
}
```

Maps to: `services.graph_service.queries.query_entity(...)`.

### `jarvis_graph_neighbors`

Same as `query` but takes a `node_id` (canonical form, e.g. `person:adam-nowak`)
rather than a free-text entity. For agents that already have the canonical
ID from a previous call. Maps to `queries.get_neighbors`.

### `jarvis_graph_entity_detail`

```json
{
  "description": "Get full details about a graph node: aliases, mentions count, top related notes/issues. Use after query_graph identifies an entity.",
  "cost_class": "cheap",
  "max_output_tokens": 1500,
  "input_schema": {
    "type": "object",
    "required": ["node_id"],
    "properties": { "node_id": { "type": "string", "maxLength": 200 } },
    "additionalProperties": false
  }
}
```

Maps to: `services.graph_service.queries.get_node_detail`.

### `jarvis_graph_path_between`

```json
{
  "description": "Find the shortest connection path between two entities in the knowledge graph. Returns the sequence of nodes + edge types. Use to explain how X relates to Y.",
  "cost_class": "medium",
  "max_output_tokens": 1500,
  "input_schema": {
    "type": "object",
    "required": ["source", "target"],
    "properties": {
      "source":    { "type": "string", "maxLength": 200 },
      "target":    { "type": "string", "maxLength": 200 },
      "max_depth": { "type": "integer", "minimum": 1, "maximum": 5, "default": 4 }
    },
    "additionalProperties": false
  }
}
```

Reuses `services.retrieval.pipeline._shortest_weighted_path` (already
implemented for graph-aware retrieval) — promote to public API in
`graph_service.queries.shortest_path`.

### `jarvis_jira_describe_issue`

```json
{
  "description": "Get a Jira issue by key with the Jarvis-enriched summary, next steps, risk level, and graph neighbors. Much cheaper than reading raw Jira XML.",
  "cost_class": "medium",
  "max_output_tokens": 4000,
  "input_schema": {
    "type": "object",
    "required": ["issue_key"],
    "properties": {
      "issue_key":         { "type": "string", "pattern": "^[A-Z][A-Z0-9_]+-[0-9]+$" },
      "include_comments":  { "type": "boolean", "default": false },
      "include_neighbors": { "type": "boolean", "default": true }
    },
    "additionalProperties": false
  }
}
```

Maps to: `services.tools.jira_tools.jira_describe_issue`.

### `jarvis_jira_list_issues`

```json
{
  "description": "Filter Jira issues by project, status, assignee, sprint, label. Returns key + title + status only — call jarvis_jira_describe_issue for details.",
  "cost_class": "cheap",
  "max_output_tokens": 2000,
  "input_schema": {
    "type": "object",
    "properties": {
      "project":  { "type": "string", "maxLength": 50 },
      "status":   { "type": "string", "enum": ["to-do", "in-progress", "done"] },
      "assignee": { "type": "string", "maxLength": 100 },
      "sprint":   { "type": "string", "maxLength": 100 },
      "label":    { "type": "string", "maxLength": 50 },
      "limit":    { "type": "integer", "minimum": 1, "maximum": 100, "default": 20 }
    },
    "additionalProperties": false
  }
}
```

### `jarvis_jira_blockers_of` / `jarvis_jira_depends_on`

Both `cost_class: cheap`, max 1,500 tokens. Take `issue_key` + optional
`max_depth` (default 2). Direct delegation to existing functions in
`services.tools.jira_tools`.

### `jarvis_jira_sprint_risk`

```json
{
  "description": "Risk overview for a sprint: ranked list of at-risk issues with reasons (overdue, missing assignee, hidden concerns from enrichment, blockers). Replaces dumping 40 issues into the prompt.",
  "cost_class": "medium",
  "max_output_tokens": 3000,
  "input_schema": {
    "type": "object",
    "required": ["sprint"],
    "properties": {
      "sprint": { "type": "string", "maxLength": 100 },
      "limit":  { "type": "integer", "minimum": 1, "maximum": 50, "default": 15 }
    },
    "additionalProperties": false
  }
}
```

### `jarvis_jira_cluster_by_topic`

```json
{
  "description": "Group Jira issues by semantic topic using existing chunk embeddings. Returns clusters with representative issues.",
  "cost_class": "medium",
  "max_output_tokens": 3000,
  "input_schema": {
    "type": "object",
    "properties": {
      "project":      { "type": "string", "maxLength": 50 },
      "sprint":       { "type": "string", "maxLength": 100 },
      "min_cluster":  { "type": "integer", "minimum": 2, "maximum": 20, "default": 3 },
      "max_clusters": { "type": "integer", "minimum": 2, "maximum": 20, "default": 8 }
    },
    "additionalProperties": false
  }
}
```

### `jarvis_session_recent`

```json
{
  "description": "List recent Jarvis chat sessions with topic + last message timestamp. Use to remind the agent what the user has been working on.",
  "cost_class": "cheap",
  "max_output_tokens": 1500,
  "input_schema": {
    "type": "object",
    "properties": {
      "limit":      { "type": "integer", "minimum": 1, "maximum": 50, "default": 10 },
      "days_back":  { "type": "integer", "minimum": 1, "maximum": 365, "default": 14 }
    },
    "additionalProperties": false
  }
}
```

Maps to: `services.session_service.list_sessions(limit)` filtered by date.

### `jarvis_session_recent_decisions`

```json
{
  "description": "Find decisions the user has made recently — mined from saved sessions where the assistant or user wrote phrases like 'we decided', 'let's go with', 'final answer'. Filterable by topic.",
  "cost_class": "medium",
  "max_output_tokens": 3000,
  "input_schema": {
    "type": "object",
    "properties": {
      "topic":     { "type": "string", "maxLength": 200 },
      "days_back": { "type": "integer", "minimum": 1, "maximum": 90, "default": 14 },
      "limit":     { "type": "integer", "minimum": 1, "maximum": 30, "default": 10 }
    },
    "additionalProperties": false
  }
}
```

New helper in `session_service.find_decisions(topic, days_back, limit)`:

- Loads sessions from the last N days.
- Greps message bodies for decision markers (configurable list).
- Optional topic: hybrid search inside session bodies first.
- Returns `[{session_id, ts, snippet, topic_tags}]`.

### `jarvis_session_tool_history`

```json
{
  "description": "What tools were called in recent sessions (and how often). Helps an external agent avoid repeating Jarvis-side work.",
  "cost_class": "cheap",
  "max_output_tokens": 1000,
  "input_schema": {
    "type": "object",
    "properties": {
      "days_back": { "type": "integer", "minimum": 1, "maximum": 30, "default": 7 }
    },
    "additionalProperties": false
  }
}
```

Reads from `session_service`'s recorded tool-use logs.

### `jarvis_get_preferences`

```json
{
  "description": "Return saved user preferences, optionally filtered by category (e.g. 'coding', 'language', 'testing'). Use to align with user style without asking the user again.",
  "cost_class": "cheap",
  "max_output_tokens": 1000,
  "input_schema": {
    "type": "object",
    "properties": {
      "category": { "type": "string", "maxLength": 50 }
    },
    "additionalProperties": false
  }
}
```

Maps to: `services.preference_service.load_preferences()`, filtered
by category prefix.

### `jarvis_list_specialists`

Returns the user's defined specialists (curated personas). Lets an
agent know "there's a `frontend-architect` persona; you can mimic its
focus areas for this kind of question." Maps to
`services.specialist_service.list_specialists()`.

### `jarvis_workspace_stats`

```json
{
  "description": "Counts and freshness summary: notes, jira issues, embedded chunks, graph nodes, last enrichment run. Lets agents know what Jarvis can answer.",
  "cost_class": "cheap",
  "max_output_tokens": 600
}
```

### Opt-in writes (require `mcp.allow_writes = true`)

#### `jarvis_save_preference`

```json
{
  "description": "Persist a user preference Jarvis will recall in every future session and tool call.",
  "cost_class": "cheap",
  "max_output_tokens": 200,
  "input_schema": {
    "type": "object",
    "required": ["category", "rule"],
    "properties": {
      "category": { "type": "string", "maxLength": 50 },
      "rule":     { "type": "string", "maxLength": 1000 }
    },
    "additionalProperties": false
  }
}
```

#### `jarvis_append_note`

Append (never overwrite) a block to an existing note. Refuses to create
new notes — forces the user to create the file in Jarvis UI first. Reuses
`memory_service.append_note`.

#### `jarvis_summarize_and_save`

Wraps `services.tools.executor._execute_summarize` so an external agent
can say "save this conversation summary into today's daily note." Uses
local LLM only when privacy mode allows; otherwise returns text without
saving.

---

## Cost-class enforcement

In `services/mcp/server.py`:

```python
async def call_tool(self, name: str, args: dict, *, client_id: str) -> dict:
    tool = self._tools.get(name)
    if tool is None:
        raise UnknownToolError(name)
    if tool.write and not allow_writes_enabled():
        raise UnknownToolError(name)  # not advertised, not callable
    if tool.requires_external_network:
        from services.privacy import is_offline_mode
        if is_offline_mode():
            raise PrivacyBlockedError(f"{name} blocked by offline mode")
    validate_against_schema(args, tool.input_schema)
    raw = await tool.handler(args)
    return _enforce_output_budget(raw, tool.max_output_tokens)
```

`_enforce_output_budget` measures the result with `tiktoken` (cl100k
encoder; cheap, no API). If the result fits, returned as-is. If it
overflows, the helper:

1. Truncates the bulky list/text to the token budget.
2. Adds `"truncated": true` and `"continuation_token": "<opaque>"` keys.
3. Stores the remaining payload in an in-memory LRU keyed by the token
   (TTL 5 min, capped at 50 entries).

Clients can call `jarvis_continue` (a built-in tool) with the token to
fetch the next chunk. This means **the agent decides whether to spend
tokens on the rest** instead of being forced into a 50k blob.

---

## Server skeleton (`services/mcp/server.py`)

```python
from typing import Any, Callable, Awaitable
from dataclasses import dataclass

@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    handler: Callable[[dict], Awaitable[dict]]

class JarvisMCPServer:
    """Transport-agnostic MCP server. Holds tool registry + dispatch."""

    def __init__(self, tools: list[ToolSpec]) -> None:
        self._tools = {t.name: t for t in tools}

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    async def call_tool(self, name: str, args: dict, *, client_id: str) -> dict:
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownToolError(name)
        validate_against_schema(args, tool.input_schema)  # jsonschema
        async with mcp_logging.scope(tool=name, args=args, client=client_id):
            return await tool.handler(args)
```

Validation is **strict** — extra fields are rejected, not ignored. This
prevents prompt-injected agents from sneaking in side-channel parameters.

---

## Auth (`services/mcp/auth.py`)

```python
TOKEN_FILE = "app/mcp_token"
TOKEN_BYTES = 32  # 256 bits

def ensure_token(workspace_path: Path) -> str:
    p = workspace_path / TOKEN_FILE
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(TOKEN_BYTES)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(token, encoding="utf-8")
    p.chmod(0o600)
    return token

def regenerate_token(workspace_path: Path) -> str:
    p = workspace_path / TOKEN_FILE
    if p.exists():
        p.unlink()
    return ensure_token(workspace_path)

def verify_bearer(header: str | None, expected: str) -> bool:
    if not header or not header.startswith("Bearer "):
        return False
    return secrets.compare_digest(header[7:], expected)  # constant-time
```

stdio transport skips auth (the OS process boundary is the auth).
SSE transport requires `Authorization: Bearer <token>` on every request
(both `GET /sse` and `POST /messages`). Missing/wrong → `401`.

---

## Lifecycle API (`routers/mcp.py`)

| Endpoint | Body | Response |
|---|---|---|
| `GET  /api/mcp/status` | — | `{ running, transport, port?, token_set, calls_today, last_call }` |
| `POST /api/mcp/start`  | `{ "transport": "sse", "port": 8765 }` | `{ ok, port, snippet }` |
| `POST /api/mcp/stop`   | — | `{ ok }` |
| `POST /api/mcp/regenerate-token` | — | `{ ok }` (does not return token; UI must re-fetch) |
| `GET  /api/mcp/token`  | — | `{ token }` (returns full token; only over loopback) |

The `start` action launches the SSE server in an **asyncio task** of the
FastAPI app — no subprocess. `stop` cancels the task and closes
listeners. State (`running`, `port`) lives in a module-level singleton.

stdio transport is **not** controlled via this API — clients spawn the
process themselves via `python -m services.mcp --transport stdio`.

---

## Privacy integration

In `services/mcp/server.py`, before dispatching:

```python
async def call_tool(self, name: str, args: dict, *, client_id: str) -> dict:
    tool = self._tools.get(name)
    if tool is None:
        raise UnknownToolError(name)
    # Future-proof: if a tool declares `requires_external_network=True`,
    # privacy gate runs here. None of the MVP tools do.
    if tool.requires_external_network:
        from services.privacy import is_offline_mode, web_search_enabled
        if is_offline_mode() or not web_search_enabled():
            raise PrivacyBlockedError(f"{name} blocked by privacy settings")
    validate_against_schema(args, tool.input_schema)
    return await tool.handler(args)
```

For the MVP no tool sets that flag, but the hook is in place so we don't
forget when (e.g.) `jarvis_web_search` lands.

---

## Logging (`services/mcp/logging.py`)

Append-only JSONL at `app/logs/mcp.jsonl`. Rotated daily (simple: rename
to `mcp-YYYY-MM-DD.jsonl` on first write of a new day). One line per
call, with arg hashing:

```python
def hash_args(args: dict) -> str:
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

Errors are logged with `error.type` and `error.message` but **never** the
stack trace (could leak file paths to the log).

`GET /api/mcp/status` returns aggregated stats from this file (calls
today, last call timestamp, top tool by count).

---

## Runner (`services/mcp/runner.py`)

```bash
python -m services.mcp --transport stdio
python -m services.mcp --transport sse --port 8765 --token-file ~/Jarvis/app/mcp_token
```

For stdio: instantiate the server, attach the stdio transport, run
forever. No HTTP, no port, no auth. Designed for clients that spawn it
as a subprocess.

For SSE: prefer the in-process FastAPI lifecycle (started via the API).
The CLI is a fallback for users who want to run the SSE server
standalone (e.g. as a system service).

---

## SQLite read-only connections

```python
def ro_connect(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True, check_same_thread=False)
```

All MCP tool handlers that touch the DB use this. Guarantees the MCP
server cannot corrupt or write the DB even if a handler has a bug.
Verify WAL mode in `models/database.py` so concurrent reads with the
FastAPI writer work.

---

## New helpers required outside `services/mcp/`

MCP must not embed business logic. The following thin helpers are
added to existing services so MCP handlers stay one-liners:

| Helper | Module | Notes |
|---|---|---|
| `outline_note(path) -> list[Heading]` | `services.memory_service` | Parses `^#{1,6} ` lines, returns `[{level, text, line}]` |
| `shortest_path(source, target, max_depth)` | `services.graph_service.queries` | Promote existing private `_shortest_weighted_path` from retrieval pipeline |
| `find_decisions(topic, days_back, limit)` | `services.session_service` | Hybrid search inside session bodies + decision-marker grep; markers configurable in `config.json` (`decision_markers`) |
| `recent_tool_use(days_back) -> dict[str, int]` | `services.session_service` | Aggregates the existing per-session tool-use log |
| `workspace_stats() -> dict` | `services.workspace_service` | Counts notes, jira, chunks, graph nodes, last enrichment ts |

Each helper has its own unit test in the matching service test file
(not in `test_mcp_*`).

---

## Tests

### `test_mcp_tools.py`

- Each of the 15 read tools: happy path returns expected shape.
- Each of the 3 write tools: callable when `mcp.allow_writes=true`,
  hidden from `tools/list` when `false`, calling raises
  `UnknownToolError` when `false`.
- Each tool: invalid args (extra field, wrong type, out-of-range) raise
  validation error, never reach the handler.
- `jarvis_note_read`: path traversal (`../../etc/passwd`) is rejected
  by the existing validator.
- `jarvis_search_memory` returns at most `top_k` results, in
  descending score order.
- Cost-budget enforcement: a synthetic large result truncates and
  returns `continuation_token`; calling `jarvis_continue` returns the
  rest; expired token returns a clear error.
- Tool count assertion: `len(server.list_tools()) == 15` with
  `allow_writes=false`, `== 18` with `allow_writes=true`.

### `test_mcp_auth.py`

- `ensure_token` creates the file with `0o600`.
- `regenerate_token` rotates the value.
- `verify_bearer`: missing header → `False`, wrong scheme → `False`,
  wrong token → `False`, correct token → `True`.
- SSE endpoints reject requests without `Authorization`.

### `test_mcp_privacy.py`

- With `JARVIS_OFFLINE_MODE=1`, the MCP server starts successfully.
- All read-only tools work in offline mode (they're local).
- A test tool with `requires_external_network=True` fails with
  `PrivacyBlockedError` in offline mode.

### `test_mcp_concurrency.py`

- 50 concurrent `jarvis_search_memory` calls don't lock against a
  concurrent FastAPI write to the same DB (validates WAL + RO).

---

## Acceptance criteria

- [ ] `services/mcp/` package implemented with **all 18 tools** (15 read
      + 3 opt-in write).
- [ ] Write tools are hidden from `tools/list` when
      `mcp.allow_writes=false` (default).
- [ ] `cost_class` and `max_output_tokens` enforced; oversized results
      truncate with a `continuation_token` resolved by
      `jarvis_continue`.
- [ ] stdio transport works: `python -m services.mcp --transport stdio`
      passes a manual MCP handshake (`initialize`, `tools/list`,
      `tools/call`).
- [ ] SSE transport starts via `POST /api/mcp/start`, serves on
      `127.0.0.1:8765`, requires bearer token, stops cleanly on
      `POST /api/mcp/stop`.
- [ ] `app/mcp_token` is created with `0o600` on first start, never
      logged, regeneratable.
- [ ] `app/logs/mcp.jsonl` is written on every call with arg hash and
      output-token estimate; daily rotated.
- [ ] Privacy tests pass: offline mode allows all read/write tools (all
      local), would block any future `requires_external_network` tool.
- [ ] All new tests pass; existing test suites unaffected.
- [ ] `pip install -e backend && python -m services.mcp --help` works
      out of the box.

---

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| MCP SDK ABI churn (early-stage spec) | Pin the SDK version; abstract behind our `JarvisMCPServer`. |
| Tool returns 100k-token blob, blowing client's context | Hard cap output size in each handler (`max_chars`, `top_k`); doc the cap. |
| Two MCP servers fight over port 8765 | `start` checks port availability and returns `409` with the conflicting PID if found. |
| Token leaks into logs / git | `app/mcp_token` is in `.gitignore`; logging filters strip `Authorization` header. |
| Future tool accidentally writes to DB | Read-only connection helper; integration test asserts `OperationalError` on any write. Write tools use a separate read-write connection and are explicitly opt-in. |
| Tool count creep → prompt bloat in client | Each tool description is hard-capped at 400 chars; `tools/list` total payload asserted ≤ 6k tokens in `test_mcp_tools.py`. |
| Cost budgets misjudged for some workloads | Budgets are `config.json` overridable per tool (`mcp.tool_budgets`); `mcp.jsonl` records actual output tokens so budgets can be tuned with data. |
