# Jarvis MCP — Ready-to-Paste Client Configs

Drop-in JSON snippets for connecting popular AI clients to your local Jarvis
MCP server. All snippets default to the **stdio** transport, which is the
simplest setup — the client launches Jarvis on demand, no SSE server required,
no token to manage.

> **Scope:** these configs expose ~22 read-only tools spanning **all notes,
> conversations, Jira issues, and graph entities** in your workspace — not
> just Jira data. Three opt-in write tools (`jarvis_save_preference`,
> `jarvis_append_note`, `jarvis_summarize_and_save`) are disabled unless
> `mcp.allow_writes: true` is set in your workspace `app/config.json`.

> **Paths:** The `<JARVIS_BACKEND>` and `<JARVIS_WORKSPACE>` placeholders in the JSON files below are filled in automatically by the **Settings → MCP Server** snippet generator in the Jarvis UI. Copy the generated snippet from there — it will contain your actual paths. The JSON files in this folder are reference templates only.

---

## Claude Desktop

**File:** `~/Library/Application Support/Claude/claude_desktop_config.json`
(macOS) · `%APPDATA%/Claude/claude_desktop_config.json` (Windows)

Paste [`claude-desktop.json`](./claude-desktop.json), then restart Claude
Desktop. Look for the 🔌 plug icon in the message composer to confirm
Jarvis is connected.

## Cursor

**File:** `~/.cursor/mcp.json` · or via UI: **Settings → Cursor Settings →
MCP → Add new MCP server**.

Paste [`cursor.json`](./cursor.json) and toggle the server on. Cursor will
auto-discover tools on next chat.

## VS Code / GitHub Copilot

**File:** `<workspace>/.vscode/mcp.json` (workspace-scoped) or via
**Settings → Features → Chat → MCP: Servers → Edit in settings.json**.

Paste [`vscode-copilot.json`](./vscode-copilot.json). Requires VS Code
≥ 1.94 with MCP support enabled in Copilot Chat.

## Continue.dev

**File:** `~/.continue/config.json` — merge the `experimental` block from
[`continue.json`](./continue.json) into your existing config.

## SSE / HTTP (any other MCP client)

For clients that only speak HTTP/SSE:

1. Open Jarvis → **Settings → MCP Server**.
2. Click **Start SSE on :8765**.
3. Click **Reveal** under "Bearer token", then **Copy**.
4. Paste [`sse-http.json`](./sse-http.json) into your client and replace
   `REPLACE_WITH_TOKEN_FROM_SETTINGS_PAGE` with the copied token.

The token lives at `app/mcp_token` in your workspace (mode `0600`) and is
gitignored. Regenerate any time from the Settings panel.

---

## Verify a working connection

Once connected, ask the AI client:

> "Use jarvis_workspace_stats to show me what's indexed."

A successful response returns counts of notes, Jira issues, chunks, graph
nodes & edges, plus the last enrichment timestamp.

Other quick smoke tests:

- `jarvis_search_memory("decision about postgres", k=5)` — universal hybrid
  search across notes + sessions + Jira.
- `jarvis_session_recent(limit=10)` — recent conversations.
- `jarvis_note_outline(folder="meetings")` — table of contents for any folder.
- `jarvis_graph_neighbors(entity="JARVIS-123", depth=2)` — graph walk.

## Tool surface (25 total)

| Namespace | Tools | Purpose |
|---|---|---|
| `jarvis_search_*` | 3 | Hybrid BM25 + embeddings over notes / Jira / unified |
| `jarvis_note_*` | 3 | Read / list / outline any markdown note |
| `jarvis_session_*` | 3 | Conversation history, decisions, tool-call timeline |
| `jarvis_graph_*` | 4 | Knowledge-graph query, neighbors, paths, entity detail |
| `jarvis_jira_*` | 6 | Issue describe, list, blockers, sprint risk, clustering |
| `jarvis_get_preferences`, `jarvis_list_specialists`, `jarvis_workspace_stats` | 3 | Meta |
| **Opt-in writes** (off by default) | 3 | Save preference, append note, summarize+save |

See [`../README.md`](../README.md) and `docs/steps/step-24*-mcp-server.spec.md`
for protocol details, cost classes, and per-tool budgets.
