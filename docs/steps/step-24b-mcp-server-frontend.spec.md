# Step 24b — MCP Server Frontend Toggle

> **Goal**: Surface the MCP server in the Jarvis UI so the user can
> start/stop it, see live status, copy a client config snippet, and
> manage the auth token — all without touching the terminal.

**Status**: ⬜ Not started
**Parent**: [Step 24 — MCP Server overview](step-24-mcp-server.spec.md)
**Depends on**: 24a (backend), feat/privacy-offline-mode (Settings UI patterns)
**Effort**: ~0.5 day

---

## What this step covers

| Feature | Description |
|---|---|
| Settings → MCP Server section | Below "Privacy & Network", above "Maintenance" |
| Start/Stop toggle | Wire-equivalent of the existing "Alive" indicator pattern |
| Status badge | Running / Stopped / Error, with port + uptime |
| Token panel | Show / hide / regenerate, copy-to-clipboard |
| Client snippet generator | Tabs for Cursor / Claude Desktop / Continue / Generic |
| Recent activity | Sparkline of last-hour call count + top tools |
| Composable: `useMcpServer` | Wraps the API, polls status while section visible |

---

## File layout

```
frontend/
  app/
    pages/
      settings.vue            # MODIFY — add new section
    components/
      McpServerPanel.vue      # NEW — status, toggle, stats
      McpTokenManager.vue     # NEW — show/hide/regenerate/copy
      McpClientSnippets.vue   # NEW — tabbed config generator
    composables/
      useMcpServer.ts         # NEW
  tests/
    components/
      McpServerPanel.test.ts  # NEW
      McpClientSnippets.test.ts # NEW
```

---

## UI layout

Inserted right under the **Privacy & Network** section (matches that
section's visual rhythm):

```
┌──────────────────────────────────────────────────────────────────┐
│  MCP Server                              ● Running · :8765 · 12m │
├──────────────────────────────────────────────────────────────────┤
│  Expose Jarvis as a local Model Context Protocol server so       │
│  Cursor, Claude Desktop, and other AI tools can query your       │
│  memory and Jira context without copy-paste.                     │
│                                                                  │
│  ☑ Run MCP server                          [Stop server]         │
│                                                                  │
│  ┌── Auth token ───────────────────────────────────────────┐    │
│  │  •••••••••••••••••••••••••••••••• [👁 Show] [⟳ Rotate] │    │
│  │  Required for HTTP/SSE clients. stdio clients don't     │    │
│  │  need it.                                               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌── Connect from your AI tool ────────────────────────────┐    │
│  │  ┌Cursor┐┌Claude Desktop┐┌Continue┐┌Generic┐           │    │
│  │  │      │└──────────────┘└────────┘└───────┘           │    │
│  │  └──────┘                                               │    │
│  │                                                         │    │
│  │  ```json                                                │    │
│  │  {                                                      │    │
│  │    "mcpServers": {                                      │    │
│  │      "jarvis": {                                        │    │
│  │        "url": "http://127.0.0.1:8765/sse",              │    │
│  │        "headers": {                                     │    │
│  │          "Authorization": "Bearer ••••"                 │    │
│  │        }                                                │    │
│  │      }                                                  │    │
│  │    }                                                    │    │
│  │  }                                                      │    │
│  │  ```                                                    │    │
│  │                          [📋 Copy] [📖 Docs]            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Activity (last hour): ▁▂▅█▇▃▂▁  · 142 calls  · last: 12s ago   │
│  Top tools: jarvis_jira_describe_issue (87), jarvis_search (42) │
└──────────────────────────────────────────────────────────────────┘
```

When **Stopped** the toggle/snippet collapse to a placeholder:
> Server is stopped. Start it to expose Jarvis to other AI tools.

When **Offline mode** is enabled (from Privacy section), show a small
inline note:
> 🛡️ Offline mode is on — MCP server still works for local memory and
> Jira tools. Cloud-bound tools (none in MVP) would be blocked.

---

## Composable (`useMcpServer.ts`)

```typescript
export type McpStatus = {
  running: boolean
  transport: 'sse' | 'stdio' | null
  port: number | null
  token_set: boolean
  calls_today: number
  last_call_at: string | null
  uptime_seconds: number
  top_tools: Array<{ name: string; count: number }>
  hourly_buckets: number[]   // 60 buckets, calls/min
}

export function useMcpServer() {
  const status = useState<McpStatus | null>('mcpStatus', () => null)
  const token  = useState<string | null>('mcpToken', () => null)
  const error  = useState<string>('mcpError', () => '')
  let pollHandle: ReturnType<typeof setInterval> | null = null

  async function refresh() { /* GET /api/mcp/status */ }
  async function start()   { /* POST /api/mcp/start */ }
  async function stop()    { /* POST /api/mcp/stop */ }
  async function loadToken()       { /* GET  /api/mcp/token */ }
  async function regenerateToken() { /* POST /api/mcp/regenerate-token, then loadToken */ }

  function startPolling() {
    refresh()
    pollHandle = setInterval(refresh, 5000)
  }
  function stopPolling() {
    if (pollHandle) clearInterval(pollHandle)
    pollHandle = null
  }

  return { status, token, error, start, stop, loadToken, regenerateToken,
           startPolling, stopPolling, refresh }
}
```

Polling runs **only while the Settings section is visible** — wire to
`onMounted`/`onBeforeUnmount` of `McpServerPanel.vue`. No background
polling on other pages.

---

## Snippet generator (`McpClientSnippets.vue`)

Four tabs, each generates a snippet from the live status + token:

### Cursor (`~/.cursor/mcp.json`)

```json
{
  "mcpServers": {
    "jarvis": {
      "url": "http://127.0.0.1:8765/sse",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

### Claude Desktop (`~/Library/.../claude_desktop_config.json`)

Uses **stdio** transport — no token needed:

```json
{
  "mcpServers": {
    "jarvis": {
      "command": "python",
      "args": ["-m", "services.mcp", "--transport", "stdio"],
      "cwd": "/Users/<you>/path/to/jarvis/backend"
    }
  }
}
```

### Continue (`.continue/config.json`)

Same shape as Cursor (SSE).

### Generic

Plain text instructions: URL, header name, header value, list of
available tools with one-line descriptions.

Each tab has:
- **Copy** button (writes the rendered snippet to clipboard)
- The token is masked in the display, but copied **unmasked** when the
  user clicks Copy.

The path / username placeholders in the Claude Desktop snippet are
filled from `GET /api/settings` (workspace path) — no manual edits.

---

## Token manager (`McpTokenManager.vue`)

- **Show**: replaces `••••` with the real token (after a one-time fetch
  via `GET /api/mcp/token`); auto-hides after 30s.
- **Copy**: copies unmasked token without showing it on screen.
- **Rotate**: confirmation dialog (`"All MCP clients will need to be
  reconfigured. Continue?"`); calls `POST /api/mcp/regenerate-token`
  then refreshes the snippets.

Never log the token to the browser console. The composable scrubs it
from any error toast.

---

## Visual style

Matches the existing **Privacy & Network** section visual style
(established in `feat/privacy-offline-mode`):

- Same panel border, padding, typography.
- Status badge uses the same green for "Running" as Privacy uses for
  "Offline mode active".
- Toggle is a real `<input type="checkbox">` with `.privacy-toggle`
  styling, not a custom switch.
- Code blocks use the existing `JetBrains Mono` token from CSS vars.

No new design tokens introduced — every color/spacing already exists
in `assets/`.

---

## Tests (Vitest)

### `McpServerPanel.test.ts`

- Mounts with `running=false` → shows placeholder + "Start" button.
- Mounts with `running=true` → shows status row + token + snippets.
- Click "Start" → calls `useMcpServer.start()`; on resolve, refreshes.
- Polling registered on mount, cleared on unmount.

### `McpClientSnippets.test.ts`

- Each tab renders correct snippet with the workspace path and a
  masked token.
- Copy button writes the **unmasked** snippet to `navigator.clipboard`.
- When `running=false`, all tabs show a "start the server first"
  placeholder.

---

## Acceptance criteria

- [ ] New Settings section visible between Privacy & Maintenance.
- [ ] Toggle starts/stops the SSE server end-to-end (verifiable via
      `lsof -i :8765`).
- [ ] Token can be revealed, copied, rotated; never persisted to
      browser localStorage.
- [ ] All four snippet tabs produce a config that, when pasted into
      the respective client, results in a working MCP connection
      (manual smoke test, see 24c).
- [ ] Polling stops when leaving the Settings page (no idle network
      noise).
- [ ] Offline-mode banner renders correctly when applicable.
- [ ] All component tests pass.
