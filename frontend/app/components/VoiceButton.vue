<script setup lang="ts">
import type { OrbState } from '~/types'

const props = defineProps<{
  state: OrbState
  supported: boolean
}>()

const emit = defineEmits<{
  toggle: []
}>()

const label = computed(() => {
  if (!props.supported) return 'Voice not supported'
  if (props.state === 'listening') return 'Stop listening'
  if (props.state === 'speaking') return 'Stop speaking'
  return 'Start voice input'
})
</script>

<template>
  <button
    class="voice-button"
    :class="state"
    :disabled="!supported"
    :aria-label="label"
    :title="!supported ? 'Voice not supported in this browser' : undefined"
    @click="emit('toggle')"
  >
    <span v-if="state === 'listening'" class="voice-button__icon voice-button__icon--stop">⏹</span>
    <span v-else class="voice-button__icon voice-button__icon--mic">🎤</span>
  </button>
</template>

<style scoped>
.voice-button {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  flex-shrink: 0;
}

.voice-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.voice-button.listening {
  border-color: rgba(239, 68, 68, 0.5);
  box-shadow: 0 0 15px rgba(239, 68, 68, 0.15);
  animation: pulse-ring 1.2s ease-in-out infinite;
}

.voice-button.thinking {
  border-color: var(--neon-yellow);
}

.voice-button.speaking {
  border-color: var(--neon-cyan-30);
}

.voice-button__icon {
  font-size: 1.25rem;
}

@keyframes pulse-ring {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
  50% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }
}
</style>
