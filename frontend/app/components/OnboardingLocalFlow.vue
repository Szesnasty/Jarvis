<script setup lang="ts">
const emit = defineEmits<{
  (e: 'model-ready'): void
  (e: 'back'): void
}>()

const localModels = useLocalModels()
const flow = useLocalSetupFlow()
const showAll = ref(false)
const showManualSetup = ref(false)

const linuxCommand = 'curl -fsSL https://ollama.com/install.sh | sh'
const copiedCommand = ref(false)

onMounted(() => {
  flow.initialize()
})

onUnmounted(() => {
  flow.cleanup()
})

function copyLinuxCommand() {
  navigator.clipboard.writeText(linuxCommand)
  copiedCommand.value = true
  setTimeout(() => { copiedCommand.value = false }, 2000)
}

async function handlePull(modelId: string) {
  const ok = await flow.downloadModel(modelId)
  if (ok) {
    // Don't auto-emit — let user see the success screen
  }
}

async function handleSelect(modelId: string) {
  await flow.selectModel(modelId)
}

function handleFinish() {
  emit('model-ready')
}

function handleDownloadAnother() {
  flow.state.value = 'model_selection'
}

const displayModels = computed(() => {
  if (showAll.value) return localModels.catalog.value
  return localModels.recommendedModels.value.slice(0, 3)
})

const downloadingModel = computed(() => {
  if (!flow.downloadingModelId.value) return null
  return localModels.catalog.value.find(m => m.model_id === flow.downloadingModelId.value)
})

const readyModel = computed(() => localModels.activeModel.value)
</script>

<template>
  <div class="local-flow">
    <h2 class="local-flow__title">Run Jarvis locally</h2>

    <!-- Step indicators -->
    <div class="local-flow__steps">
      <div class="local-flow__step" :class="{
        'local-flow__step--active': flow.wizardStep.value === 1,
        'local-flow__step--done': flow.wizardStep.value > 1
      }">
        <span class="local-flow__step-num">{{ flow.wizardStep.value > 1 ? '✓' : '1' }}</span>
        <span class="local-flow__step-label">Install local runtime</span>
      </div>
      <div class="local-flow__step-line" :class="{ 'local-flow__step-line--done': flow.wizardStep.value > 1 }" />
      <div class="local-flow__step" :class="{
        'local-flow__step--active': flow.wizardStep.value === 2,
        'local-flow__step--done': flow.wizardStep.value > 2
      }">
        <span class="local-flow__step-num">{{ flow.wizardStep.value > 2 ? '✓' : '2' }}</span>
        <span class="local-flow__step-label">Choose a model</span>
      </div>
      <div class="local-flow__step-line" :class="{ 'local-flow__step-line--done': flow.wizardStep.value > 2 }" />
      <div class="local-flow__step" :class="{ 'local-flow__step--active': flow.wizardStep.value === 3 }">
        <span class="local-flow__step-num">3</span>
        <span class="local-flow__step-label">Start using Jarvis</span>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="localModels.loading.value" class="local-flow__loading">
      <div class="local-flow__spinner" />
      Detecting your hardware...
    </div>

    <!-- ==================== STATE: runtime_missing ==================== -->
    <template v-else-if="flow.state.value === 'runtime_missing'">
      <div class="local-flow__install">
        <h3 class="local-flow__section-title">Ollama powers local AI on your computer</h3>
        <p class="local-flow__section-desc">
          <template v-if="flow.detectedOS.value === 'macos'">Install it from the official website, then open the app once. Jarvis will detect it automatically.</template>
          <template v-else-if="flow.detectedOS.value === 'windows'">Install it from the official website. It runs automatically in the background after install.</template>
          <template v-else>Install it using the command below, then run <code>ollama serve</code> to start it.</template>
        </p>

        <!-- Hardware badge -->
        <div v-if="flow.hardwareSummary.value" class="local-flow__hw-badge">
          {{ flow.hardwareSummary.value.label }}
        </div>

        <!-- Platform-specific install -->
        <div class="local-flow__platform">
          <button class="local-flow__install-btn" @click="flow.openOllamaDownload()">
            <template v-if="flow.detectedOS.value === 'macos'">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
            </template>
            <template v-else-if="flow.detectedOS.value === 'windows'">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.9-1.801"/></svg>
            </template>
            Open official Ollama download
            <svg class="local-flow__external-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          </button>
        </div>

        <p class="local-flow__helper-text">
          <template v-if="flow.detectedOS.value === 'macos'">After installing, open Ollama.app once — it will start the local server at <code>localhost:11434</code>.</template>
          <template v-else-if="flow.detectedOS.value === 'windows'">After installing, Ollama starts automatically in the background.</template>
          <template v-else>After installing, run <code>ollama serve</code> in a terminal to start the server.</template>
        </p>

        <!-- Installed but not running -->
        <div v-if="localModels.runtime.value?.installed && !localModels.runtime.value?.running" class="local-flow__start-hint">
          <span class="local-flow__dot local-flow__dot--yellow" />
          <div>
            <p class="local-flow__start-hint-title">Ollama is installed but not running</p>
            <p class="local-flow__start-hint-desc">Open the Ollama app or run <code>ollama serve</code></p>
          </div>
        </div>

        <!-- Secondary actions -->
        <div class="local-flow__install-actions">
          <button class="local-flow__secondary-btn" @click="flow.checkAgain()">
            I've installed Ollama
          </button>
          <button class="local-flow__link-btn" @click="showManualSetup = !showManualSetup">
            Manual setup
          </button>
        </div>

        <!-- Manual setup (expandable) -->
        <div v-if="showManualSetup" class="local-flow__manual">
          <template v-if="flow.detectedOS.value === 'linux'">
            <p class="local-flow__manual-label">Run this command in your terminal:</p>
            <div class="local-flow__cmd-block">
              <code class="local-flow__cmd-text">{{ linuxCommand }}</code>
              <button class="local-flow__cmd-copy" @click="copyLinuxCommand" :title="copiedCommand ? 'Copied!' : 'Copy command'">
                <template v-if="copiedCommand">✓</template>
                <template v-else>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                </template>
              </button>
            </div>
          </template>
          <p class="local-flow__manual-note">
            After installing, open Ollama once so it starts its local server at
            <code>http://localhost:11434</code>
          </p>
        </div>
      </div>
    </template>

    <!-- ==================== STATE: runtime_waiting ==================== -->
    <template v-else-if="flow.state.value === 'runtime_waiting'">
      <div class="local-flow__waiting">
        <h3 class="local-flow__section-title">Waiting for Ollama</h3>
        <p class="local-flow__section-desc">
          <template v-if="flow.detectedOS.value === 'macos'">Open <strong>Ollama.app</strong> once after installing — Jarvis will detect it automatically.</template>
          <template v-else-if="flow.detectedOS.value === 'windows'">Ollama should be running in the background. If not, try restarting it from the system tray.</template>
          <template v-else>Run <code>ollama serve</code> in your terminal, then click Check again.</template>
        </p>

        <!-- Status box -->
        <div class="local-flow__status-box">
          <div class="local-flow__status-row">
            <div class="local-flow__spinner local-flow__spinner--small" />
            <span class="local-flow__status-label">Checking localhost:11434</span>
          </div>
          <span class="local-flow__status-value">Not detected yet</span>
        </div>

        <!-- Installed but not running -->
        <div v-if="localModels.runtime.value?.installed && !localModels.runtime.value?.running" class="local-flow__start-hint">
          <span class="local-flow__dot local-flow__dot--yellow" />
          <div>
            <p class="local-flow__start-hint-title">Ollama is installed but not running</p>
            <p class="local-flow__start-hint-desc">Open the Ollama app or run <code>ollama serve</code></p>
          </div>
        </div>

        <div class="local-flow__install-actions">
          <button class="local-flow__secondary-btn" @click="flow.checkAgain()">
            Check again
          </button>
          <button class="local-flow__link-btn" @click="showManualSetup = !showManualSetup">
            Troubleshooting
          </button>
          <button class="local-flow__link-btn" @click="flow.state.value = 'runtime_missing'">
            Back
          </button>
        </div>

        <div v-if="showManualSetup" class="local-flow__manual">
          <p class="local-flow__manual-note">
            Make sure Ollama is running. It should be available at
            <code>http://localhost:11434</code>
          </p>
          <p class="local-flow__manual-note">
            On macOS/Windows: open the Ollama app once after install.<br>
            On Linux: run <code>ollama serve</code> in a terminal.
          </p>
        </div>
      </div>
    </template>

    <!-- ==================== STATE: model_selection ==================== -->
    <template v-else-if="flow.state.value === 'model_selection' || flow.state.value === 'runtime_ready'">
      <div class="local-flow__choose">
        <!-- Hardware summary card -->
        <div v-if="flow.hardwareSummary.value" class="local-flow__hw-card">
          <div class="local-flow__hw-card-header">
            <span class="local-flow__dot local-flow__dot--green" />
            <span class="local-flow__hw-card-title">Your computer</span>
            <span class="local-flow__hw-card-version">
              <template v-if="localModels.runtime.value?.version">Ollama v{{ localModels.runtime.value.version }}</template>
              <template v-if="localModels.runtime.value?.version && flow.hardwareSummary.value?.effectiveContext"> · </template>
              <template v-if="flow.hardwareSummary.value?.effectiveContext">Runtime context {{ flow.hardwareSummary.value.effectiveContext }}</template>
            </span>
          </div>
          <p class="local-flow__hw-card-specs">{{ flow.hardwareSummary.value.label }}</p>
          <p class="local-flow__hw-card-rec">{{ flow.hardwareSummary.value.recommendation }}</p>
        </div>

        <h3 class="local-flow__section-title">Choose a local model</h3>
        <p class="local-flow__section-desc">You can download more models later in Settings.</p>

        <!-- Recommended models (top 3) -->
        <div v-if="localModels.recommendedModels.value.length > 0" class="local-flow__model-list">
          <LocalModelCard
            v-for="m in localModels.recommendedModels.value.slice(0, 3)"
            :key="m.model_id"
            :model="m"
            :pulling="localModels.pulling.value === m.model_id"
            :progress="localModels.pulling.value === m.model_id ? localModels.pullProgress.value : null"
            @pull="handlePull"
            @select="handleSelect"
          />
        </div>

        <!-- Show all models (collapsed) -->
        <details v-if="localModels.catalog.value.length > 3" class="local-flow__all-models">
          <summary class="local-flow__show-all">
            Show all local models ({{ localModels.catalog.value.length }})
          </summary>
          <div class="local-flow__model-list local-flow__model-list--compact">
            <LocalModelCard
              v-for="m in localModels.catalog.value"
              :key="m.model_id"
              :model="m"
              :pulling="localModels.pulling.value === m.model_id"
              :progress="localModels.pulling.value === m.model_id ? localModels.pullProgress.value : null"
              compact
              @pull="handlePull"
              @select="handleSelect"
            />
          </div>
        </details>
      </div>
    </template>

    <!-- ==================== STATE: model_downloading ==================== -->
    <template v-else-if="flow.state.value === 'model_downloading'">
      <div class="local-flow__downloading">
        <h3 class="local-flow__section-title">
          Downloading {{ downloadingModel?.label ?? 'model' }}
        </h3>
        <p class="local-flow__section-desc">
          Jarvis is downloading the model to your computer.
        </p>

        <div class="local-flow__download-progress">
          <PullProgress
            v-if="localModels.pullProgress.value"
            :model-name="downloadingModel?.ollama_model ?? ''"
            :progress="localModels.pullProgress.value"
          />
          <div v-else class="local-flow__download-starting">
            <div class="local-flow__spinner" />
            <span>Preparing download...</span>
          </div>
        </div>

        <button class="local-flow__cancel-btn" @click="flow.cancelDownload()">
          Cancel download
        </button>
      </div>
    </template>

    <!-- ==================== STATE: model_ready ==================== -->
    <template v-else-if="flow.state.value === 'model_ready' || flow.state.value === 'local_active'">
      <div class="local-flow__ready">
        <div class="local-flow__ready-check">✓</div>
        <h3 class="local-flow__section-title">Jarvis is ready</h3>
        <p class="local-flow__ready-model">
          Using {{ readyModel?.label ?? 'local model' }} locally on this computer
        </p>

        <div class="local-flow__ready-details">
          <div class="local-flow__ready-detail">
            <span class="local-flow__ready-detail-label">Runtime</span>
            <span class="local-flow__ready-detail-value">Ollama</span>
          </div>
          <div class="local-flow__ready-detail">
            <span class="local-flow__ready-detail-label">Model</span>
            <span class="local-flow__ready-detail-value">{{ readyModel?.label ?? 'Local' }}</span>
          </div>
          <div class="local-flow__ready-detail">
            <span class="local-flow__ready-detail-label">Mode</span>
            <span class="local-flow__ready-detail-value">Local</span>
          </div>
          <div class="local-flow__ready-detail">
            <span class="local-flow__ready-detail-label">Privacy</span>
            <span class="local-flow__ready-detail-value">On-device</span>
          </div>
        </div>

        <button class="local-flow__primary-btn" @click="handleFinish">
          Open Jarvis
        </button>

        <div class="local-flow__ready-actions">
          <button class="local-flow__link-btn" @click="handleDownloadAnother">
            Download another model
          </button>
          <span class="local-flow__ready-sep">·</span>
          <span class="local-flow__ready-hint">Change later in Settings</span>
        </div>
      </div>
    </template>

    <!-- Error -->
    <p v-if="localModels.error.value" class="local-flow__error">
      {{ localModels.error.value }}
    </p>

    <div class="local-flow__footer">
      <button class="local-flow__back" @click="emit('back')">
        ← Back to choices
      </button>
    </div>
  </div>
</template>

<style scoped>
.local-flow {
  width: 100%;
}

.local-flow__title {
  font-size: 1.15rem;
  font-weight: 600;
  text-align: center;
  color: var(--text-primary);
  margin-bottom: 1.25rem;
}

/* ---- Step indicators ---- */
.local-flow__steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: 1.75rem;
  padding: 0 0.5rem;
}

.local-flow__step {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  opacity: 0.4;
  transition: opacity 0.3s;
}

.local-flow__step--active {
  opacity: 1;
}

.local-flow__step--done {
  opacity: 0.7;
}

.local-flow__step-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.7rem;
  font-weight: 700;
  border: 1.5px solid var(--border-default);
  color: var(--text-secondary);
  flex-shrink: 0;
}

.local-flow__step--active .local-flow__step-num {
  border-color: var(--neon-cyan);
  color: var(--neon-cyan);
  box-shadow: 0 0 8px var(--neon-cyan-08);
}

.local-flow__step--done .local-flow__step-num {
  border-color: #34d399;
  color: #34d399;
  background: rgba(52, 211, 153, 0.08);
}

.local-flow__step-label {
  font-size: 0.72rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.local-flow__step--active .local-flow__step-label {
  color: var(--text-primary);
  font-weight: 600;
}

.local-flow__step-line {
  width: 28px;
  height: 1px;
  background: var(--border-default);
  margin: 0 0.35rem;
  flex-shrink: 0;
  transition: background 0.3s;
}

.local-flow__step-line--done {
  background: #34d399;
}

/* ---- Shared section headings ---- */
.local-flow__section-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.3rem;
  text-align: center;
}

.local-flow__section-desc {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin-bottom: 1.25rem;
  text-align: center;
}

/* ---- Loading ---- */
.local-flow__loading {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
  font-size: 0.88rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
}

.local-flow__spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--border-default);
  border-top-color: var(--neon-cyan);
  border-radius: 50%;
  animation: local-spin 0.8s linear infinite;
}

.local-flow__spinner--small {
  width: 14px;
  height: 14px;
  border-width: 1.5px;
}

@keyframes local-spin {
  to { transform: rotate(360deg); }
}

/* ---- Step 1: Install / runtime_missing ---- */
.local-flow__install {
  text-align: center;
}

.local-flow__hw-badge {
  display: inline-block;
  font-size: 0.72rem;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  background: var(--neon-cyan-08);
  color: var(--neon-cyan-60);
  border: 1px solid var(--neon-cyan-15);
  margin-bottom: 1.25rem;
}

.local-flow__platform {
  margin-bottom: 1rem;
}

.local-flow__install-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1.5rem;
  border: 1px solid var(--neon-cyan-30);
  border-radius: 8px;
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.local-flow__install-btn:hover {
  background: rgba(2, 254, 255, 0.15);
  box-shadow: 0 0 16px var(--neon-cyan-08);
}

.local-flow__external-icon {
  opacity: 0.6;
}

.local-flow__helper-text {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-bottom: 1rem;
  line-height: 1.5;
}

/* ---- Installed-but-not-running hint ---- */
.local-flow__start-hint {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  margin: 0.75rem 0;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  background: rgba(251, 191, 36, 0.04);
  border: 1px solid rgba(251, 191, 36, 0.15);
  text-align: left;
}

.local-flow__start-hint-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: #fbbf24;
  margin-bottom: 0.1rem;
}

.local-flow__start-hint-desc {
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.local-flow__start-hint-desc code {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.72rem;
  background: var(--bg-elevated);
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  color: var(--neon-cyan);
}

.local-flow__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 0.2rem;
  flex-shrink: 0;
}

.local-flow__dot--green {
  background: #34d399;
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.4);
}

.local-flow__dot--yellow {
  background: #fbbf24;
  box-shadow: 0 0 6px rgba(251, 191, 36, 0.4);
}

/* ---- Secondary actions row ---- */
.local-flow__install-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  margin-top: 0.75rem;
  flex-wrap: wrap;
}

.local-flow__secondary-btn {
  padding: 0.3rem 0.65rem;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.78rem;
  cursor: pointer;
  transition: all 0.15s;
}

.local-flow__secondary-btn:hover:not(:disabled) {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
}

.local-flow__secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.local-flow__link-btn {
  padding: 0.3rem 0.4rem;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.75rem;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.local-flow__link-btn:hover {
  color: var(--neon-cyan-60);
}

/* ---- Manual setup expandable ---- */
.local-flow__manual {
  margin-top: 0.85rem;
  padding: 0.75rem;
  border-radius: 6px;
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  text-align: left;
}

.local-flow__manual-label {
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-bottom: 0.4rem;
}

.local-flow__manual-note {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.4rem;
  line-height: 1.5;
}

.local-flow__manual-note code {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.7rem;
  background: var(--bg-elevated);
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
  color: var(--neon-cyan);
}

.local-flow__cmd-block {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  padding: 0.45rem 0.65rem;
}

.local-flow__cmd-text {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.75rem;
  color: var(--neon-cyan);
  user-select: all;
}

.local-flow__cmd-copy {
  padding: 0.2rem 0.35rem;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.78rem;
  display: flex;
  align-items: center;
  transition: all 0.15s;
}

.local-flow__cmd-copy:hover {
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan);
}

/* ---- Step 1A: Waiting / runtime_waiting ---- */
.local-flow__waiting {
  text-align: center;
}

.local-flow__status-box {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: var(--bg-base);
  margin-bottom: 0.85rem;
}

.local-flow__status-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.local-flow__status-label {
  font-size: 0.78rem;
  color: var(--text-secondary);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.local-flow__status-value {
  font-size: 0.78rem;
  color: var(--text-muted);
}

/* ---- Step 2: Choose model / model_selection ---- */
.local-flow__choose {
  /* container */
}

.local-flow__hw-card {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  border: 1px solid rgba(52, 211, 153, 0.15);
  background: rgba(52, 211, 153, 0.03);
  margin-bottom: 1.25rem;
}

.local-flow__hw-card-header {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.2rem;
}

.local-flow__hw-card-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}

.local-flow__hw-card-version {
  margin-left: auto;
  font-size: 0.68rem;
  color: #34d399;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  white-space: nowrap;
}

.local-flow__hw-card-specs {
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.local-flow__hw-card-rec {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-top: 0.1rem;
}

.local-flow__model-list {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.local-flow__model-list--compact {
  margin-top: 0.65rem;
}

.local-flow__all-models {
  margin-top: 0.85rem;
}

.local-flow__show-all {
  font-size: 0.82rem;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.45rem;
  user-select: none;
  list-style: none;
  text-align: center;
  border: 1px dashed var(--border-default);
  border-radius: 6px;
  transition: all 0.15s;
}

.local-flow__show-all:hover {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
}

.local-flow__show-all::-webkit-details-marker {
  display: none;
}

/* ---- Step 2A: Downloading / model_downloading ---- */
.local-flow__downloading {
  text-align: center;
}

.local-flow__download-progress {
  margin-top: 0.5rem;
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: var(--bg-base);
  text-align: left;
}

.local-flow__download-starting {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 1rem;
  color: var(--text-muted);
  font-size: 0.85rem;
}

.local-flow__cancel-btn {
  display: block;
  width: 100%;
  margin-top: 1rem;
  padding: 0.5rem;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 0.8rem;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}

.local-flow__cancel-btn:hover {
  color: rgba(248, 113, 113, 0.9);
  border-color: rgba(248, 113, 113, 0.3);
}

/* ---- Step 3: Ready / model_ready ---- */
.local-flow__ready {
  text-align: center;
  padding: 0.5rem 0;
}

.local-flow__ready-check {
  width: 40px;
  height: 40px;
  margin: 0 auto 0.85rem;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  color: #34d399;
  background: rgba(52, 211, 153, 0.08);
  border: 1.5px solid rgba(52, 211, 153, 0.3);
}

.local-flow__ready-model {
  font-size: 0.88rem;
  color: var(--text-secondary);
  margin-bottom: 1.25rem;
}

.local-flow__ready-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--border-subtle);
  background: var(--bg-base);
  text-align: left;
}

.local-flow__ready-detail {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.local-flow__ready-detail-label {
  font-size: 0.68rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.local-flow__ready-detail-value {
  font-size: 0.82rem;
  color: var(--text-primary);
  font-weight: 500;
}

.local-flow__primary-btn {
  display: block;
  width: 100%;
  padding: 0.7rem 1.25rem;
  background: var(--neon-cyan, #02feff);
  color: var(--bg-deep, #06080d);
  border: none;
  border-radius: 6px;
  font-weight: 700;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.02em;
}

.local-flow__primary-btn:hover {
  box-shadow: 0 0 20px rgba(2, 254, 255, 0.25), 0 0 4px rgba(2, 254, 255, 0.4);
}

.local-flow__ready-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  margin-top: 0.85rem;
}

.local-flow__ready-sep {
  color: var(--text-muted);
  font-size: 0.72rem;
}

.local-flow__ready-hint {
  font-size: 0.75rem;
  color: var(--text-muted);
}

/* ---- Error ---- */
.local-flow__error {
  margin-top: 0.65rem;
  font-size: 0.8rem;
  color: rgba(248, 113, 113, 0.9);
  background: rgba(248, 113, 113, 0.06);
  border: 1px solid rgba(248, 113, 113, 0.2);
  border-radius: 6px;
  padding: 0.45rem 0.7rem;
}

/* ---- Footer ---- */
.local-flow__footer {
  margin-top: 1.5rem;
  display: flex;
  justify-content: flex-start;
}

.local-flow__back {
  padding: 0.35rem 0.75rem;
  background: transparent;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.15s;
}

.local-flow__back:hover {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
}
</style>
