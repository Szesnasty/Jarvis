<template>
  <div class="specialist-card" :class="{ 'specialist-card--active': active }">
    <div class="specialist-card__icon">{{ specialist.icon }}</div>
    <div class="specialist-card__info">
      <h3 class="specialist-card__name">{{ specialist.name }}</h3>
      <p class="specialist-card__meta">
        {{ specialist.source_count }} sources · {{ specialist.rule_count }} rules
      </p>
    </div>
    <div class="specialist-card__actions">
      <button class="specialist-card__activate-btn" @click.stop="$emit('activate', specialist.id)">
        {{ active ? 'Active' : 'Activate' }}
      </button>
      <button class="specialist-card__delete-btn" @click.stop="$emit('delete', specialist.id)">
        Delete
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SpecialistSummary } from '~/types'

defineProps<{
  specialist: SpecialistSummary
  active?: boolean
}>()

defineEmits<{
  activate: [id: string]
  delete: [id: string]
}>()
</script>

<style scoped>
.specialist-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 8px;
  cursor: pointer;
}
.specialist-card--active {
  border-color: var(--color-primary, #60a5fa);
  background: rgba(96, 165, 250, 0.08);
}
.specialist-card__icon {
  font-size: 2rem;
}
.specialist-card__info {
  flex: 1;
}
.specialist-card__name {
  margin: 0;
  font-size: 1rem;
}
.specialist-card__meta {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  opacity: 0.7;
}
.specialist-card__actions {
  display: flex;
  gap: 0.5rem;
}
.specialist-card__activate-btn,
.specialist-card__delete-btn {
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 4px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 0.85rem;
}
.specialist-card__activate-btn:hover {
  background: var(--color-primary, #60a5fa);
  color: #fff;
}
.specialist-card__delete-btn:hover {
  background: #ef4444;
  color: #fff;
}
</style>
