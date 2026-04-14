<template>
  <div class="provider-card" :class="{ 'provider-card--configured': configured }">
    <div class="provider-card__header">
      <span class="provider-card__icon" :style="{ color: provider.color }" v-html="provider.icon"></span>
      <span class="provider-card__name">{{ provider.name }}</span>
      <div class="provider-card__actions">
        <span v-if="configured" class="provider-card__badge">✅ Configured</span>
        <button v-if="!configured" class="provider-card__btn provider-card__btn--add" @click="$emit('addKey')">
          Add Key
        </button>
        <button v-if="configured" class="provider-card__btn provider-card__btn--remove" @click="$emit('removeKey')">
          Remove
        </button>
      </div>
    </div>
    <div class="provider-card__detail">
      <template v-if="configured">
        <span class="provider-card__masked">{{ maskedKey }}</span>
        <span class="provider-card__storage">{{ remembered ? 'remembered' : 'this session only' }}</span>
      </template>
      <template v-else-if="showModels">
        <span class="provider-card__models">{{ provider.models.map(m => shortModel(m)).join(', ') }}</span>
      </template>
      <template v-else>
        <span class="provider-card__no-key">No key added</span>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ProviderConfig } from '~/types'

const props = defineProps<{
  provider: ProviderConfig
  configured: boolean
  maskedKey: string
  remembered: boolean
  showModels?: boolean
}>()

defineEmits<{
  addKey: []
  removeKey: []
}>()

function shortModel(model: string): string {
  // "claude-sonnet-4-20250514" → "Claude Sonnet"
  // "gpt-4o" → "GPT-4o"
  // "gemini-2.5-flash" → "Gemini 2.5 Flash"
  return model
    .replace(/-\d{8}$/, '')
    .replace(/^claude-/, 'Claude ')
    .replace(/^gpt-/, 'GPT-')
    .replace(/^gemini-/, 'Gemini ')
    .replace(/^o3-/, 'o3-')
    .split('-').map(w => w === w.toUpperCase() ? w : w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
    .replace(/  +/g, ' ')
    .trim()
}
</script>

<style scoped>
.provider-card {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-subtle);
  transition: background 0.15s;
}
.provider-card:last-child {
  border-bottom: none;
}
.provider-card:hover {
  background: var(--bg-hover);
}
.provider-card__header {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.provider-card__icon {
  width: 1.5rem;
  height: 1.5rem;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.provider-card__icon :deep(svg) {
  width: 100%;
  height: 100%;
}
.provider-card__name {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}
.provider-card__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.provider-card__badge {
  font-size: 0.72rem;
  font-weight: 600;
  color: #34d399;
  background: rgba(52, 211, 153, 0.08);
  border: 1px solid rgba(52, 211, 153, 0.25);
  padding: 0.15rem 0.5rem;
  border-radius: 12px;
}
.provider-card__btn {
  padding: 0.25rem 0.7rem;
  border-radius: 4px;
  font-size: 0.78rem;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid;
}
.provider-card__btn--add {
  border-color: var(--neon-cyan-30);
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
}
.provider-card__btn--add:hover {
  background: rgba(2, 254, 255, 0.15);
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}
.provider-card__btn--remove {
  border-color: rgba(248, 113, 113, 0.25);
  background: rgba(248, 113, 113, 0.06);
  color: rgba(248, 113, 113, 0.8);
}
.provider-card__btn--remove:hover {
  background: rgba(248, 113, 113, 0.12);
  border-color: rgba(248, 113, 113, 0.4);
}
.provider-card__detail {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-left: 2.2rem;
  font-size: 0.78rem;
}
.provider-card__masked {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  color: var(--text-secondary);
}
.provider-card__storage {
  color: var(--text-muted);
  font-style: italic;
}
.provider-card__no-key {
  color: var(--text-muted);
}
.provider-card__models {
  color: var(--text-muted);
}
</style>
