<template>
  <div class="spec-badge" v-if="specialist" @click="$emit('click')">
    <span class="spec-badge__dot" />
    <span class="spec-badge__icon">{{ specialist.icon }}</span>
    <span class="spec-badge__name">{{ specialist.name }}</span>
    <button class="spec-badge__close" @click.stop="$emit('deactivate')" title="Deactivate specialist">
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="6" x2="6" y2="18"/>
        <line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
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
.spec-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.6rem 0.2rem 0.5rem;
  border-radius: 999px;
  background: var(--neon-cyan-08);
  border: 1px solid var(--neon-cyan-15);
  color: var(--neon-cyan);
  font-size: 0.78rem;
  cursor: pointer;
  transition: all 0.2s;
}

.spec-badge:hover {
  background: var(--neon-cyan-15);
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}

.spec-badge__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--neon-cyan);
  box-shadow: 0 0 4px var(--neon-cyan-60);
  animation: badge-pulse 2s ease-in-out infinite;
}

@keyframes badge-pulse {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

.spec-badge__icon {
  font-size: 0.85rem;
  line-height: 1;
}

.spec-badge__name {
  font-weight: 500;
  font-size: 0.75rem;
}

.spec-badge__close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: transparent;
  border: none;
  color: var(--neon-cyan-60);
  cursor: pointer;
  padding: 0;
  margin-left: 0.1rem;
  transition: all 0.15s;
}

.spec-badge__close:hover {
  background: rgba(239, 68, 68, 0.15);
  color: var(--neon-red);
}
</style>
