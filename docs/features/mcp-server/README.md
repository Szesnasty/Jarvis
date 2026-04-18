# MCP Server

Local Model Context Protocol server that lets any MCP-compatible AI client
(Claude Desktop, Cursor, VS Code Copilot, Continue, Zed, …) tap directly
into your Jarvis workspace — notes, conversations, Jira, knowledge graph.

- **Transport:** stdio only (zero-config, no port, no token)
- **Binary:** `jarvis-mcp` — standalone CLI on your `PATH` after backend install
- **Surface:** 22 read-only tools + 3 opt-in write tools (25 total)
- **Privacy:** runs locally, launched on demand by the client
- **Logs:** JSONL append-only at `app/logs/mcp/YYYY-MM-DD.jsonl`
- **Writes:** disabled unless `mcp.allow_writes: true` in `app/config.json`

## Quick start

1. Open **Settings → MCP** in the Jarvis UI.
2. Pick your client in the snippet switcher.
3. Copy the generated JSON (paths are filled in for your machine).
4. Paste into your client's config file (see [`clients/`](./clients/)).
5. Restart the client and ask: *"Use `jarvis_workspace_stats`."*

## Minimal config (all clients)

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

No `cwd`, no `PYTHONPATH`, no env required — the workspace is auto-discovered.
If `jarvis-mcp` is not on your `PATH`, the Settings snippet generator emits
an absolute-path fallback pointing at `backend/.venv/bin/jarvis-mcp`.

## Ready-to-paste per-client configs

See [`clients/`](./clients/) for:
- [`claude-desktop.json`](./clients/claude-desktop.json)
- [`cursor.json`](./clients/cursor.json)
- [`vscode-copilot.json`](./clients/vscode-copilot.json)
- [`continue.json`](./clients/continue.json)

## Tools

22 read-only + 3 opt-in write. Categories: `search`, `memory`, `graph`,
`sessions`, `jira`, `workspace`, `preferences`. Each tool is tagged with a
cost class (`free` / `cheap` / `standard` / `premium`) for per-session
budget caps — configurable in Settings → MCP.

## Specs

- [`refactor.spec.md`](./refactor.spec.md) — historical refactor notes
  (CLI-only, stdio-only architecture)
- [`../../steps/step-24*-mcp-*.spec.md`](../../steps/) — original design specs

> **Historical note:** earlier versions shipped an optional SSE transport
> on `127.0.0.1:8765` with a bearer token. That was removed in favour of
> the simpler stdio-only model: clients spawn `jarvis-mcp` themselves, so
> there's no background server, no port, and no token to manage.

