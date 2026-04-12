<template>
  <div class="orb-container">
    <div class="orb" :class="state">
      <div class="orb__glow" />
      <div class="orb__core" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { OrbState } from '~/types'

withDefaults(defineProps<{
  state?: OrbState
}>(), {
  state: 'idle',
})
</script>

<style scoped>
.orb-container {
  display: flex;
  align-items: center;
  justify-content: center;
}

.orb {
  position: relative;
  width: 120px;
  height: 120px;
}

.orb__core {
  position: absolute;
  inset: 20%;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #6ab0f3, #2d5a8e);
}

.orb__glow {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(106, 176, 243, 0.3), transparent 70%);
  animation: pulse 3s ease-in-out infinite;
}

.orb.idle .orb__glow {
  animation: pulse 3s ease-in-out infinite;
}

.orb.listening .orb__glow {
  animation: pulse 1.5s ease-in-out infinite;
  background: radial-gradient(circle, rgba(34, 197, 94, 0.4), transparent 70%);
}

.orb.thinking .orb__glow {
  animation: pulse 0.8s ease-in-out infinite;
  background: radial-gradient(circle, rgba(234, 179, 8, 0.4), transparent 70%);
}

.orb.speaking .orb__glow {
  animation: pulse 1.2s ease-in-out infinite;
  background: radial-gradient(circle, rgba(168, 85, 247, 0.4), transparent 70%);
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.7;
  }
  50% {
    transform: scale(1.15);
    opacity: 1;
  }
}
</style>
