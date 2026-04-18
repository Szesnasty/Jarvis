<template>
  <SettingsSection
    id="mcp"
    title="MCP Server"
    section-class="mcp-section"
    :default-open="false"
  >
    <template #suffix>
      <span
        class="mcp-section__pill"
        :class="{ 'mcp-section__pill--on': mcp.info.value.cli_on_path }"
      >
        <span class="mcp-section__dot" />
        {{ mcp.info.value.cli_on_path ? 'CLI on PATH' : 'CLI not on PATH' }}
      </span>
    </template>

    <p class="mcp-section__lead">
      Expose your <strong>entire workspace</strong> — every note, conversation,
      Jira issue and graph entity — to any MCP-compatible AI client
      (Claude Desktop, Cursor, VS Code Copilot, Continue, Zed). Read-only
      by default, runs locally as a stdio CLI launched on demand by your
      client. Nothing leaves your machine.
    </p>

    <div class="mcp-section__grid">
      <div class="mcp-stat">
        <span class="mcp-stat__label">Read tools</span>
        <span class="mcp-stat__value">{{ mcp.info.value.tool_count }}</span>
      </div>
      <div class="mcp-stat">
        <span class="mcp-stat__label">Write tools (opt-in)</span>
        <span class="mcp-stat__value">{{ mcp.info.value.write_tool_count }}</span>
      </div>
      <div class="mcp-stat">
        <span class="mcp-stat__label">Calls today</span>
        <span class="mcp-stat__value">{{ mcp.info.value.calls_today }}</span>
      </div>
      <div class="mcp-stat">
        <span class="mcp-stat__label">Top tool</span>
        <span class="mcp-stat__value mcp-stat__value--small">{{ mcp.info.value.top_tool || '—' }}</span>
      </div>
      <div class="mcp-stat">
        <span class="mcp-stat__label">Last call</span>
        <span class="mcp-stat__value mcp-stat__value--small">{{ formatLastCall(mcp.info.value.last_call) }}</span>
      </div>
      <div class="mcp-stat">
        <span class="mcp-stat__label">Workspace</span>
        <span class="mcp-stat__value mcp-stat__value--small" :title="mcp.info.value.workspace_path">
          {{ mcp.info.value.workspace_path || '—' }}
        </span>
      </div>
    </div>

    <div v-if="!mcp.info.value.cli_on_path" class="mcp-section__error">
      <strong>jarvis-mcp</strong> isn't on your <code>PATH</code>. The bootstrap installer normally
      symlinks it to <code>~/.local/bin</code>. Either re-run <code>scripts/install-backend.mjs</code>,
      or use the absolute path snippet below: <code>{{ mcp.info.value.cli_command }}</code>
    </div>

    <div v-if="mcp.error.value" class="mcp-section__error">{{ mcp.error.value }}</div>

    <div class="settings-page__actions mcp-section__actions">
      <button class="settings-page__btn" :disabled="mcp.loading.value" @click="mcp.refreshInfo">
        {{ mcp.loading.value ? 'Refreshing…' : 'Refresh' }}
      </button>
      <a class="settings-page__btn" href="/docs/features/mcp-server/" target="_blank" rel="noopener">
        Docs
      </a>
      <span class="mcp-section__audit-hint">
        Audit log: <code>{{ mcp.info.value.audit_log_path || '—' }}</code>
      </span>
    </div>

    <!-- Snippet generator -->
    <div class="mcp-section__snippets">
      <h3 class="mcp-section__sub">Client config snippets</h3>
      <div class="mcp-tabs">
        <button
          v-for="t in tabs"
          :key="t.id"
          class="mcp-tab"
          :class="{ 'mcp-tab--active': activeId === t.id }"
          @click="activeId = t.id"
        >
          {{ t.label }}
        </button>
      </div>
      <p class="mcp-section__snippet-hint">{{ activeTab.hint }}</p>
      <div class="mcp-snippet">
        <pre class="mcp-snippet__code"><code>{{ activeText }}</code></pre>
        <button class="mcp-snippet__copy" @click="copy">
          {{ copied ? 'Copied ✓' : 'Copy' }}
        </button>
      </div>
      <p class="mcp-section__paste-path">
        <strong>Paste into:</strong> <code>{{ activeTab.path }}</code>
      </p>
    </div>
  </SettingsSection>
</template>

<script setup lang="ts">
import { nextTick, onMounted } from 'vue'
import SettingsSection from '~/components/settings/SettingsSection.vue'
import { useMcpSnippets, formatLastCall } from '~/composables/settings/useMcpSnippets'

const { mcp, activeId, copied, activeTab, activeText, copy, tabs } = useMcpSnippets()

onMounted(async () => {
  await mcp.refreshInfo()
  if (typeof window !== 'undefined' && window.location.hash === '#mcp') {
    await nextTick()
    document.getElementById('mcp')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
})
</script>
