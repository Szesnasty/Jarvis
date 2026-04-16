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
import { ref, computed, onMounted } from 'vue'
import type { ProviderConfig } from '~/types'
import { ICON_LOCK } from '~/composables/providerIcons'

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
</style>
