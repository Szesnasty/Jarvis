<script setup lang="ts">
import type { ModelRecommendation, PullProgress as PullProgressType } from '~/types'

const props = defineProps<{
  model: ModelRecommendation
  pulling: boolean
  progress: PullProgressType | null
  disabled?: boolean
  compact?: boolean
}>()

const emit = defineEmits<{
  pull: [modelId: string]
  select: [modelId: string]
}>()

const presetLabel = computed(() => {
  const map: Record<string, string> = {
    fast: 'Fast',
    everyday: 'Everyday',
    balanced: 'Balanced',
    'long-docs': 'Long Docs',
    reasoning: 'Reasoning',
    code: 'Code',
    'best-local': 'Best Local',
  }
  return map[props.model.preset] ?? props.model.preset
})

const toolBadge = computed(() => {
  const mode = props.model.tool_mode
  if (mode === 'native') return { label: 'Native tools', cssClass: 'tool-badge--native', icon: '✅' }
  if (mode === 'json_fallback') return { label: 'Tools via prompt', cssClass: 'tool-badge--fallback', icon: '⚠️' }
  return { label: 'Limited tool support', cssClass: 'tool-badge--limited', icon: '❌' }
})

const buttonState = computed(() => {
  if (props.disabled) return 'disabled'
  if (props.pulling) return 'pulling'
  if (props.model.active) return 'active'
  if (props.model.installed) return 'installed'
  if (props.model.compatibility === 'unsupported') return 'unsupported'
  return 'available'
})
</script>

<template>
  <div class="model-card" :class="{ 'model-card--active': model.active, 'model-card--disabled': disabled, 'model-card--compact': compact }">
    <div class="model-card__top">
      <span class="model-card__name">{{ model.label }}</span>
      <span class="model-card__preset">{{ presetLabel }}</span>
    </div>

    <div class="model-card__meta">
      <span>{{ model.download_size_gb }} GB</span>
      <span class="model-card__sep">·</span>
      <span>Max context {{ model.context_window }}</span>
    </div>

    <p v-if="!compact" class="model-card__hw-req">Recommended hardware: {{ model.recommended_ram }}</p>

    <template v-if="!compact">
      <div class="model-card__tags">
        <span v-for="s in model.strengths.slice(0, 3)" :key="s" class="model-card__tag">{{ s }}</span>
      </div>

      <div class="model-card__tool-badge" :class="toolBadge.cssClass" :title="toolBadge.label">
        <span class="model-card__tool-icon">{{ toolBadge.icon }}</span>
        <span>{{ toolBadge.label }}</span>
      </div>

      <p v-if="model.best_for && model.best_for.length" class="model-card__best-for">
        Best for: {{ model.best_for.slice(0, 2).join(', ') }}
      </p>

      <p v-if="model.context_window === '40K'" class="model-card__ctx-hint">
        Good for everyday chat. For long documents, choose a 128K–384K model.
      </p>

      <p v-if="model.reason && model.compatibility !== 'great'" class="model-card__reason">{{ model.reason }}</p>
    </template>

    <div v-if="compact" class="model-card__tool-badge model-card__tool-badge--inline" :class="toolBadge.cssClass" :title="toolBadge.label">
      <span class="model-card__tool-icon">{{ toolBadge.icon }}</span>
      <span>{{ toolBadge.label }}</span>
    </div>

    <!-- Actions -->
    <div class="model-card__action">
      <template v-if="buttonState === 'disabled'">
        <button class="model-card__btn" disabled>
          Start Ollama first
        </button>
      </template>
      <template v-else-if="buttonState === 'pulling'">
        <PullProgress :model-name="model.ollama_model" :progress="progress" />
      </template>
      <template v-else-if="buttonState === 'active'">
        <button class="model-card__btn model-card__btn--active" disabled>
          Active
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
        </button>
      </template>
      <template v-else-if="buttonState === 'installed'">
        <button class="model-card__btn model-card__btn--use" @click="emit('select', model.model_id)">
          Use This Model
        </button>
      </template>
      <template v-else-if="buttonState === 'unsupported'">
        <button class="model-card__btn" disabled>
          Not enough resources
        </button>
      </template>
      <template v-else>
        <button
          class="model-card__btn model-card__btn--download"
          @click="emit('pull', model.model_id)"
        >
          Download &amp; Use
        </button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.model-card {
  padding: 0.85rem 1rem;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: var(--bg-base);
  transition: border-color 0.2s;
}

.model-card:hover {
  border-color: var(--neon-cyan-15);
}

.model-card--active {
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 12px var(--neon-cyan-08);
}

.model-card--disabled {
  opacity: 0.55;
}

.model-card--compact {
  padding: 0.55rem 0.75rem;
}

.model-card--compact .model-card__name {
  font-size: 0.85rem;
}

.model-card--compact .model-card__meta {
  margin-bottom: 0.25rem;
}

.model-card__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}

.model-card__name {
  font-weight: 600;
  font-size: 0.92rem;
  color: var(--text-primary);
}

.model-card__preset {
  font-size: 0.68rem;
  font-weight: 600;
  padding: 0.12rem 0.45rem;
  border-radius: 4px;
  background: var(--neon-cyan-08);
  color: var(--neon-cyan-60);
  border: 1px solid var(--neon-cyan-15);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.model-card__meta {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-bottom: 0.3rem;
}

.model-card__hw-req {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-bottom: 0.45rem;
}

.model-card__sep {
  margin: 0 0.25rem;
}

.model-card__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-bottom: 0.55rem;
}

.model-card__tag {
  font-size: 0.68rem;
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
}

.model-card__tool-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.7rem;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  margin-bottom: 0.45rem;
}

.model-card__tool-icon {
  font-size: 0.65rem;
}

.tool-badge--native {
  color: #34d399;
  background: rgba(52, 211, 153, 0.08);
}

.tool-badge--fallback {
  color: #fbbf24;
  background: rgba(251, 191, 36, 0.08);
}

.tool-badge--limited {
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.03);
}

.model-card__reason {
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-bottom: 0.55rem;
  line-height: 1.4;
}

.model-card__best-for {
  font-size: 0.75rem;
  color: var(--text-secondary);
  margin-bottom: 0.45rem;
}

.model-card__ctx-hint {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-bottom: 0.45rem;
  line-height: 1.4;
  padding: 0.25rem 0.45rem;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid var(--border-subtle);
}

.model-card__tool-badge--inline {
  margin-bottom: 0.3rem;
}

.model-card__action {
  min-height: 36px;
}

.model-card__btn {
  width: 100%;
  padding: 0.4rem 0.75rem;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.35rem;
}

.model-card__btn:hover:not(:disabled) {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
}

.model-card__btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.model-card__btn--download {
  border-color: var(--neon-cyan-30);
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
}

.model-card__btn--download:hover {
  background: rgba(2, 254, 255, 0.15);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}

.model-card__btn--use {
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan);
}

.model-card__btn--use:hover {
  background: var(--neon-cyan-08);
}

.model-card__btn--active {
  border-color: rgba(52, 211, 153, 0.3);
  color: #34d399;
  background: rgba(52, 211, 153, 0.06);
}
</style>
