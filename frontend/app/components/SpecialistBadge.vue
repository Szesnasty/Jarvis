<template>
  <div class="specialist-badge" v-if="specialist" @click="$emit('click')">
    <span class="specialist-badge__icon">{{ specialist.icon }}</span>
    <span class="specialist-badge__name">{{ specialist.name }}</span>
    <button class="specialist-badge__close" @click.stop="$emit('deactivate')">&times;</button>
  </div>
</template>

<script setup lang="ts">
import type { SpecialistDetail } from '~/types'

defineProps<{
  specialist: SpecialistDetail | null
}>()

defineEmits<{
  click: []
  deactivate: []
}>()
</script>

<style scoped>
.specialist-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.75rem;
  border-radius: 999px;
  background: rgba(96, 165, 250, 0.15);
  color: var(--color-primary, #60a5fa);
  font-size: 0.85rem;
  cursor: pointer;
}
.specialist-badge__icon {
  font-size: 1rem;
}
.specialist-badge__name {
  font-weight: 500;
}
.specialist-badge__close {
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 1.1rem;
  padding: 0;
  line-height: 1;
  opacity: 0.7;
}
.specialist-badge__close:hover {
  opacity: 1;
}
</style>
