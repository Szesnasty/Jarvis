<script setup lang="ts">
const emit = defineEmits<{
  (e: 'model-ready'): void
  (e: 'back'): void
}>()

const localModels = useLocalModels()
const showAll = ref(false)

// Wizard step: 1=install, 2=choose, 3=downloading
const step = ref<1 | 2 | 3>(1)
let _pollInterval: ReturnType<typeof setInterval> | null = null
const pollStatus = ref<'idle' | 'waiting'>('idle')

// Detect user's OS for platform-specific install
const detectedOS = ref<'macos' | 'windows' | 'linux'>('linux')
if (import.meta.client) {
  const ua = navigator.userAgent.toLowerCase()
  if (ua.includes('mac')) detectedOS.value = 'macos'
  else if (ua.includes('win')) detectedOS.value = 'windows'
  else detectedOS.value = 'linux'
}

const linuxCommand = 'curl -fsSL https://ollama.com/install.sh | sh'
const copiedCommand = ref(false)

// Determine initial step based on runtime
onMounted(async () => {
  await localModels.refreshAll()
  if (localModels.isOllamaReady()) {
    step.value = 2
  } else {
    step.value = 1
  }
})

onUnmounted(() => {
  stopPolling()
})

function openInstallLink() {
  if (detectedOS.value === 'macos') {
    window.open('https://ollama.com/download/mac', '_blank', 'noopener')
  } else if (detectedOS.value === 'windows') {
    window.open('https://ollama.com/download/windows', '_blank', 'noopener')
  } else {
    window.open('https://ollama.com/download/linux', '_blank', 'noopener')
  }
  startPolling()
}

function copyLinuxCommand() {
  navigator.clipboard.writeText(linuxCommand)
  copiedCommand.value = true
  setTimeout(() => { copiedCommand.value = false }, 2000)
  startPolling()
}

function startPolling() {
  pollStatus.value = 'waiting'
  if (_pollInterval) return
  _pollInterval = setInterval(async () => {
    await localModels.fetchRuntime()
    if (localModels.isOllamaReady()) {
      stopPolling()
      await localModels.fetchCatalog()
      step.value = 2
    }
  }, 2500)
}

function stopPolling() {
  if (_pollInterval) {
    clearInterval(_pollInterval)
    _pollInterval = null
  }
  pollStatus.value = 'idle'
}

async function handleCheckAgain() {
  await localModels.fetchRuntime()
  if (localModels.isOllamaReady()) {
    await localModels.fetchCatalog()
    step.value = 2
  }
}

async function handlePull(modelId: string) {
  step.value = 3
  await localModels.pullModel(modelId)
  const model = localModels.catalog.value.find(m => m.model_id === modelId)
  if (model?.installed) {
    await localModels.selectModel(modelId)
    emit('model-ready')
  } else {
    // Pull failed or was cancelled — go back to choose
    step.value = 2
  }
}

async function handleSelect(modelId: string) {
  await localModels.selectModel(modelId)
  emit('model-ready')
}

const displayModels = computed(() => {
  if (showAll.value) return localModels.catalog.value
  return localModels.recommendedModels.value.slice(0, 3)
})

const isPulling = computed(() => !!localModels.pulling.value)

const hardwareLabel = computed(() => {
  const hw = localModels.hardware.value
  if (!hw) return ''
  const parts: string[] = []
  parts.push(`${hw.total_ram_gb.toFixed(0)} GB RAM`)
  if (hw.is_apple_silicon) parts.push('Apple Silicon')
  else if (hw.gpu_vendor) parts.push(`${hw.gpu_vendor} GPU`)
  return parts.join(' · ')
})
</script>

<template>
  <div class="local-flow">
    <!-- Step indicators -->
    <div class="local-flow__steps">
      <div class="local-flow__step" :class="{ 'local-flow__step--active': step === 1, 'local-flow__step--done': step > 1 }">
        <span class="local-flow__step-num">{{ step > 1 ? '✓' : '1' }}</span>
        <span class="local-flow__step-label">Install Ollama</span>
      </div>
      <div class="local-flow__step-line" :class="{ 'local-flow__step-line--done': step > 1 }" />
      <div class="local-flow__step" :class="{ 'local-flow__step--active': step === 2, 'local-flow__step--done': step > 2 }">
        <span class="local-flow__step-num">{{ step > 2 ? '✓' : '2' }}</span>
        <span class="local-flow__step-label">Choose a model</span>
      </div>
      <div class="local-flow__step-line" :class="{ 'local-flow__step-line--done': step > 2 }" />
      <div class="local-flow__step" :class="{ 'local-flow__step--active': step === 3 }">
        <span class="local-flow__step-num">3</span>
        <span class="local-flow__step-label">Start using Jarvis</span>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="localModels.loading.value" class="local-flow__loading">
      <div class="local-flow__spinner" />
      Detecting your hardware...
    </div>

    <!-- ==================== STEP 1: Install Ollama ==================== -->
    <template v-else-if="step === 1">
      <div class="local-flow__install">
        <h3 class="local-flow__install-title">Ollama powers local AI on your computer</h3>
        <p class="local-flow__install-desc">Install it once, then choose a model inside Jarvis.</p>

        <!-- Hardware info if detected -->
        <div v-if="hardwareLabel" class="local-flow__hw-badge">
          {{ hardwareLabel }}
        </div>

        <!-- Platform-specific install -->
        <div class="local-flow__platform">
          <!-- macOS -->
          <template v-if="detectedOS === 'macos'">
            <button class="local-flow__install-btn" @click="openInstallLink">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
              Download for macOS
              <svg class="local-flow__external-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </button>
            <p class="local-flow__install-note">After installing, open Ollama once to start it.</p>
          </template>

          <!-- Windows -->
          <template v-else-if="detectedOS === 'windows'">
            <button class="local-flow__install-btn" @click="openInstallLink">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.4H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.9-1.801"/></svg>
              Download for Windows
              <svg class="local-flow__external-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </button>
            <p class="local-flow__install-note">After installing, open Ollama once to start it.</p>
          </template>

          <!-- Linux -->
          <template v-else>
            <p class="local-flow__install-label">Run this command in your terminal:</p>
            <div class="local-flow__cmd-block">
              <code class="local-flow__cmd-text">{{ linuxCommand }}</code>
              <button class="local-flow__cmd-copy" @click="copyLinuxCommand" :title="copiedCommand ? 'Copied!' : 'Copy command'">
                <template v-if="copiedCommand">✓</template>
                <template v-else>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                </template>
              </button>
            </div>
            <p class="local-flow__install-note">Then come back here — Jarvis will detect it automatically.</p>
          </template>
        </div>

        <!-- Polling status -->
        <div class="local-flow__detect">
          <template v-if="pollStatus === 'waiting'">
            <div class="local-flow__detect-row">
              <div class="local-flow__spinner local-flow__spinner--small" />
              <span class="local-flow__detect-text">Waiting for Ollama on localhost:11434...</span>
            </div>
          </template>
          <template v-else>
            <span class="local-flow__detect-text local-flow__detect-text--dim">
              Jarvis checks localhost:11434 automatically
            </span>
          </template>
        </div>

        <!-- Secondary actions -->
        <div class="local-flow__install-actions">
          <button class="local-flow__secondary-btn" @click="handleCheckAgain" :disabled="localModels.loading.value">
            Check again
          </button>
          <a href="https://ollama.com/download" target="_blank" rel="noopener" class="local-flow__link">
            Manual setup
          </a>
        </div>

        <!-- Installed but not running -->
        <div v-if="localModels.runtime.value?.installed && !localModels.runtime.value?.running" class="local-flow__start-hint">
          <span class="local-flow__dot local-flow__dot--yellow" />
          <div>
            <p class="local-flow__start-hint-title">Ollama is installed but not running</p>
            <p class="local-flow__start-hint-desc">Open Ollama app or run <code>ollama serve</code></p>
          </div>
        </div>
      </div>
    </template>

    <!-- ==================== STEP 2: Choose a model ==================== -->
    <template v-else-if="step === 2">
      <div class="local-flow__choose">
        <div class="local-flow__ollama-ok">
          <span class="local-flow__dot local-flow__dot--green" />
          <span class="local-flow__ollama-ok-text">
            Ollama running
            <template v-if="localModels.runtime.value?.version">
              v{{ localModels.runtime.value.version }}
            </template>
          </span>
          <span v-if="hardwareLabel" class="local-flow__hw-inline">{{ hardwareLabel }}</span>
        </div>

        <h3 class="local-flow__choose-title">Choose a model for Jarvis</h3>
        <p class="local-flow__choose-desc">Recommended for your computer:</p>

        <div class="local-flow__model-list">
          <LocalModelCard
            v-for="m in displayModels"
            :key="m.model_id"
            :model="m"
            :pulling="localModels.pulling.value === m.model_id"
            :progress="localModels.pulling.value === m.model_id ? localModels.pullProgress.value : null"
            @pull="handlePull"
            @select="handleSelect"
          />
        </div>

        <button
          v-if="!showAll && localModels.catalog.value.length > 3"
          class="local-flow__show-all"
          @click="showAll = true"
        >
          Show all models ({{ localModels.catalog.value.length }})
        </button>
      </div>
    </template>

    <!-- ==================== STEP 3: Downloading ==================== -->
    <template v-else-if="step === 3">
      <div class="local-flow__downloading">
        <h3 class="local-flow__download-title">Downloading model...</h3>
        <p class="local-flow__download-hint">
          This may take a few minutes depending on your connection.
        </p>

        <!-- Show the card that's being pulled -->
        <div v-if="localModels.pulling.value" class="local-flow__pulling-card">
          <LocalModelCard
            v-for="m in localModels.catalog.value.filter(c => c.model_id === localModels.pulling.value)"
            :key="m.model_id"
            :model="m"
            :pulling="true"
            :progress="localModels.pullProgress.value"
            @pull="() => {}"
            @select="() => {}"
          />
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
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
}

.local-flow__step--active .local-flow__step-label {
  color: var(--text-primary);
  font-weight: 600;
}

.local-flow__step-line {
  width: 32px;
  height: 1px;
  background: var(--border-default);
  margin: 0 0.4rem;
  flex-shrink: 0;
  transition: background 0.3s;
}

.local-flow__step-line--done {
  background: #34d399;
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

/* ---- Step 1: Install ---- */
.local-flow__install {
  text-align: center;
}

.local-flow__install-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.35rem;
}

.local-flow__install-desc {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-bottom: 1.25rem;
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
  margin-bottom: 1.25rem;
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
  font-size: 0.9rem;
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

.local-flow__install-note {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-top: 0.65rem;
}

.local-flow__install-label {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin-bottom: 0.5rem;
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

/* ---- Detection status ---- */
.local-flow__detect {
  margin: 1rem 0 0.5rem;
}

.local-flow__detect-row {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
}

.local-flow__detect-text {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.local-flow__detect-text--dim {
  color: var(--text-muted);
}

.local-flow__install-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 0.75rem;
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

.local-flow__link {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-decoration: none;
}

.local-flow__link:hover {
  color: var(--neon-cyan-60);
  text-decoration: underline;
  text-underline-offset: 2px;
}

/* ---- Installed but not running hint ---- */
.local-flow__start-hint {
  display: flex;
  align-items: flex-start;
  gap: 0.65rem;
  margin-top: 1.25rem;
  padding: 0.75rem 1rem;
  border-radius: 8px;
  background: rgba(251, 191, 36, 0.04);
  border: 1px solid rgba(251, 191, 36, 0.15);
  text-align: left;
}

.local-flow__start-hint-title {
  font-size: 0.82rem;
  font-weight: 600;
  color: #fbbf24;
  margin-bottom: 0.15rem;
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

/* ---- Step 2: Choose ---- */
.local-flow__choose {
  /* no extra container styles needed */
}

.local-flow__ollama-ok {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 1rem;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  background: rgba(52, 211, 153, 0.04);
  border: 1px solid rgba(52, 211, 153, 0.15);
}

.local-flow__ollama-ok-text {
  font-size: 0.82rem;
  font-weight: 600;
  color: #34d399;
}

.local-flow__hw-inline {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-left: auto;
}

.local-flow__choose-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.25rem;
}

.local-flow__choose-desc {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin-bottom: 0.85rem;
}

.local-flow__model-list {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.local-flow__show-all {
  display: block;
  width: 100%;
  margin-top: 0.65rem;
  padding: 0.45rem;
  background: transparent;
  border: 1px dashed var(--border-default);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.15s;
}

.local-flow__show-all:hover {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
}

/* ---- Step 3: Downloading ---- */
.local-flow__downloading {
  text-align: center;
}

.local-flow__download-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.35rem;
}

.local-flow__download-hint {
  font-size: 0.82rem;
  color: var(--text-muted);
  margin-bottom: 1rem;
}

.local-flow__pulling-card {
  text-align: left;
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
