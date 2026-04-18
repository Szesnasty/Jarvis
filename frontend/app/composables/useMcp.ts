/**
 * useMcp — composable for the Settings → MCP Server panel.
 *
 * The MCP server is a standalone CLI (`jarvis-mcp`) that MCP clients
 * (Cursor, Claude Desktop, VS Code, Continue, Zed) launch themselves
 * over stdio. The Jarvis backend does NOT manage its lifecycle — this
 * composable just reports status and renders client config snippets.
 */

import { ref, computed, readonly } from 'vue'

export interface McpInfo {
  cli_on_path: boolean
  cli_path: string | null
  cli_command: string
  workspace_path: string
  backend_dir: string
  tool_count: number
  write_tool_count: number
  audit_log_path: string
  calls_today: number
  last_call: string | null
  top_tool: string | null
}

const info = ref<McpInfo>({
  cli_on_path: false,
  cli_path: null,
  cli_command: 'jarvis-mcp',
  workspace_path: '',
  backend_dir: '',
  tool_count: 0,
  write_tool_count: 0,
  audit_log_path: '',
  calls_today: 0,
  last_call: null,
  top_tool: null,
})

const loading = ref(false)
const error = ref<string | null>(null)

async function refreshInfo(): Promise<void> {
  loading.value = true
  try {
    info.value = await $fetch<McpInfo>('/api/mcp/info')
    error.value = null
  } catch (e) {
    error.value = (e as { statusMessage?: string })?.statusMessage ?? 'Failed to fetch MCP info'
  } finally {
    loading.value = false
  }
}

// ---------------------------------------------------------------------------
// Snippet generators — produce ready-to-paste client configs.
// ---------------------------------------------------------------------------

export interface SnippetContext {
  /** Either "jarvis-mcp" (preferred, CLI on PATH) or absolute path fallback. */
  command: string
  /** True when the CLI is on PATH; affects which snippet is shown. */
  portable: boolean
}

function jsonStringify(obj: unknown): string {
  return JSON.stringify(obj, null, 2)
}

/** Claude Desktop / Cursor / Continue / Zed — stdio MCP config. */
export function buildStdioConfig(ctx: SnippetContext): string {
  return jsonStringify({
    mcpServers: {
      jarvis: {
        command: ctx.command,
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
        command: ctx.command,
      },
    },
  })
}

export function useMcp() {
  const snippetCtx = computed<SnippetContext>(() => ({
    command: info.value.cli_command,
    portable: info.value.cli_on_path,
  }))

  return {
    info: readonly(info),
    loading: readonly(loading),
    error: readonly(error),
    snippetCtx,
    refreshInfo,
    buildStdioConfig,
    buildVscodeConfig,
  }
}
