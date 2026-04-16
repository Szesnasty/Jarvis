<script setup lang="ts">
import type { PullProgress } from '~/types'

const props = defineProps<{
  modelName: string
  progress: PullProgress | null
}>()

const percentage = computed(() => {
  const p = props.progress
  if (!p || !p.total || !p.completed) return 0
  return Math.round((p.completed / p.total) * 100)
})

function formatBytes(bytes: number): string {
  const gb = bytes / 1e9
  if (gb >= 1) return gb.toFixed(1) + ' GB'
  const mb = bytes / 1e6
  return mb.toFixed(0) + ' MB'
}
</script>

<template>
  <div class="pull-progress">
    <div class="pull-progress__header">
      <span class="pull-progress__label">Downloading {{ modelName }}...</span>
      <span class="pull-progress__pct">{{ percentage }}%</span>
    </div>
    <div class="pull-progress__track">
      <div class="pull-progress__fill" :style="{ width: percentage + '%' }" />
    </div>
    <div class="pull-progress__detail">
      <span v-if="progress?.completed && progress?.total">
        {{ formatBytes(progress.completed) }} / {{ formatBytes(progress.total) }}
      </span>
      <span v-else class="pull-progress__status">{{ progress?.status ?? 'Preparing...' }}</span>
    </div>
  </div>
</template>

<style scoped>
.pull-progress {
  padding: 0.65rem 0;
}

.pull-progress__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.35rem;
}

.pull-progress__label {
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.pull-progress__pct {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--neon-cyan);
}

.pull-progress__track {
  height: 6px;
  border-radius: 3px;
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  overflow: hidden;
}

.pull-progress__fill {
  height: 100%;
  border-radius: 3px;
  background: var(--neon-cyan);
  box-shadow: 0 0 8px var(--neon-cyan-30);
  transition: width 0.3s ease;
}

.pull-progress__detail {
  margin-top: 0.25rem;
  font-size: 0.7rem;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.pull-progress__status {
  text-transform: capitalize;
}
</style>
