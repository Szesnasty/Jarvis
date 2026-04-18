<template>
  <div class="settings-page">
    <h1 class="settings-page__title">Settings</h1>

    <!-- AI Providers -->
    <section class="settings-page__section providers-section">
      <div class="providers-header">
        <h2 class="settings-page__section-title">AI Providers</h2>
        <div class="providers-badge">
          <span class="providers-badge__icon" v-html="lockIcon"></span>
          <span class="providers-badge__label">Keys handled locally</span>
        </div>
      </div>

      <KeyProtectionInfo />

      <!-- Server-stored Anthropic key (legacy) -->
      <div v-if="settingsLoaded && serverKeyConfigured" class="server-key-notice">
        <svg class="server-key-notice__icon" viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="10" r="9" stroke="currentColor" stroke-width="1.5" />
          <path d="M6 10.5l2.5 2.5 5.5-5.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <div class="server-key-notice__text">
          <span class="server-key-notice__primary">Anthropic key stored on server</span>
          <span class="server-key-notice__secondary">
            <template v-if="keyStorage === 'keyring'">via system credential store</template>
            <template v-else-if="keyStorage === 'environment'">via environment variable</template>
            <template v-else-if="keyStorage === 'file'">via local file</template>
          </span>
        </div>
      </div>

      <div class="providers-list">
        <ProviderCard
          v-for="p in apiKeys.providers"
          :key="p.id"
          :provider="p"
          :configured="apiKeys.isConfigured(p.id)"
          :masked-key="apiKeys.getMaskedKey(p.id)"
          :remembered="apiKeys.isRemembered(p.id)"
          @add-key="openAddKey(p)"
          @remove-key="apiKeys.removeKey(p.id)"
        />
      </div>
    </section>

    <AddKeyModal
      :provider="addKeyProvider"
      :show="showAddKeyModal"
      @close="showAddKeyModal = false"
      @saved="onKeySaved"
    />

    <!-- Local Models (Ollama) -->
    <section class="settings-page__section local-models-section">
      <h2 class="settings-page__section-title">Local Models</h2>
      <p class="settings-page__hint">
        Run Jarvis locally — private on-device AI. Models are downloaded to your computer.
        <strong>No API key needed.</strong>
      </p>

      <!-- Runtime status card -->
      <div class="local-models__runtime-card" :class="localModels.isOllamaReady() ? 'local-models__runtime-card--ok' : 'local-models__runtime-card--missing'">
        <span class="local-models__runtime-icon">{{ localModels.isOllamaReady() ? '✅' : '⚠️' }}</span>
        <div class="local-models__runtime-info">
          <span class="local-models__runtime-title">
            {{ localModels.isOllamaReady()
              ? `Ollama running${localModels.runtime.value?.version ? ' · v' + localModels.runtime.value.version : ''}`
              : 'Local runtime not detected' }}
          </span>
          <span v-if="!localModels.isOllamaReady()" class="local-models__runtime-hint">
            Install Ollama to use local models.
            <a :href="ollamaDownloadUrl" target="_blank" rel="noopener" class="settings-page__link">Download Ollama →</a>
          </span>
        </div>
        <button v-if="!localModels.isOllamaReady()" class="settings-page__btn settings-page__btn--sm" @click="localModels.refreshAll()">
          Check Again
        </button>
      </div>

      <!-- Hardware summary card -->
      <div v-if="setupFlow.hardwareSummary.value" class="local-models__hw-card">
        <span class="local-models__hw-icon">🖥️</span>
        <div class="local-models__hw-info">
          <span class="local-models__hw-label">{{ setupFlow.hardwareSummary.value.label }}</span>
          <span class="local-models__hw-rec">{{ setupFlow.hardwareSummary.value.recommendation }}</span>
        </div>
      </div>

      <!-- Installed models -->
      <div v-if="installedLocalModels.length > 0" class="local-models__group">
        <h3 class="local-models__group-title">Installed models</h3>
        <div class="local-models__installed-list">
          <div
            v-for="m in installedLocalModels"
            :key="m.model_id"
            class="local-models__installed-row"
            :class="{ 'local-models__installed-row--active': m.active }"
          >
            <div class="local-models__installed-info">
              <span class="local-models__installed-name">{{ m.label }}</span>
              <span class="local-models__quality" :title="qualityDots(m.preset).label">
                <span
                  v-for="i in qualityDots(m.preset).filled"
                  :key="'f'+i"
                  class="local-models__dot local-models__dot--filled"
                  :style="{ '--dot-index': i }"
                />
                <span
                  v-for="i in qualityDots(m.preset).empty"
                  :key="'e'+i"
                  class="local-models__dot local-models__dot--empty"
                />
              </span>
              <span v-if="m.active" class="local-models__installed-badge">Active</span>
              <span class="local-models__installed-meta">{{ m.download_size_gb }} GB · Context {{ m.context_window }}</span>
            </div>
            <div class="local-models__installed-actions">
              <button
                v-if="!m.active"
                class="settings-page__btn settings-page__btn--sm"
                @click="localModels.selectModel(m.model_id)"
              >Set active</button>
              <button
                class="settings-page__btn settings-page__btn--sm"
                @click="localModels.warmUpModel(m.ollama_model)"
              >Warm up</button>
              <button
                class="settings-page__btn settings-page__btn--sm settings-page__btn--danger"
                @click="handleDeleteModel(m)"
              >Remove</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Recommended models — max 3 -->
      <div v-if="localModels.recommendedModels.value.length > 0" class="local-models__group">
        <h3 class="local-models__group-title">Recommended for your hardware</h3>
        <div class="local-models__grid">
          <LocalModelCard
            v-for="m in localModels.recommendedModels.value.slice(0, 3)"
            :key="m.model_id"
            :model="m"
            :pulling="localModels.pulling.value === m.model_id"
            :progress="localModels.pulling.value === m.model_id ? localModels.pullProgress.value : null"
            :disabled="!localModels.isOllamaReady()"
            @pull="localModels.pullModel($event)"
            @select="localModels.selectModel($event)"
            @cancel="localModels.cancelPull()"
          />
        </div>
      </div>

      <!-- More models (collapsed) -->
      <details v-if="nonRecommendedModels.length > 0" class="local-models__all">
        <summary class="local-models__all-toggle">
          Show all local models ({{ nonRecommendedModels.length }})
        </summary>
        <div class="local-models__grid">
          <LocalModelCard
            v-for="m in nonRecommendedModels"
            :key="m.model_id"
            :model="m"
            :pulling="localModels.pulling.value === m.model_id"
            :progress="localModels.pulling.value === m.model_id ? localModels.pullProgress.value : null"
            :disabled="!localModels.isOllamaReady()"
            compact
            @pull="localModels.pullModel($event)"
            @select="localModels.selectModel($event)"
            @cancel="localModels.cancelPull()"
          />
        </div>
      </details>

      <!-- Advanced connection settings (hidden) -->
      <details class="local-models__advanced">
        <summary class="local-models__all-toggle">Advanced connection settings</summary>
        <div class="local-models__url">
          <label class="local-models__url-label">Ollama URL</label>
          <div class="local-models__url-row">
            <input
              type="text"
              class="settings-page__input"
              :value="localModels.baseUrl.value"
              @change="localModels.setBaseUrl(($event.target as HTMLInputElement).value)"
              placeholder="http://localhost:11434"
            />
            <button class="settings-page__btn" @click="localModels.refreshAll()">
              Test Connection
            </button>
          </div>
        </div>
      </details>

      <p v-if="localModels.error.value" class="local-models__error">
        {{ localModels.error.value }}
      </p>
    </section>

    <!-- Workspace -->
    <section class="settings-page__section">
      <h2 class="settings-page__section-title">Workspace</h2>
      <p class="settings-page__path">{{ workspacePath }}</p>
    </section>

    <!-- MCP Server -->
    <section id="mcp" class="settings-page__section mcp-section">
      <div class="mcp-section__header">
        <div>
          <h2 class="settings-page__section-title">MCP Server</h2>
          <p class="mcp-section__lead">
            Expose your <strong>entire workspace</strong> — every note, conversation,
            Jira issue and graph entity — to any MCP-compatible AI client
            (Claude Desktop, Cursor, VS Code Copilot, Continue, Zed). Read-only
            by default, runs locally as a stdio CLI launched on demand by your
            client. Nothing leaves your machine.
          </p>
        </div>
        <span
          class="mcp-section__pill"
          :class="{ 'mcp-section__pill--on': mcp.info.value.cli_on_path }"
        >
          <span class="mcp-section__dot" />
          {{ mcp.info.value.cli_on_path ? 'CLI on PATH' : 'CLI not on PATH' }}
        </span>
      </div>

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

      <div class="mcp-section__actions">
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
            v-for="t in snippetTabs"
            :key="t.id"
            class="mcp-tab"
            :class="{ 'mcp-tab--active': activeSnippet === t.id }"
            @click="activeSnippet = t.id"
          >
            {{ t.label }}
          </button>
        </div>
        <p class="mcp-section__snippet-hint">{{ activeSnippetHint }}</p>
        <div class="mcp-snippet">
          <pre class="mcp-snippet__code"><code>{{ activeSnippetText }}</code></pre>
          <button class="mcp-snippet__copy" @click="copySnippet">
            {{ snippetCopied ? 'Copied ✓' : 'Copy' }}
          </button>
        </div>
        <p class="mcp-section__paste-path">
          <strong>Paste into:</strong> <code>{{ activeSnippetPath }}</code>
        </p>
      </div>
    </section>

    <!-- Voice -->
    <section class="settings-page__section">
      <h2 class="settings-page__section-title">Voice Settings</h2>
      <label class="settings-page__toggle">
        <input type="checkbox" v-model="autoSpeak" @change="updateVoicePrefs" />
        Auto-speak responses
      </label>
    </section>

    <!-- Actions -->
    <section class="settings-page__section">
      <h2 class="settings-page__section-title">Maintenance</h2>
      <div class="settings-page__actions">
        <button class="settings-page__btn" @click="reindexMemory">Reindex Memory</button>
        <button class="settings-page__btn" @click="rebuildGraphAction">Rebuild Graph</button>
      </div>
    </section>

    <!-- Sharpen all (local AI enrichment) -->
    <section class="settings-page__section sharpen-section">
      <h2 class="settings-page__section-title">Sharpen with Local AI</h2>
      <p class="sharpen-section__lead">
        One-click pass through your local LLM to enrich every note and Jira issue
        with summaries, tags and entities — improves retrieval quality and graph density.
        Runs entirely on your machine via Ollama. No API calls to Anthropic.
      </p>
      <div class="sharpen-section__meta">
        <div class="sharpen-section__model-select">
          <label class="sharpen-section__model-label">Model:</label>
          <select
            class="sharpen-section__model-dropdown"
            :value="enrichmentModelId"
            @change="changeEnrichmentModel(($event.target as HTMLSelectElement).value)"
          >
            <option v-for="m in installedLocalModels" :key="m.litellm_model" :value="m.litellm_model">
              {{ m.label }} · {{ qualityDotsText(m.preset) }}
            </option>
          </select>
        </div>
        <span class="sharpen-section__chip" v-if="sharpenQueue">
          Queue: <strong>{{ sharpenQueue.pending }}</strong> pending /
          <strong>{{ sharpenQueue.processing }}</strong> processing
        </span>
        <span class="sharpen-section__chip sharpen-section__chip--warn" v-if="sharpenQueue && sharpenQueue.failed_last_hour > 0">
          Failed (1h): {{ sharpenQueue.failed_last_hour }}
        </span>
      </div>
      <div class="settings-page__actions">
        <button
          class="settings-page__btn settings-page__btn--primary"
          :disabled="sharpenRunning"
          @click="runSharpenAll"
        >
          {{ sharpenRunning ? 'Enqueuing…' : 'Sharpen all notes & issues' }}
        </button>
        <button
          class="settings-page__btn"
          :disabled="sharpenRunning"
          @click="runSharpenNotesOnly"
        >
          Notes only
        </button>
      </div>
      <label class="settings-page__toggle sharpen-section__battery" v-if="onBattery !== null">
        <input type="checkbox" v-model="allowOnBattery" @change="updateBatterySetting" />
        Allow processing on battery
        <span class="sharpen-section__battery-hint" v-if="onBattery">
          &nbsp;⚡ Currently on battery — {{ allowOnBattery ? 'worker will run' : 'worker paused' }}
        </span>
      </label>
      <!-- Progress bar -->
      <div class="sharpen-progress" v-if="sharpenTotal > 0">
        <div class="sharpen-progress__header">
          <span class="sharpen-progress__label">
            <span v-if="sharpenActive && sharpenProgress < 100" class="sharpen-progress__dot" />
            <template v-if="sharpenProgress >= 100">
              Done &mdash; <strong>{{ sharpenTotal }}</strong> items sharpened
            </template>
            <template v-else>
              Processing&hellip; <strong>{{ sharpenDone }}</strong>&thinsp;/&thinsp;{{ sharpenTotal }} items
            </template>
          </span>
          <span class="sharpen-progress__pct">{{ sharpenProgress }}&thinsp;%</span>
          <button
            v-if="sharpenActive && sharpenProgress < 100"
            class="settings-page__btn settings-page__btn--sm settings-page__btn--danger sharpen-progress__cancel"
            :disabled="sharpenCancelling"
            @click="cancelSharpen"
          >
            {{ sharpenCancelling ? 'Cancelling…' : 'Cancel' }}
          </button>
        </div>
        <div class="sharpen-progress__track">
          <div
            class="sharpen-progress__fill"
            :class="{ 'sharpen-progress__fill--done': sharpenProgress >= 100 }"
            :style="{ width: Math.max(sharpenProgress, sharpenTotal > 0 ? 1 : 0) + '%' }"
          />
          <div class="sharpen-progress__shimmer" v-if="sharpenActive && sharpenProgress < 100" />
        </div>
        <div class="sharpen-progress__footer">
          <template v-if="sharpenProgress < 100 && sharpenQueue">
            <span class="sharpen-progress__sub">{{ sharpenQueue.pending }} pending</span>
            <span class="sharpen-progress__sub">{{ sharpenQueue.processing }} processing</span>
          </template>
          <span
            class="sharpen-progress__sub sharpen-progress__sub--warn"
            v-if="sharpenQueue && sharpenQueue.failed_last_hour > 0"
          >{{ sharpenQueue.failed_last_hour }} failed (1h)</span>
          <span class="sharpen-progress__sub sharpen-section__skipped" v-if="sharpenLastResult && sharpenLastResult.skipped > 0">
            {{ sharpenLastResult.skipped }} skipped
          </span>
        </div>
      </div>
    </section>

    <!-- Token Usage & Budget -->
    <section class="settings-page__section budget-section">
      <h2 class="settings-page__section-title">Token Usage & Budget</h2>

      <!-- Today's gauge -->
      <div class="budget-today" v-if="budget">
        <div class="budget-gauge">
          <div class="budget-gauge__track">
            <div
              class="budget-gauge__fill"
              :class="{
                'budget-gauge__fill--warning': budget.level === 'warning',
                'budget-gauge__fill--exceeded': budget.level === 'exceeded',
              }"
              :style="{ width: Math.min(budget.percent, 100) + '%' }"
            />
            <div
              v-if="budget.percent > 100"
              class="budget-gauge__overflow"
              :style="{ width: Math.min(budget.percent - 100, 100) + '%' }"
            />
          </div>
          <div class="budget-gauge__labels">
            <span class="budget-gauge__pct" :class="{
              'budget-gauge__pct--warning': budget.level === 'warning',
              'budget-gauge__pct--exceeded': budget.level === 'exceeded',
            }">
              {{ budget.budget > 0 ? budget.percent + '%' : 'No limit' }}
            </span>
            <span class="budget-gauge__detail">
              {{ formatTokens(budget.used_today) }} / {{ budget.budget > 0 ? formatTokens(budget.budget) : '\u221E' }} tokens today
            </span>
          </div>
        </div>
        <p v-if="budget.level === 'exceeded'" class="budget-exceeded-msg">
          Budget exceeded — chat is blocked until tomorrow or you raise the limit.
        </p>
      </div>

      <!-- Budget control -->
      <div class="budget-control">
        <label class="budget-control__label">Daily token budget</label>
        <div class="budget-control__row">
          <input
            type="range"
            class="budget-control__slider"
            :min="0"
            :max="2000000"
            :step="50000"
            v-model.number="budgetValue"
            @change="saveBudget"
          />
          <div class="budget-control__input-wrap">
            <input
              type="number"
              class="budget-control__input"
              v-model.number="budgetValue"
              @change="saveBudget"
              :min="0"
              :step="50000"
            />
            <span class="budget-control__unit">tokens</span>
          </div>
        </div>
        <div class="budget-control__presets">
          <button
            v-for="p in budgetPresets"
            :key="p.value"
            class="budget-preset"
            :class="{ 'budget-preset--active': budgetValue === p.value }"
            @click="budgetValue = p.value; saveBudget()"
          >{{ p.label }}</button>
        </div>
        <p class="budget-control__hint">
          Set to <strong>0</strong> for unlimited. Est. cost at limit:
          <span class="settings-page__mono">{{ budgetValue > 0 ? '$' + estimateCost(budgetValue) : 'N/A' }}</span>/day
        </p>
      </div>

      <!-- All-time stats -->
      <div class="budget-stats" v-if="usage">
        <div class="budget-stat">
          <span class="budget-stat__value">{{ formatTokens(usage.total) }}</span>
          <span class="budget-stat__label">All-time tokens</span>
        </div>
        <div class="budget-stat">
          <span class="budget-stat__value">{{ usage.request_count }}</span>
          <span class="budget-stat__label">Requests</span>
        </div>
        <div class="budget-stat">
          <span class="budget-stat__value">${{ (usage.cost_estimate ?? 0).toFixed(2) }}</span>
          <span class="budget-stat__label">Est. total cost</span>
        </div>
      </div>

      <!-- Daily history sparkline -->
      <div class="budget-history" v-if="history.length > 0">
        <span class="budget-history__title">Last 14 days</span>
        <div class="budget-history__chart">
          <div
            v-for="(day, i) in history"
            :key="day.date"
            class="budget-history__bar-wrap"
            :title="day.date + ': ' + formatTokens(day.total_tokens) + ' tokens'"
          >
            <div
              class="budget-history__bar"
              :style="{
                height: historyMax > 0 ? Math.max((day.total_tokens / historyMax) * 100, 2) + '%' : '2%',
                animationDelay: (i * 40) + 'ms',
              }"
              :class="{
                'budget-history__bar--over': budgetValue > 0 && day.total_tokens > budgetValue,
                'budget-history__bar--today': i === 0,
              }"
            />
            <span class="budget-history__day">{{ day.date.slice(8) }}</span>
          </div>
        </div>
        <div v-if="budgetValue > 0 && historyMax > 0" class="budget-history__limit" :style="{ bottom: Math.min((budgetValue / historyMax) * 100, 100) + '%' }">
          <span class="budget-history__limit-label">limit</span>
        </div>
      </div>
    </section>

    <!-- Status -->
    <p v-if="statusMsg" class="settings-page__status">{{ statusMsg }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import type { ProviderConfig } from '~/types'
import { ICON_LOCK } from '~/composables/providerIcons'
import { useMcp } from '~/composables/useMcp'

const lockIcon = ICON_LOCK

const localModels = useLocalModels()
const setupFlow = useLocalSetupFlow()

const ollamaDownloadUrl = computed(() => {
  const urls: Record<string, string> = {
    macos: 'https://ollama.com/download/mac',
    windows: 'https://ollama.com/download/windows',
    linux: 'https://ollama.com/download/linux',
  }
  return urls[setupFlow.detectedOS.value] ?? 'https://ollama.com/download'
})

const installedLocalModels = computed(() =>
  localModels.catalog.value.filter(m => m.installed)
)

const nonRecommendedModels = computed(() => {
  const recIds = new Set(localModels.recommendedModels.value.slice(0, 3).map(m => m.model_id))
  return localModels.catalog.value.filter(m => !m.installed && !recIds.has(m.model_id))
})

async function handleDeleteModel(model: { ollama_model: string }) {
  await localModels.deleteModel(model.ollama_model)
  await localModels.refreshAll()
}

const settingsLoaded = ref(false)
const serverKeyConfigured = ref(false)
const keyStorage = ref('')
const workspacePath = ref('')
const autoSpeak = ref(false)
const usage = ref<{ total: number; request_count: number; cost_estimate: number } | null>(null)
const budget = ref<{ daily_budget: number; used_today: number; percent: number; level: string } | null>(null)
const budgetValue = ref(100000)
const history = ref<{ date: string; total_tokens: number }[]>([])
const statusMsg = ref('')

// Provider keys
const apiKeys = useApiKeys()
const showAddKeyModal = ref(false)
const addKeyProvider = ref<ProviderConfig>(apiKeys.providers[0]!)

function openAddKey(provider: ProviderConfig) {
  addKeyProvider.value = provider
  showAddKeyModal.value = true
}

function onKeySaved(_providerId: string) {
  statusMsg.value = 'API key saved'
}

const budgetPresets = [
  { label: '50K', value: 50000 },
  { label: '100K', value: 100000 },
  { label: '250K', value: 250000 },
  { label: '500K', value: 500000 },
  { label: '1M', value: 1000000 },
  { label: 'Unlimited', value: 0 },
]

const historyMax = computed(() => {
  const maxTokens = Math.max(...history.value.map(d => d.total_tokens), 0)
  return budgetValue.value > 0 ? Math.max(maxTokens, budgetValue.value) : maxTokens
})

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K'
  return String(n)
}

function estimateCost(tokens: number): string {
  // rough average: ~$9/MTok blended (input + output)
  return ((tokens / 1_000_000) * 9).toFixed(2)
}

async function saveBudget() {
  try {
    await $fetch('/api/settings/budget', { method: 'PATCH', body: { daily_token_budget: budgetValue.value } })
    // Refresh budget status
    const b = await $fetch<{ daily_budget: number; used_today: number; percent: number; level: string }>('/api/settings/budget')
    budget.value = b
  } catch {
    statusMsg.value = 'Failed to update budget'
  }
}

onMounted(async () => {
  try {
    const resp = await $fetch<{
      workspace_path: string
      api_key_set: boolean
      key_storage: string
      voice: { auto_speak: string; tts_voice: string }
    }>('/api/settings')
    workspacePath.value = resp.workspace_path
    serverKeyConfigured.value = resp.api_key_set
    keyStorage.value = resp.key_storage
    autoSpeak.value = resp.voice.auto_speak === 'true' || resp.voice.auto_speak === true
    settingsLoaded.value = true
  } catch {
    settingsLoaded.value = true
    statusMsg.value = 'Failed to load settings'
  }

  try {
    usage.value = await $fetch('/api/settings/usage')
  } catch { /* non-critical */ }

  try {
    const b = await $fetch<{ daily_budget: number; used_today: number; percent: number; level: string }>('/api/settings/budget')
    budget.value = b
    budgetValue.value = b.daily_budget
  } catch { /* non-critical */ }

  try {
    const h = await $fetch<{ date: string; total_tokens: number }[]>('/api/settings/usage/history')
    history.value = h.slice(0, 14)
  } catch { /* non-critical */ }

  // Load local models state
  localModels.refreshAll()
})

async function updateVoicePrefs() {
  try {
    await $fetch('/api/settings/voice', { method: 'PATCH', body: { auto_speak: String(autoSpeak.value) } })
  } catch { /* ignore */ }
}

async function reindexMemory() {
  try {
    const resp = await $fetch<{ indexed: number }>('/api/memory/reindex', { method: 'POST' })
    statusMsg.value = `Reindexed ${resp.indexed} notes`
  } catch {
    statusMsg.value = 'Reindex failed'
  }
}

async function rebuildGraphAction() {
  try {
    await $fetch('/api/graph/rebuild', { method: 'POST' })
    statusMsg.value = 'Graph rebuilt'
  } catch {
    statusMsg.value = 'Rebuild failed'
  }
}

// ── Sharpen with Local AI ──
type SharpenQueue = { pending: number; processing: number; failed_last_hour: number; completed_total: number; model_id: string }
type SharpenResult = { queued_notes: number; queued_jira: number; queued: number; skipped: number; model_id: string }

const SHARPEN_KEY = 'jarvis_sharpen_progress'

interface SharpenState {
  total: number
  completedAtStart: number
  active: boolean
  lastResult: SharpenResult | null
}

function toFiniteNumber(value: unknown, fallback = 0): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return fallback
}

function loadSharpenState(): SharpenState {
  try {
    const raw = localStorage.getItem(SHARPEN_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<SharpenState> & { startActive?: number }
      // Backward compatibility: old state used startActive; fall back to 0 baseline.
      const completedAtStart =
        toFiniteNumber(parsed.completedAtStart, Number.NaN)
      const migratedCompletedAtStart = Number.isFinite(completedAtStart)
        ? completedAtStart
        : toFiniteNumber(parsed.startActive, 0)

      return {
        total: Math.max(0, toFiniteNumber(parsed.total, 0)),
        completedAtStart: Math.max(0, migratedCompletedAtStart),
        active: Boolean(parsed.active),
        lastResult: parsed.lastResult ?? null,
      }
    }
  } catch { /* ignore */ }
  return { total: 0, completedAtStart: 0, active: false, lastResult: null }
}

function saveSharpenState() {
  try {
    localStorage.setItem(SHARPEN_KEY, JSON.stringify({
      total: sharpenTotal.value,
      completedAtStart: sharpenCompletedAtStart.value,
      active: sharpenActive.value,
      lastResult: sharpenLastResult.value,
    }))
  } catch { /* ignore */ }
}

function clearSharpenState() {
  try { localStorage.removeItem(SHARPEN_KEY) } catch { /* ignore */ }
}

const sharpenQueue = ref<SharpenQueue | null>(null)
const sharpenRunning = ref(false)
const sharpenLastResult = ref<SharpenResult | null>(null)
const sharpenTotal = ref(0)              // items enqueued by our last sharpen call
const sharpenCompletedAtStart = ref(0)   // completed_total snapshot right after enqueue
const sharpenActive = ref(false)         // true while worker is consuming our batch
let sharpenPollTimer: ReturnType<typeof setInterval> | null = null

const sharpenDone = computed((): number => {
  if (!sharpenTotal.value) return 0
  const pending = toFiniteNumber(sharpenQueue.value?.pending, 0)
  const processing = toFiniteNumber(sharpenQueue.value?.processing, 0)
  return Math.min(sharpenTotal.value, Math.max(0, sharpenTotal.value - pending - processing))
})

const sharpenProgress = computed((): number => {
  const total = toFiniteNumber(sharpenTotal.value, 0)
  if (total <= 0) return 0
  return Math.min(100, Math.round((sharpenDone.value / total) * 100))
})

async function refreshSharpenQueue() {
  try {
    sharpenQueue.value = await $fetch<SharpenQueue>('/api/enrichment/queue')
  } catch { /* non-critical */ }
}

function startSharpenPolling() {
  if (sharpenPollTimer) return
  sharpenPollTimer = setInterval(async () => {
    await refreshSharpenQueue()
    saveSharpenState()
    if (sharpenQueue.value && sharpenQueue.value.pending === 0 && sharpenQueue.value.processing === 0) {
      sharpenActive.value = false
      saveSharpenState()
      stopSharpenPolling()
    }
  }, 3000)
}

function stopSharpenPolling() {
  if (sharpenPollTimer) {
    clearInterval(sharpenPollTimer)
    sharpenPollTimer = null
  }
}

async function runSharpen(includeJira: boolean) {
  if (sharpenRunning.value) return
  sharpenRunning.value = true
  // reset progress for new run
  sharpenTotal.value = 0
  sharpenCompletedAtStart.value = 0
  sharpenActive.value = false
  clearSharpenState()
  stopSharpenPolling()
  try {
    const result = await $fetch<SharpenResult>('/api/enrichment/sharpen-all', {
      method: 'POST',
      body: { reason: 'manual_sharpen_all', include_notes: true, include_jira: includeJira },
    })
    sharpenLastResult.value = result
    sharpenTotal.value = result.queued
    statusMsg.value = `Enqueued ${result.queued} items for local AI sharpening`
    await refreshSharpenQueue()
    sharpenCompletedAtStart.value = sharpenQueue.value?.completed_total ?? 0
    if (result.queued > 0) {
      sharpenActive.value = true
      saveSharpenState()
      startSharpenPolling()
    }
  } catch {
    statusMsg.value = 'Sharpen request failed'
  } finally {
    sharpenRunning.value = false
  }
}

const runSharpenAll = () => runSharpen(true)
const runSharpenNotesOnly = () => runSharpen(false)

const sharpenCancelling = ref(false)

async function cancelSharpen() {
  if (sharpenCancelling.value) return
  sharpenCancelling.value = true
  try {
    const resp = await $fetch<{ removed: number }>('/api/enrichment/queue', { method: 'DELETE' })
    statusMsg.value = `Cancelled — removed ${resp.removed} pending items`
    await refreshSharpenQueue()
    sharpenActive.value = false
    saveSharpenState()
    stopSharpenPolling()
  } catch {
    statusMsg.value = 'Cancel failed'
  } finally {
    sharpenCancelling.value = false
  }
}

// Battery toggle
const allowOnBattery = ref(false)
const onBattery = ref<boolean | null>(null) // null = not yet loaded
const enrichmentModelId = ref('')

// Quality dots (shared with ModelSelector)
type LocalModelPreset = 'fast' | 'everyday' | 'balanced' | 'long-docs' | 'reasoning' | 'code' | 'best-local'

const PRESET_QUALITY: Record<LocalModelPreset, number> = {
  'fast': 1, 'everyday': 2, 'balanced': 3, 'long-docs': 3,
  'reasoning': 4, 'code': 4, 'best-local': 5,
}
const PRESET_LABEL: Record<LocalModelPreset, string> = {
  'fast': 'Fast · light', 'everyday': 'Good · everyday', 'balanced': 'Solid · balanced',
  'long-docs': 'Solid · long docs', 'reasoning': 'Strong · reasoning',
  'code': 'Strong · coding', 'best-local': 'Best local',
}

function qualityDots(preset: string): { filled: number; empty: number; label: string } {
  const q = PRESET_QUALITY[preset as LocalModelPreset] ?? 3
  const label = PRESET_LABEL[preset as LocalModelPreset] ?? preset
  return { filled: q, empty: 5 - q, label }
}

function qualityDotsText(preset: string): string {
  const q = PRESET_QUALITY[preset as LocalModelPreset] ?? 3
  return '●'.repeat(q) + '○'.repeat(5 - q)
}

async function loadEnrichmentSettings() {
  try {
    const resp = await $fetch<{ allow_on_battery: boolean; on_battery: boolean; model_id: string }>('/api/settings/enrichment')
    allowOnBattery.value = resp.allow_on_battery
    onBattery.value = resp.on_battery
    enrichmentModelId.value = resp.model_id
  } catch {
    onBattery.value = null
  }
}

async function changeEnrichmentModel(litellmModel: string) {
  enrichmentModelId.value = litellmModel
  try {
    await $fetch('/api/settings/enrichment', {
      method: 'PATCH',
      body: { model_id: litellmModel },
    })
    await refreshSharpenQueue()
    statusMsg.value = `Enrichment model set to ${litellmModel.replace('ollama_chat/', '')}`
  } catch {
    statusMsg.value = 'Failed to update enrichment model'
  }
}

async function updateBatterySetting() {
  try {
    await $fetch('/api/settings/enrichment', {
      method: 'PATCH',
      body: { allow_on_battery: allowOnBattery.value },
    })
  } catch { /* ignore */ }
}

// Restore progress state on mount (survives navigation / page refresh)
onMounted(async () => {
  const saved = loadSharpenState()
  if (saved.total > 0) {
    sharpenTotal.value = saved.total
    sharpenCompletedAtStart.value = saved.completedAtStart
    sharpenActive.value = saved.active
    sharpenLastResult.value = saved.lastResult
  }
  await refreshSharpenQueue()
  loadEnrichmentSettings()
  // If queue still has items and we had an active run, resume polling
  if (sharpenTotal.value > 0 && sharpenQueue.value &&
      (sharpenQueue.value.pending > 0 || sharpenQueue.value.processing > 0)) {
    sharpenActive.value = true
    startSharpenPolling()
  } else if (sharpenTotal.value > 0) {
    // Queue is empty — run is done
    sharpenActive.value = false
    saveSharpenState()
  }
})
onBeforeUnmount(() => { stopSharpenPolling() })

// ─────────────────────────────────────────────────────────────────────────
// MCP Server panel
// ─────────────────────────────────────────────────────────────────────────
const mcp = useMcp()
const snippetCopied = ref(false)

type SnippetId = 'claude' | 'cursor' | 'vscode' | 'continue' | 'zed'

interface SnippetTab {
  id: SnippetId
  label: string
  hint: string
  path: string
  builder: 'stdio' | 'vscode'
}

const snippetTabs: SnippetTab[] = [
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

const activeSnippet = ref<SnippetId>('cursor')

const activeSnippetTab = computed(() =>
  snippetTabs.find((t) => t.id === activeSnippet.value) ?? snippetTabs[0]!,
)
const activeSnippetHint = computed(() => activeSnippetTab.value.hint)
const activeSnippetPath = computed(() => activeSnippetTab.value.path)

const activeSnippetText = computed(() => {
  const ctx = mcp.snippetCtx.value
  switch (activeSnippetTab.value.builder) {
    case 'vscode': return mcp.buildVscodeConfig(ctx)
    case 'stdio':
    default: return mcp.buildStdioConfig(ctx)
  }
})

function formatLastCall(iso: string | null): string {
  if (!iso) return 'never'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const diffSec = Math.floor((Date.now() - d.getTime()) / 1000)
  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
  return d.toLocaleString()
}

async function copySnippet() {
  try {
    await navigator.clipboard.writeText(activeSnippetText.value)
    snippetCopied.value = true
    setTimeout(() => { snippetCopied.value = false }, 1500)
  } catch { /* ignore */ }
}

onMounted(async () => {
  await mcp.refreshInfo()
  if (typeof window !== 'undefined' && window.location.hash === '#mcp') {
    await nextTick()
    document.getElementById('mcp')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
})
</script>

<style scoped>
.settings-page {
  max-width: 860px;
  margin: 0 auto;
  padding: 2rem;
  height: calc(100vh - 40px);
  overflow-y: auto;
  width: 640px;
}
.settings-page__title {
  font-size: 1.5rem;
  margin-bottom: 1.5rem;
}
.settings-page__section {
  margin-bottom: 1.5rem;
  padding: 1rem;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
}
.settings-page__section-title {
  font-size: 1rem;
  margin-bottom: 0.75rem;
}
.settings-page__field {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.settings-page__hint {
  font-size: 0.82rem;
  line-height: 1.55;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}
.settings-page__hint strong {
  color: var(--neon-cyan);
  font-weight: 600;
}
.settings-page__mono {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.9em;
  background: rgba(2, 254, 255, 0.06);
  padding: 0.05em 0.35em;
  border-radius: 3px;
  border: 1px solid var(--border-subtle);
}
.settings-page__micro {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.6rem;
}
.settings-page__link {
  color: var(--neon-cyan-60);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.settings-page__link:hover {
  color: var(--neon-cyan);
}
.settings-page__warning {
  font-size: 0.8rem;
  color: rgba(251, 146, 60, 0.9);
  background: rgba(251, 146, 60, 0.06);
  border: 1px solid rgba(251, 146, 60, 0.2);
  border-radius: 6px;
  padding: 0.45rem 0.7rem;
  margin-bottom: 0.5rem;
}
.settings-page__hint-subtle {
  font-size: 0.8rem;
  color: var(--neon-cyan-60);
  margin-bottom: 0.5rem;
}
.settings-page__input {
  padding: 0.4rem 0.75rem;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  background: var(--bg-base);
  color: inherit;
  flex: 1;
  min-width: 200px;
}
.settings-page__input:focus {
  outline: none;
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}
.settings-page__btn {
  padding: 0.4rem 1rem;
  border: 1px solid var(--neon-cyan-30);
  border-radius: 4px;
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
  cursor: pointer;
  transition: all 0.2s;
}
.settings-page__btn:hover {
  background: rgba(2, 254, 255, 0.15);
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 12px var(--neon-cyan-08);
  text-shadow: 0 0 6px var(--neon-cyan-30);
}
/* ---- Providers Section ---- */
.providers-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}
.providers-header .settings-page__section-title {
  margin-bottom: 0;
}
.providers-badge {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.6rem;
  border-radius: 20px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.03em;
  color: #34d399;
  background: rgba(52, 211, 153, 0.08);
  border: 1px solid rgba(52, 211, 153, 0.25);
}
.providers-badge__icon {
  display: flex;
  align-items: center;
}
.providers-badge__icon :deep(svg) {
  width: 12px;
  height: 12px;
}
.providers-list {
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  overflow: hidden;
}
.server-key-notice {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  margin-bottom: 0.75rem;
  color: #34d399;
  background: rgba(52, 211, 153, 0.04);
  border: 1px solid rgba(52, 211, 153, 0.12);
}
.server-key-notice__icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}
.server-key-notice__text {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}
.server-key-notice__primary {
  font-size: 0.82rem;
  font-weight: 600;
}
.server-key-notice__secondary {
  font-size: 0.72rem;
  opacity: 0.7;
}

.settings-page__path {
  font-family: monospace;
  font-size: 0.85rem;
  opacity: 0.7;
}
.settings-page__toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}
.settings-page__actions {
  display: flex;
  gap: 0.75rem;
}
/* ---- Budget Section ---- */
.budget-section {
  overflow: hidden;
}

/* Gauge */
.budget-gauge {
  margin-bottom: 1rem;
}
.budget-gauge__track {
  position: relative;
  height: 10px;
  border-radius: 5px;
  background: var(--bg-base);
  overflow: hidden;
  border: 1px solid var(--border-subtle);
}
.budget-gauge__fill {
  height: 100%;
  border-radius: 5px;
  background: var(--neon-cyan);
  box-shadow: 0 0 10px var(--neon-cyan-30);
  transition: width 0.6s cubic-bezier(0.22, 1, 0.36, 1);
}
.budget-gauge__fill--warning {
  background: rgba(251, 191, 36, 1);
  box-shadow: 0 0 10px rgba(251, 191, 36, 0.3);
}
.budget-gauge__fill--exceeded {
  background: rgba(248, 113, 113, 1);
  box-shadow: 0 0 10px rgba(248, 113, 113, 0.3);
}
.budget-gauge__overflow {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  background: repeating-linear-gradient(
    -45deg,
    rgba(248, 113, 113, 0.6),
    rgba(248, 113, 113, 0.6) 4px,
    rgba(248, 113, 113, 0.3) 4px,
    rgba(248, 113, 113, 0.3) 8px
  );
  border-radius: 5px;
  animation: overflow-scroll 0.8s linear infinite;
}
@keyframes overflow-scroll {
  from { background-position: 0 0; }
  to { background-position: 11.3px 0; }
}
.budget-gauge__labels {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-top: 0.4rem;
}
.budget-gauge__pct {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--neon-cyan);
  text-shadow: 0 0 12px var(--neon-cyan-30);
}
.budget-gauge__pct--warning {
  color: rgba(251, 191, 36, 1);
  text-shadow: 0 0 12px rgba(251, 191, 36, 0.3);
}
.budget-gauge__pct--exceeded {
  color: rgba(248, 113, 113, 1);
  text-shadow: 0 0 12px rgba(248, 113, 113, 0.3);
}
.budget-gauge__detail {
  font-size: 0.78rem;
  color: var(--text-secondary);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
.budget-exceeded-msg {
  font-size: 0.8rem;
  color: rgba(248, 113, 113, 0.9);
  background: rgba(248, 113, 113, 0.06);
  border: 1px solid rgba(248, 113, 113, 0.2);
  border-radius: 6px;
  padding: 0.45rem 0.7rem;
  margin-top: 0.5rem;
}

/* Budget control */
.budget-control {
  margin: 1.25rem 0;
  padding-top: 1rem;
  border-top: 1px solid var(--border-subtle);
}
.budget-control__label {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
  display: block;
}
.budget-control__row {
  display: flex;
  align-items: center;
  gap: 1rem;
}
.budget-control__slider {
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 4px;
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  border-radius: 2px;
  outline: none;
  cursor: pointer;
}
.budget-control__slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--neon-cyan);
  box-shadow: 0 0 8px var(--neon-cyan-30), 0 0 2px var(--neon-cyan);
  cursor: pointer;
  transition: box-shadow 0.2s;
}
.budget-control__slider::-webkit-slider-thumb:hover {
  box-shadow: 0 0 14px var(--neon-cyan-60), 0 0 4px var(--neon-cyan);
}
.budget-control__slider::-moz-range-thumb {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--neon-cyan);
  box-shadow: 0 0 8px var(--neon-cyan-30);
  border: none;
  cursor: pointer;
}
.budget-control__input-wrap {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.budget-control__input {
  width: 100px;
  padding: 0.35rem 0.5rem;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  background: var(--bg-base);
  color: inherit;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.82rem;
  text-align: right;
}
.budget-control__input:focus {
  outline: none;
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}
/* Hide number input spinners */
.budget-control__input::-webkit-outer-spin-button,
.budget-control__input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.budget-control__input[type="number"] {
  -moz-appearance: textfield;
}
.budget-control__unit {
  font-size: 0.75rem;
  color: var(--text-muted);
}
.budget-control__presets {
  display: flex;
  gap: 0.4rem;
  margin-top: 0.65rem;
  flex-wrap: wrap;
}
.budget-preset {
  padding: 0.25rem 0.65rem;
  border: 1px solid var(--border-default);
  border-radius: 12px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.72rem;
  cursor: pointer;
  transition: all 0.15s;
}
.budget-preset:hover {
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan-60);
}
.budget-preset--active {
  border-color: var(--neon-cyan-60);
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
  box-shadow: 0 0 8px var(--neon-cyan-08);
}
.budget-control__hint {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.5rem;
}
.budget-control__hint strong {
  color: var(--neon-cyan);
}

/* Stats row */
.budget-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
  margin: 1.25rem 0;
  padding-top: 1rem;
  border-top: 1px solid var(--border-subtle);
}
.budget-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
}
.budget-stat__value {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 1.1rem;
  font-weight: 600;
  color: var(--text-primary);
}
.budget-stat__label {
  font-size: 0.7rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

/* History chart */
.budget-history {
  position: relative;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--border-subtle);
}
.budget-history__title {
  font-size: 0.72rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  display: block;
  margin-bottom: 0.6rem;
}
.budget-history__chart {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 80px;
  position: relative;
}
.budget-history__bar-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  justify-content: flex-end;
}
.budget-history__bar {
  width: 100%;
  min-height: 2px;
  border-radius: 2px 2px 0 0;
  background: var(--neon-cyan-30);
  transition: height 0.3s ease;
  animation: bar-grow 0.5s cubic-bezier(0.22, 1, 0.36, 1) backwards;
}
@keyframes bar-grow {
  from {
    height: 0 !important;
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
.budget-history__bar--today {
  background: var(--neon-cyan);
  box-shadow: 0 0 6px var(--neon-cyan-30);
}
.budget-history__bar--over {
  background: rgba(248, 113, 113, 0.6);
}
.budget-history__day {
  font-size: 0.6rem;
  color: var(--text-muted);
  margin-top: 3px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
.budget-history__limit {
  position: absolute;
  left: 0;
  right: 0;
  border-top: 1px dashed rgba(251, 191, 36, 0.4);
  pointer-events: none;
}
.budget-history__limit-label {
  position: absolute;
  right: 0;
  top: -14px;
  font-size: 0.58rem;
  color: rgba(251, 191, 36, 0.6);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.settings-page__status {
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  background: var(--neon-cyan-08);
  border: 1px solid var(--neon-cyan-30);
  border-radius: 4px;
  font-size: 0.9rem;
  color: var(--neon-cyan);
}

/* ---- Local Models Section ---- */
.local-models__runtime-card {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  margin-bottom: 0.85rem;
}
.local-models__runtime-card--ok {
  background: rgba(52, 211, 153, 0.04);
  border: 1px solid rgba(52, 211, 153, 0.15);
}
.local-models__runtime-card--missing {
  background: rgba(251, 191, 36, 0.04);
  border: 1px solid rgba(251, 191, 36, 0.15);
}
.local-models__runtime-icon {
  font-size: 1.1rem;
  flex-shrink: 0;
}
.local-models__runtime-info {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  flex: 1;
}
.local-models__runtime-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}
.local-models__runtime-hint {
  font-size: 0.75rem;
  color: var(--text-secondary);
}
.local-models__hw-card {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.55rem 0.85rem;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-subtle);
  margin-bottom: 0.85rem;
}
.local-models__hw-icon {
  font-size: 1rem;
  flex-shrink: 0;
}
.local-models__hw-info {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}
.local-models__hw-label {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}
.local-models__hw-rec {
  font-size: 0.72rem;
  color: var(--text-muted);
}
.local-models__installed-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.local-models__installed-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.55rem 0.75rem;
  border-radius: 6px;
  border: 1px solid var(--border-default);
  background: var(--bg-base);
}
.local-models__installed-row--active {
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 8px var(--neon-cyan-08);
}
.local-models__installed-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.local-models__installed-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}
.local-models__installed-badge {
  font-size: 0.62rem;
  font-weight: 600;
  padding: 0.08rem 0.35rem;
  border-radius: 4px;
  background: var(--neon-cyan-08);
  color: var(--neon-cyan-60);
  border: 1px solid var(--neon-cyan-15);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.local-models__installed-meta {
  font-size: 0.72rem;
  color: var(--text-muted);
}
.local-models__installed-actions {
  display: flex;
  gap: 0.35rem;
  flex-shrink: 0;
}
.settings-page__btn--sm {
  padding: 0.25rem 0.6rem;
  font-size: 0.72rem;
}
.settings-page__btn--danger {
  border-color: rgba(248, 113, 113, 0.3);
  color: rgba(248, 113, 113, 0.8);
  background: rgba(248, 113, 113, 0.04);
}
.settings-page__btn--danger:hover {
  border-color: rgba(248, 113, 113, 0.5);
  background: rgba(248, 113, 113, 0.1);
  box-shadow: none;
  text-shadow: none;
  color: rgba(248, 113, 113, 1);
}
.local-models__group {
  margin-top: 1rem;
}
.local-models__group-title {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin-bottom: 0.65rem;
  font-weight: 600;
}
.local-models__grid {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}
.local-models__all {
  margin-top: 1rem;
}
.local-models__advanced {
  margin-top: 0.75rem;
}
.local-models__all-toggle {
  font-size: 0.82rem;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.4rem 0;
  user-select: none;
}
.local-models__all-toggle:hover {
  color: var(--text-primary);
}
.local-models__all[open] .local-models__grid {
  margin-top: 0.65rem;
}
.local-models__url {
  margin-top: 0.65rem;
}
.local-models__url-label {
  font-size: 0.78rem;
  color: var(--text-secondary);
  display: block;
  margin-bottom: 0.35rem;
}
.local-models__url-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.local-models__error {
  margin-top: 0.65rem;
  font-size: 0.8rem;
  color: rgba(248, 113, 113, 0.9);
  background: rgba(248, 113, 113, 0.06);
  border: 1px solid rgba(248, 113, 113, 0.2);
  border-radius: 6px;
  padding: 0.45rem 0.7rem;
}

/* Sharpen with Local AI — progress bar */
.sharpen-progress {
  margin-top: 1.1rem;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 10px;
  padding: 0.85rem 1rem 0.75rem;
}
.sharpen-progress__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
  font-size: 0.83rem;
  gap: 0.5rem;
}
.sharpen-progress__label {
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.sharpen-progress__label strong {
  color: var(--text-primary);
}
.sharpen-progress__dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: rgba(96, 165, 250, 0.9);
  animation: sharpen-pulse 1.4s ease-in-out infinite;
  flex-shrink: 0;
}
@keyframes sharpen-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.75); }
}
.sharpen-progress__pct {
  font-variant-numeric: tabular-nums;
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}
.sharpen-progress__track {
  position: relative;
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 999px;
  overflow: hidden;
}
.sharpen-progress__fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(96, 165, 250, 0.65), rgba(147, 197, 253, 0.9));
  transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
  min-width: 4px;
}
.sharpen-progress__fill--done {
  background: linear-gradient(90deg, rgba(52, 211, 153, 0.7), rgba(110, 231, 183, 0.95));
}
.sharpen-progress__shimmer {
  position: absolute;
  top: 0;
  bottom: 0;
  left: -80px;
  width: 80px;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  animation: sharpen-shimmer 2.2s ease-in-out infinite;
}
@keyframes sharpen-shimmer {
  from { left: -80px; }
  to { left: 100%; }
}
.sharpen-progress__footer {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.45rem;
}
.sharpen-progress__sub {
  font-size: 0.74rem;
  color: rgba(255, 255, 255, 0.28);
}
.sharpen-progress__sub--warn {
  color: rgba(248, 113, 113, 0.7);
}
.sharpen-section__skipped {
  color: rgba(255, 255, 255, 0.22);
}

.settings-page__btn--primary {
  border-color: rgba(96, 165, 250, 0.45);
  color: rgba(147, 197, 253, 0.95);
  background: rgba(59, 130, 246, 0.08);
}
.settings-page__btn--primary:hover:not(:disabled) {
  border-color: rgba(96, 165, 250, 0.7);
  background: rgba(59, 130, 246, 0.16);
  color: #fff;
}
.settings-page__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.sharpen-section__lead {
  color: var(--text-secondary);
  font-size: 0.85rem;
  line-height: 1.5;
  margin: 0.4rem 0 0.85rem;
}
.sharpen-section__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.sharpen-section__chip {
  font-size: 0.75rem;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  padding: 0.2rem 0.65rem;
}
.sharpen-section__chip strong {
  color: var(--text-primary);
  font-weight: 600;
}
.sharpen-section__chip--warn {
  border-color: rgba(248, 113, 113, 0.3);
  color: rgba(248, 113, 113, 0.9);
  background: rgba(248, 113, 113, 0.06);
}
.sharpen-section__result {
  margin-top: 0.7rem;
  font-size: 0.82rem;
  color: var(--text-secondary);
}
.sharpen-section__battery {
  margin-top: 0.6rem;
  font-size: 0.84rem;
}
.sharpen-section__battery-hint {
  font-size: 0.78rem;
  color: rgba(250, 204, 21, 0.7);
}

/* Quality dots (installed models) */
.local-models__quality {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-left: 0.35rem;
}
.local-models__dot {
  display: inline-block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
}
.local-models__dot--filled {
  background: color-mix(in srgb, var(--neon-cyan) calc(40% + var(--dot-index, 1) * 12%), #888);
  box-shadow: 0 0 3px color-mix(in srgb, var(--neon-cyan) calc(var(--dot-index, 1) * 12%), transparent);
}
.local-models__dot--empty {
  background: var(--border-default);
  opacity: 0.35;
}

/* Enrichment model selector */
.sharpen-section__model-select {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.65rem;
}
.sharpen-section__model-label {
  font-size: 0.8rem;
  color: var(--text-secondary);
}
.sharpen-section__model-dropdown {
  font-size: 0.78rem;
  padding: 0.25rem 0.5rem;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  background: var(--bg-base);
  color: var(--text-primary);
  cursor: pointer;
  min-width: 180px;
}
.sharpen-section__model-dropdown:focus {
  outline: none;
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 8px var(--neon-cyan-08);
}
.sharpen-progress__cancel {
  margin-left: auto;
  flex-shrink: 0;
}

/* ──────────────────────────────────────────────────────────────────────
   MCP Server panel
   ────────────────────────────────────────────────────────────────────── */
.mcp-section {
  scroll-margin-top: 80px;
}

.mcp-section__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}

.mcp-section__lead {
  margin: 0.25rem 0 0;
  color: var(--text-secondary);
  font-size: 0.88rem;
  line-height: 1.5;
  max-width: 70ch;
}

.mcp-section__lead strong {
  color: var(--neon-cyan);
}

.mcp-section__pill {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.3rem 0.75rem;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);
  background-color: rgba(148, 163, 184, 0.08);
  border: 1px solid var(--border-subtle);
  border-radius: 9999px;
}

.mcp-section__pill--on {
  color: var(--neon-cyan);
  background-color: var(--neon-cyan-08);
  border-color: var(--neon-cyan-30);
  text-shadow: 0 0 6px var(--neon-cyan-30);
}

.mcp-section__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: var(--text-muted, #64748b);
}

.mcp-section__pill--on .mcp-section__dot {
  background-color: #22d3ee;
  box-shadow: 0 0 8px rgba(34, 211, 238, 0.7);
  animation: mcpPulse 2.4s ease-in-out infinite;
}

@keyframes mcpPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

.mcp-section__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.mcp-stat {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.65rem 0.85rem;
  background-color: var(--bg-elevated, rgba(148, 163, 184, 0.04));
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
}

.mcp-stat__label {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-muted, #94a3b8);
}

.mcp-stat__value {
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

.mcp-stat__value--small {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.mcp-section__actions {
  align-items: center;
  flex-wrap: wrap;
}

.mcp-section__port {
  width: 90px;
  padding: 0.4rem 0.6rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.85rem;
  background-color: var(--bg-elevated, rgba(148, 163, 184, 0.04));
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-primary);
}

.mcp-section__port:disabled {
  opacity: 0.55;
}

.mcp-section__error {
  margin-top: 0.6rem;
  padding: 0.5rem 0.75rem;
  font-size: 0.82rem;
  color: var(--neon-red, #f87171);
  background-color: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 6px;
}

.mcp-section__sub {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
  font-weight: 600;
}

.mcp-section__token {
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px dashed var(--border-subtle);
}

.mcp-section__token-header {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.mcp-section__token-hint {
  font-size: 0.75rem;
  color: var(--text-muted, #94a3b8);
}

.mcp-section__token-hint code {
  padding: 0.05rem 0.3rem;
  background-color: rgba(148, 163, 184, 0.1);
  border-radius: 3px;
  font-size: 0.72rem;
}

.mcp-section__token-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
}

.mcp-section__token-input {
  flex: 1 1 320px;
  min-width: 0;
  padding: 0.45rem 0.7rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8rem;
  background-color: var(--bg-elevated, rgba(148, 163, 184, 0.04));
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-primary);
}

.mcp-section__snippets {
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px dashed var(--border-subtle);
}

.mcp-tabs {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
  margin-bottom: 0.75rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--border-subtle);
}

.mcp-tab {
  padding: 0.4rem 0.85rem;
  font-size: 0.8rem;
  background: none;
  border: 1px solid transparent;
  border-radius: 6px 6px 0 0;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.mcp-tab:hover {
  color: var(--text-primary);
  background-color: var(--neon-cyan-08);
}

.mcp-tab--active {
  color: var(--neon-cyan);
  background-color: var(--neon-cyan-08);
  border-color: var(--neon-cyan-30);
  text-shadow: 0 0 6px var(--neon-cyan-30);
}

.mcp-section__snippet-hint {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
  color: var(--text-muted, #94a3b8);
}

.mcp-snippet {
  position: relative;
  background-color: rgba(15, 23, 42, 0.5);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  overflow: hidden;
}

.mcp-snippet__code {
  margin: 0;
  padding: 0.85rem 1rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.78rem;
  line-height: 1.5;
  color: #e2e8f0;
  overflow-x: auto;
  white-space: pre;
}

.mcp-snippet__copy {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  padding: 0.3rem 0.7rem;
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  background-color: rgba(34, 211, 238, 0.1);
  color: var(--neon-cyan);
  border: 1px solid var(--neon-cyan-30);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.mcp-snippet__copy:hover {
  background-color: rgba(34, 211, 238, 0.2);
}

.mcp-section__paste-path {
  margin: 0.55rem 0 0;
  font-size: 0.78rem;
  color: var(--text-muted, #94a3b8);
}

.mcp-section__paste-path code {
  padding: 0.1rem 0.4rem;
  background-color: rgba(148, 163, 184, 0.1);
  border-radius: 4px;
  font-size: 0.75rem;
  color: var(--text-secondary);
}
</style>
