<script setup lang="ts">
import type { DuelConfig, SpecialistSummary } from '~/types'
import { useApiKeys, MODEL_CATALOG } from '~/composables/useApiKeys'

const { activeProvider, activeModel, providers } = useApiKeys()

const currentModelLabel = computed(() => {
  const catalog = MODEL_CATALOG[activeProvider.value]
  return catalog?.find(m => m.id === activeModel.value)?.label ?? activeModel.value
})

const currentProviderIcon = computed(() => {
  return providers.find(p => p.id === activeProvider.value)?.icon ?? ''
})

const props = defineProps<{
  specialists: SpecialistSummary[]
  prefillTopic?: string
  sessionDuelSpend?: number
}>()

const emit = defineEmits<{
  start: [config: DuelConfig]
  cancel: []
}>()

const topic = ref(props.prefillTopic ?? '')
const selectedIds = ref<Set<string>>(new Set())

function toggleSpecialist(id: string): void {
  const next = new Set(selectedIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else if (next.size < 2) {
    next.add(id)
  }
  selectedIds.value = next
}

const canStart = computed(() => topic.value.trim().length > 0 && selectedIds.value.size === 2)

const showSpendWarning = computed(() => (props.sessionDuelSpend ?? 0) > 1.0)

function handleStart(): void {
  if (!canStart.value) return
  emit('start', {
    topic: topic.value.trim(),
    specialist_ids: Array.from(selectedIds.value),
  })
}

// Sync prefill if changed externally
watch(() => props.prefillTopic, (v) => {
  if (v && !topic.value) topic.value = v
})
</script>

<template>
  <div class="duel-setup">
    <div class="duel-setup__header">
      <span class="duel-setup__icon">⚔️</span>
      <span class="duel-setup__title">Duel Mode</span>
    </div>

    <label class="duel-setup__label">Topic</label>
    <textarea
      v-model="topic"
      class="duel-setup__topic"
      placeholder="e.g. Should I change jobs this year?"
      rows="2"
    />

    <label class="duel-setup__label">Pick 2 specialists</label>
    <div class="duel-setup__list">
      <button
        v-for="spec in specialists"
        :key="spec.id"
        class="duel-setup__spec"
        :class="{
          'duel-setup__spec--selected': selectedIds.has(spec.id),
          'duel-setup__spec--disabled': !selectedIds.has(spec.id) && selectedIds.size >= 2,
        }"
        @click="toggleSpecialist(spec.id)"
      >
        <span class="duel-setup__spec-check">{{ selectedIds.has(spec.id) ? '✓' : '' }}</span>
        <span class="duel-setup__spec-icon">{{ spec.icon || '🤖' }}</span>
        <span class="duel-setup__spec-name">{{ spec.name }}</span>
      </button>
      <p v-if="specialists.length === 0" class="duel-setup__empty">
        No specialists found. Create at least 2 to use Duel Mode.
      </p>
    </div>

    <div class="duel-setup__model">
      <span class="duel-setup__model-icon" v-html="currentProviderIcon" />
      <span class="duel-setup__model-label">{{ currentModelLabel }}</span>
    </div>

    <div class="duel-setup__info">
      2 rounds · 5 scoring criteria · ~$0.08 · ~30s
    </div>

    <div v-if="showSpendWarning" class="duel-setup__warning">
      ⚠️ You've spent ~${{ (sessionDuelSpend ?? 0).toFixed(2) }} on duels today
    </div>

    <div class="duel-setup__actions">
      <button
        class="duel-setup__btn duel-setup__btn--start"
        :disabled="!canStart"
        @click="handleStart"
      >
        Start Duel
      </button>
      <button class="duel-setup__btn duel-setup__btn--cancel" @click="emit('cancel')">
        Cancel
      </button>
    </div>
  </div>
</template>

<style scoped>
.duel-setup {
  padding: 1.25rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  animation: slideUp 0.25s ease-out;
  position: relative;
  z-index: 210;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.duel-setup__header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.duel-setup__icon {
  font-size: 1.2rem;
}

.duel-setup__title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.duel-setup__label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.duel-setup__topic {
  resize: none;
  padding: 0.6rem 0.85rem;
  font-size: 0.9rem;
  line-height: 1.5;
  color: var(--text-primary);
  background: var(--bg-deep);
  border: 1px solid var(--border-default);
  border-radius: 8px;
  outline: none;
  font-family: inherit;
  transition: border-color 0.2s;
}

.duel-setup__topic:focus {
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 0 2px var(--neon-cyan-08);
}

.duel-setup__topic::placeholder {
  color: var(--text-muted);
}

.duel-setup__list {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  max-height: 200px;
  overflow-y: auto;
}

.duel-setup__spec {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  background: var(--bg-deep);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-primary);
  font-size: 0.88rem;
  font-family: inherit;
  transition: all 0.15s;
  text-align: left;
}

.duel-setup__spec:hover {
  border-color: var(--neon-cyan-30);
  background: var(--bg-elevated);
}

.duel-setup__spec--selected {
  border-color: var(--neon-cyan-60);
  background: rgba(2, 254, 255, 0.06);
}

.duel-setup__spec--disabled {
  opacity: 0.35;
  cursor: not-allowed;
  pointer-events: none;
}

.duel-setup__spec-check {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  color: var(--neon-cyan);
  flex-shrink: 0;
}

.duel-setup__spec--selected .duel-setup__spec-check {
  background: var(--neon-cyan-15);
  border-color: var(--neon-cyan-60);
}

.duel-setup__spec-icon {
  font-size: 1.1rem;
}

.duel-setup__spec-name {
  font-weight: 500;
}

.duel-setup__empty {
  font-size: 0.82rem;
  color: var(--text-muted);
  padding: 0.5rem 0;
}

.duel-setup__model {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.4rem 0.75rem;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  align-self: center;
}

.duel-setup__model-icon {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.duel-setup__model-icon :deep(svg) {
  width: 14px;
  height: 14px;
}

.duel-setup__model-label {
  font-size: 0.82rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.duel-setup__info {
  font-size: 0.78rem;
  color: var(--text-muted);
  text-align: center;
  padding: 0.25rem 0;
}

.duel-setup__warning {
  font-size: 0.82rem;
  color: var(--neon-orange);
  background: rgba(251, 146, 60, 0.06);
  border: 1px solid rgba(251, 146, 60, 0.2);
  border-radius: 6px;
  padding: 0.4rem 0.75rem;
  text-align: center;
}

.duel-setup__actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.duel-setup__btn {
  padding: 0.5rem 1.25rem;
  font-size: 0.88rem;
  font-weight: 600;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.2s;
}

.duel-setup__btn--start {
  background: var(--neon-cyan-15);
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan);
}

.duel-setup__btn--start:hover:not(:disabled) {
  background: var(--neon-cyan-30);
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 12px var(--neon-cyan-08);
}

.duel-setup__btn--start:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.duel-setup__btn--cancel {
  background: transparent;
  color: var(--text-secondary);
}

.duel-setup__btn--cancel:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}
</style>
