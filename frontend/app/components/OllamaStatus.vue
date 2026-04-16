<script setup lang="ts">
import type { HardwareProfile, RuntimeStatus } from '~/types'

const props = defineProps<{
  runtime: RuntimeStatus | null
  hardware: HardwareProfile | null
  loading: boolean
}>()

const emit = defineEmits<{
  refresh: []
}>()

function openOllamaDownload() {
  window.open('https://ollama.com/download', '_blank', 'noopener')
}

function tierLabel(tier: string): string {
  const labels: Record<string, string> = {
    light: 'Light',
    balanced: 'Balanced',
    strong: 'Strong',
    workstation: 'Workstation',
  }
  return labels[tier] ?? tier
}

function formatRam(gb: number): string {
  return gb.toFixed(0) + ' GB'
}
</script>

<template>
  <div class="ollama-status" :class="statusClass">
    <!-- Not installed -->
    <template v-if="!runtime || !runtime.installed">
      <div class="ollama-status__header">
        <span class="ollama-status__dot ollama-status__dot--red" />
        <span class="ollama-status__title">Ollama not found</span>
      </div>
      <p class="ollama-status__desc">
        Ollama is required to run local AI models on your computer.
      </p>
      <div class="ollama-status__actions">
        <button class="ollama-status__btn ollama-status__btn--primary" @click="openOllamaDownload">
          Install Ollama
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        </button>
        <button class="ollama-status__btn" :disabled="loading" @click="emit('refresh')">
          Check Again
        </button>
      </div>
    </template>

    <!-- Installed but not running -->
    <template v-else-if="!runtime.running">
      <div class="ollama-status__header">
        <span class="ollama-status__dot ollama-status__dot--yellow" />
        <span class="ollama-status__title">Ollama installed but not running</span>
      </div>
      <p class="ollama-status__desc">
        Start Ollama to use local models.
      </p>
      <code class="ollama-status__command">ollama serve</code>
      <div class="ollama-status__actions">
        <button class="ollama-status__btn" :disabled="loading" @click="emit('refresh')">
          Check Again
        </button>
      </div>
    </template>

    <!-- Running -->
    <template v-else>
      <div class="ollama-status__header">
        <span class="ollama-status__dot ollama-status__dot--green" />
        <span class="ollama-status__title">Ollama running</span>
        <span v-if="runtime.version" class="ollama-status__version">v{{ runtime.version }}</span>
      </div>
      <div class="ollama-status__info">
        <span class="ollama-status__url">{{ runtime.base_url }}</span>
      </div>
      <div v-if="hardware" class="ollama-status__hw">
        <span>{{ formatRam(hardware.total_ram_gb) }} RAM</span>
        <span v-if="hardware.is_apple_silicon" class="ollama-status__chip">Apple Silicon</span>
        <span v-else-if="hardware.gpu_vendor" class="ollama-status__chip">{{ hardware.gpu_vendor }} GPU</span>
        <span class="ollama-status__tier">{{ tierLabel(hardware.tier) }}</span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ollama-status {
  padding: 0.85rem 1rem;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: var(--bg-base);
}

.ollama-status__header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.35rem;
}

.ollama-status__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.ollama-status__dot--red {
  background: #f87171;
  box-shadow: 0 0 6px rgba(248, 113, 113, 0.4);
}

.ollama-status__dot--yellow {
  background: #fbbf24;
  box-shadow: 0 0 6px rgba(251, 191, 36, 0.4);
}

.ollama-status__dot--green {
  background: #34d399;
  box-shadow: 0 0 6px rgba(52, 211, 153, 0.4);
}

.ollama-status__title {
  font-weight: 600;
  font-size: 0.88rem;
  color: var(--text-primary);
}

.ollama-status__version {
  font-size: 0.72rem;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.ollama-status__desc {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin: 0.25rem 0 0.65rem;
}

.ollama-status__command {
  display: inline-block;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.78rem;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 4px;
  padding: 0.25rem 0.5rem;
  margin-bottom: 0.65rem;
  color: var(--neon-cyan);
}

.ollama-status__actions {
  display: flex;
  gap: 0.5rem;
}

.ollama-status__btn {
  padding: 0.35rem 0.75rem;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.78rem;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.ollama-status__btn:hover:not(:disabled) {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
}

.ollama-status__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ollama-status__btn--primary {
  border-color: var(--neon-cyan-30);
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
}

.ollama-status__btn--primary:hover {
  background: rgba(2, 254, 255, 0.15);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}

.ollama-status__info {
  margin-bottom: 0.35rem;
}

.ollama-status__url {
  font-size: 0.72rem;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  color: var(--text-muted);
}

.ollama-status__hw {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.78rem;
  color: var(--text-secondary);
  flex-wrap: wrap;
}

.ollama-status__chip {
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  background: rgba(52, 211, 153, 0.08);
  color: #34d399;
  border: 1px solid rgba(52, 211, 153, 0.2);
}

.ollama-status__tier {
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
  background: var(--neon-cyan-08);
  color: var(--neon-cyan-60);
  border: 1px solid var(--neon-cyan-15);
}
</style>
