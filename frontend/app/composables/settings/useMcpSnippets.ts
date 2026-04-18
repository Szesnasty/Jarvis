import { computed, ref } from 'vue'
import { useMcp } from '~/composables/useMcp'

export type SnippetId = 'claude' | 'cursor' | 'vscode' | 'continue' | 'zed'

export interface SnippetTab {
  id: SnippetId
  label: string
  hint: string
  path: string
  builder: 'stdio' | 'vscode'
}

export const SNIPPET_TABS: SnippetTab[] = [
  {
    id: 'claude',
    label: 'Claude Desktop',
    hint: 'Claude Desktop launches jarvis-mcp on demand over stdio. Nothing else to configure.',
    path: '~/Library/Application Support/Claude/claude_desktop_config.json',
    builder: 'stdio',
  },
  {
    id: 'cursor',
    label: 'Cursor',
    hint: 'Cursor → Settings → MCP → Add. Drop this in or save to the path below.',
    path: '~/.cursor/mcp.json',
    builder: 'stdio',
  },
  {
    id: 'vscode',
    label: 'VS Code / Copilot',
    hint: 'Works with GitHub Copilot Chat (MCP-enabled) and the Continue extension.',
    path: '<workspace>/.vscode/mcp.json',
    builder: 'vscode',
  },
  {
    id: 'continue',
    label: 'Continue',
    hint: 'Continue.dev config file (used by both VS Code and JetBrains).',
    path: '~/.continue/config.json (mcpServers field)',
    builder: 'stdio',
  },
  {
    id: 'zed',
    label: 'Zed',
    hint: 'Zed → settings.json → context_servers.',
    path: '~/.config/zed/settings.json',
    builder: 'stdio',
  },
]

export function useMcpSnippets() {
  const mcp = useMcp()
  const activeId = ref<SnippetId>('cursor')
  const copied = ref(false)

  const activeTab = computed(() =>
    SNIPPET_TABS.find((t) => t.id === activeId.value) ?? SNIPPET_TABS[0]!,
  )
  const activeText = computed(() => {
    const ctx = mcp.snippetCtx.value
    switch (activeTab.value.builder) {
      case 'vscode': return mcp.buildVscodeConfig(ctx)
      case 'stdio':
      default: return mcp.buildStdioConfig(ctx)
    }
  })

  async function copy() {
    try {
      await navigator.clipboard.writeText(activeText.value)
      copied.value = true
      setTimeout(() => { copied.value = false }, 1500)
    } catch { /* ignore */ }
  }

  return { mcp, activeId, copied, activeTab, activeText, copy, tabs: SNIPPET_TABS }
}

export function formatLastCall(iso: string | null): string {
  if (!iso) return 'never'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const diffSec = Math.floor((Date.now() - d.getTime()) / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  return d.toLocaleString()
}
