<template>
  <div
    class="spec-card"
    :class="{
      'spec-card--active': active,
      'spec-card--expanded': expanded,
    }"
  >
    <!-- Main row -->
    <div class="spec-card__main" @click="$emit('toggle-expand', specialist.id)">
      <div class="spec-card__icon-wrap">
        <span class="spec-card__icon">{{ specialist.icon }}</span>
        <span v-if="active" class="spec-card__active-dot" />
      </div>

      <div class="spec-card__body">
        <div class="spec-card__name-row">
          <h3 class="spec-card__name">{{ specialist.name }}</h3>
          <span v-if="active" class="spec-card__active-tag">Active</span>
        </div>
        <div class="spec-card__stats">
          <span class="spec-card__stat">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            {{ specialist.file_count || 0 }} files
          </span>
          <span class="spec-card__stat-dot">&middot;</span>
          <span class="spec-card__stat">{{ specialist.source_count }} sources</span>
          <span class="spec-card__stat-dot">&middot;</span>
          <span class="spec-card__stat">{{ specialist.rule_count }} rules</span>
          <template v-if="specialist.default_model">
            <span class="spec-card__stat-dot">&middot;</span>
            <span class="spec-card__stat spec-card__stat--model">
              <span class="spec-card__model-icon" v-html="providerIcon(specialist.default_model)" />
              {{ modelLabel(specialist.default_model) }}
            </span>
          </template>
        </div>
      </div>

      <div class="spec-card__actions" @click.stop>
        <button
          class="spec-card__btn spec-card__btn--activate"
          :class="{ 'spec-card__btn--activated': active }"
          @click="$emit('activate', specialist.id)"
          :title="active ? 'Deactivate' : 'Activate'"
        >
          <svg v-if="active" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>
            <line x1="12" y1="2" x2="12" y2="12"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
        </button>
        <button
          class="spec-card__btn spec-card__btn--edit"
          title="Edit specialist"
          @click="$emit('edit', specialist.id)"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
        </button>
        <button
          class="spec-card__btn spec-card__btn--delete"
          title="Delete specialist"
          @click="$emit('delete', specialist.id)"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
            <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
        </button>
        <button
          class="spec-card__btn spec-card__btn--expand"
          :class="{ 'spec-card__btn--expand-open': expanded }"
          @click="$emit('toggle-expand', specialist.id)"
          title="Toggle knowledge panel"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Expandable knowledge panel -->
    <Transition name="expand">
      <SpecialistKnowledgePanel
        v-if="expanded"
        :specialist-id="specialist.id"
      />
    </Transition>
  </div>
</template>

<script setup lang="ts">
import type { SpecialistSummary } from '~/types'
import { MODEL_CATALOG } from '~/composables/useApiKeys'
import { PROVIDER_ICONS } from '~/composables/providerIcons'

function modelLabel(dm?: { provider: string; model: string } | null): string {
  if (!dm) return ''
  const catalog = MODEL_CATALOG[dm.provider]
  return catalog?.find(m => m.id === dm.model)?.label ?? dm.model
}

function providerIcon(dm?: { provider: string; model: string } | null): string {
  if (!dm) return ''
  return (PROVIDER_ICONS as Record<string, string>)[dm.provider] ?? ''
}

defineProps<{
  specialist: SpecialistSummary
  active?: boolean
  expanded?: boolean
}>()

defineEmits<{
  activate: [id: string]
  edit: [id: string]
  delete: [id: string]
  'toggle-expand': [id: string]
}>()
</script>

<style scoped>
.spec-card {
  border: 1px solid var(--border-default);
  border-radius: 12px;
  background: var(--bg-surface);
  transition: all 0.25s ease;
  overflow: hidden;
  position: relative;
  width: 100%;
}

/* Subtle scanline texture */
.spec-card::after {
  content: '';
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 3px,
    rgba(2, 254, 255, 0.008) 3px,
    rgba(2, 254, 255, 0.008) 4px
  );
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.3s;
}

.spec-card:hover::after,
.spec-card--expanded::after {
  opacity: 1;
}

.spec-card:hover {
  border-color: var(--border-strong);
  box-shadow: 0 2px 16px rgba(0, 0, 0, 0.2);
}

.spec-card--active {
  border-color: var(--neon-cyan-30);
  background:
    linear-gradient(135deg, var(--neon-cyan-08) 0%, transparent 60%),
    var(--bg-surface);
  box-shadow:
    0 0 20px var(--neon-cyan-08),
    inset 0 1px 0 var(--neon-cyan-15);
}

.spec-card--expanded {
  border-color: var(--neon-cyan-15);
}

/* --- Main row --- */
.spec-card__main {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem 1.25rem;
  cursor: pointer;
  position: relative;
  z-index: 1;
}

/* --- Icon --- */
.spec-card__icon-wrap {
  position: relative;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  flex-shrink: 0;
}

.spec-card--active .spec-card__icon-wrap {
  background: var(--neon-cyan-08);
  border-color: var(--neon-cyan-15);
}

.spec-card__icon {
  font-size: 1.4rem;
  line-height: 1;
}

.spec-card__active-dot {
  position: absolute;
  bottom: -1px;
  right: -1px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--neon-cyan);
  border: 2px solid var(--bg-surface);
  box-shadow: 0 0 6px var(--neon-cyan-60);
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { box-shadow: 0 0 4px var(--neon-cyan-30); }
  50% { box-shadow: 0 0 10px var(--neon-cyan-60); }
}

/* --- Body --- */
.spec-card__body {
  flex: 1;
  min-width: 0;
}

.spec-card__name-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.spec-card__name {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.spec-card__active-tag {
  font-size: 0.6rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  background: var(--neon-cyan-15);
  color: var(--neon-cyan);
  border: 1px solid var(--neon-cyan-30);
  flex-shrink: 0;
}

.spec-card__stats {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin-top: 0.2rem;
}

.spec-card__stat {
  display: flex;
  align-items: center;
  gap: 0.2rem;
  font-size: 0.72rem;
  color: var(--text-muted);
}

.spec-card__stat svg {
  color: var(--text-muted);
}

.spec-card__stat-dot {
  color: var(--text-muted);
  font-size: 0.65rem;
}

.spec-card__stat--model {
  color: var(--text-secondary);
}

.spec-card__model-icon {
  display: inline-flex;
  width: 11px;
  height: 11px;
}

.spec-card__model-icon :deep(svg) {
  width: 11px;
  height: 11px;
}

/* --- Actions --- */
.spec-card__actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-shrink: 0;
}

.spec-card__btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.spec-card__btn:hover {
  background: var(--bg-hover);
  border-color: var(--border-default);
  color: var(--text-primary);
}

.spec-card__btn--activate:hover {
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan);
  background: var(--neon-cyan-08);
  box-shadow: 0 0 8px var(--neon-cyan-08);
}

.spec-card__btn--activated {
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan);
  background: var(--neon-cyan-08);
}

.spec-card__btn--edit:hover {
  border-color: rgba(234, 179, 8, 0.3);
  color: var(--neon-yellow);
  background: rgba(234, 179, 8, 0.08);
}

.spec-card__btn--delete:hover {
  border-color: rgba(239, 68, 68, 0.3);
  color: var(--neon-red);
  background: rgba(239, 68, 68, 0.08);
}

.spec-card__btn--expand {
  transition: all 0.2s, transform 0.3s ease;
}

.spec-card__btn--expand-open {
  transform: rotate(180deg);
}

/* --- Expand transition --- */
.expand-enter-active {
  transition: all 0.3s ease;
  overflow: hidden;
}
.expand-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>
