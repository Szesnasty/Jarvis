# MCP Server (step 24)

Local Model-Context-Protocol server that lets any MCP-compatible AI client
(Claude Desktop, Cursor, VS Code Copilot, Continue, Zed, …) tap directly
into your Jarvis workspace — notes, conversations, Jira, knowledge graph.

- **Default transport:** stdio (zero-config, no token, no port)
- **Optional transport:** SSE on `127.0.0.1:8765` with bearer-token auth
- **Surface:** 22 read-only tools + 3 opt-in write tools
- **Privacy:** localhost only · token at `app/mcp_token` (mode `0600`) · gitignored
- **Logs:** JSONL append-only at `app/logs/mcp/YYYY-MM-DD.jsonl`

## Quick start

1. **In Jarvis:** Settings → MCP Server → click the toggle next to "Alive" in
   the header (or the Start button on the Settings page) for SSE, or skip
   straight to step 2 for stdio.
2. **Pick your client:** see [`clients/`](./clients/) for ready-to-paste JSON
   configs (Claude Desktop, Cursor, VS Code, Continue, SSE).
3. **Restart the client** and ask: *"Use jarvis_workspace_stats."*

## Specs

- [`step-24-mcp-server.spec.md`](../../steps/step-24-mcp-server.spec.md)
- [`step-24a-mcp-server-backend.spec.md`](../../steps/step-24a-mcp-server-backend.spec.md)
- [`step-24b-mcp-server-frontend.spec.md`](../../steps/step-24b-mcp-server-frontend.spec.md)
- [`step-24c-mcp-client-integration.spec.md`](../../steps/step-24c-mcp-client-integration.spec.md)
