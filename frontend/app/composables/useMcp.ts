/**
 * useMcp — composable for managing the local MCP server lifecycle.
 *
 * Wraps the backend `/api/mcp/*` endpoints and exposes a small reactive
 * surface used by the StatusBar toggle and the Settings → MCP Server
 * panel.
 *
 * The MCP server exposes ~22 read tools (plus 3 opt-in write tools) that
 * cover EVERY note, conversation, Jira issue, and graph entity in the
 * workspace — not just Jira data.
 */

import { ref, computed, readonly } from 'vue'

export interface McpStatus {
  running: boolean
  transport: string | null
  port: number | null
  token_set: boolean
  tool_count: number
  calls_today: number
  last_call: string | null
  top_tool: string | null
  python_path: string
  backend_dir: string
  workspace_path: string
}

export interface McpStartResponse {
  ok: boolean
  port: number
  tool_count: number
}

const status = ref<McpStatus>({
  running: false,
  transport: null,
  port: null,
  token_set: false,
  tool_count: 0,
  calls_today: 0,
  last_call: null,
  top_tool: null,
  python_path: '',
  backend_dir: '',
  workspace_path: '',
})

const token = ref<string>('')
const loading = ref(false)
const error = ref<string | null>(null)
let pollTimer: ReturnType<typeof setInterval> | null = null

async function refreshStatus(): Promise<void> {
  try {
    status.value = await $fetch<McpStatus>('/api/mcp/status')
    error.value = null
  } catch (e) {
    error.value = (e as { statusMessage?: string })?.statusMessage ?? 'Failed to fetch MCP status'
  }
}

async function start(port = 8765): Promise<McpStartResponse | null> {
  loading.value = true
  error.value = null
  try {
    const res = await $fetch<McpStartResponse>('/api/mcp/start', {
      method: 'POST',
      body: { transport: 'sse', port },
    })
    await refreshStatus()
    await fetchToken()
    return res
  } catch (e: unknown) {
    const httpStatus = (e as { status?: number })?.status
    if (httpStatus === 409) {
      // Already running — sync UI state and clear error
      await refreshStatus()
      await fetchToken()
      error.value = null
      return null
    }
    error.value = (e as { statusMessage?: string })?.statusMessage ?? 'Failed to start MCP server'
    return null
  } finally {
    loading.value = false
  }
}

async function stop(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    await $fetch('/api/mcp/stop', { method: 'POST' })
    await refreshStatus()
  } catch (e) {
    error.value = (e as { statusMessage?: string })?.statusMessage ?? 'Failed to stop MCP server'
  } finally {
    loading.value = false
  }
}

async function fetchToken(): Promise<void> {
  try {
    const res = await $fetch<{ token: string }>('/api/mcp/token')
    token.value = res.token
  } catch (e) {
    error.value = (e as { statusMessage?: string })?.statusMessage ?? 'Failed to fetch token'
  }
}

async function regenerateToken(): Promise<void> {
  loading.value = true
  try {
    await $fetch('/api/mcp/regenerate-token', { method: 'POST' })
    await fetchToken()
    await refreshStatus()
  } catch (e) {
    error.value = (e as { statusMessage?: string })?.statusMessage ?? 'Failed to regenerate token'
  } finally {
    loading.value = false
  }
}

function startPolling(intervalMs = 5000): void {
  if (pollTimer) return
  void refreshStatus()
  pollTimer = setInterval(() => {
    void refreshStatus()
  }, intervalMs)
}

function stopPolling(): void {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// ---------------------------------------------------------------------------
// Snippet generators — produce ready-to-paste client configs.
// ---------------------------------------------------------------------------

export interface SnippetContext {
  pythonPath: string
  backendDir: string
  workspacePath: string
  port: number
  token: string
  sseUrl: string
}

function jsonStringify(obj: unknown): string {
  return JSON.stringify(obj, null, 2)
}

/** Claude Desktop / Cursor / Continue / Zed — stdio MCP config. */
export function buildStdioConfig(ctx: SnippetContext): string {
  return jsonStringify({
    mcpServers: {
      jarvis: {
        command: ctx.pythonPath,
        args: ['-m', 'services.mcp', '--transport', 'stdio'],
        cwd: ctx.backendDir,
        env: {
          JARVIS_WORKSPACE: ctx.workspacePath,
        },
      },
    },
  })
}

/** SSE transport — for clients that talk to a long-running HTTP endpoint. */
export function buildSseConfig(ctx: SnippetContext): string {
  return jsonStringify({
    mcpServers: {
      jarvis: {
        url: ctx.sseUrl,
        transport: 'sse',
        headers: {
          Authorization: `Bearer ${ctx.token || '<RUN-MCP-FIRST-TO-GET-TOKEN>'}`,
        },
      },
    },
  })
}

/** VS Code / GitHub Copilot — `.vscode/mcp.json` style. */
export function buildVscodeConfig(ctx: SnippetContext): string {
  return jsonStringify({
    servers: {
      jarvis: {
        type: 'stdio',
        command: ctx.pythonPath,
        args: ['-m', 'services.mcp', '--transport', 'stdio'],
        cwd: ctx.backendDir,
        env: {
          JARVIS_WORKSPACE: ctx.workspacePath,
        },
      },
    },
  })
}

export function useMcp() {
  return {
    status: readonly(status),
    token: readonly(token),
    loading: readonly(loading),
    error: readonly(error),
    running: computed(() => status.value.running),
    refreshStatus,
    start,
    stop,
    fetchToken,
    regenerateToken,
    startPolling,
    stopPolling,
    buildStdioConfig,
    buildSseConfig,
    buildVscodeConfig,
  }
}
