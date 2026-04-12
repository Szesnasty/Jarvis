<template>
  <div class="orb-container">
    <div class="orb" :class="state">
      <div class="orb__ring orb__ring--outer" />
      <div class="orb__ring orb__ring--inner" />
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
  width: clamp(80px, 15vw, 140px);
  height: clamp(80px, 15vw, 140px);
  transition: filter 0.6s ease;
}

.orb__core {
  position: absolute;
  inset: 25%;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #8ec5fc, #4a90d9 50%, #2d5a8e);
  box-shadow: 0 0 20px rgba(106, 176, 243, 0.4), inset 0 -3px 6px rgba(0, 0, 0, 0.2);
  transition: box-shadow 0.6s ease, background 0.6s ease;
}

.orb__glow {
  position: absolute;
  inset: 5%;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(106, 176, 243, 0.25), transparent 70%);
  animation: pulse 3s ease-in-out infinite;
  transition: background 0.6s ease;
}

.orb__ring--outer {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1px solid rgba(106, 176, 243, 0.15);
  animation: ring-rotate 12s linear infinite;
}

.orb__ring--inner {
  position: absolute;
  inset: 10%;
  border-radius: 50%;
  border: 1px solid rgba(106, 176, 243, 0.1);
  animation: ring-rotate 8s linear infinite reverse;
}

/* --- Idle --- */
.orb.idle .orb__glow {
  animation: pulse 3s ease-in-out infinite;
}

/* --- Listening --- */
.orb.listening .orb__core {
  background: radial-gradient(circle at 35% 35%, #86efac, #22c55e 50%, #166534);
  box-shadow: 0 0 30px rgba(34, 197, 94, 0.5), inset 0 -3px 6px rgba(0, 0, 0, 0.2);
}
.orb.listening .orb__glow {
  background: radial-gradient(circle, rgba(34, 197, 94, 0.35), transparent 70%);
  animation: pulse 1.2s ease-in-out infinite;
}
.orb.listening .orb__ring--outer {
  border-color: rgba(34, 197, 94, 0.25);
  animation-duration: 4s;
}
.orb.listening .orb__ring--inner {
  border-color: rgba(34, 197, 94, 0.15);
}

/* --- Thinking --- */
.orb.thinking .orb__core {
  background: radial-gradient(circle at 35% 35%, #fde68a, #eab308 50%, #92400e);
  box-shadow: 0 0 30px rgba(234, 179, 8, 0.5), inset 0 -3px 6px rgba(0, 0, 0, 0.2);
}
.orb.thinking .orb__glow {
  background: radial-gradient(circle, rgba(234, 179, 8, 0.35), transparent 70%);
  animation: pulse 0.7s ease-in-out infinite;
}
.orb.thinking .orb__ring--outer {
  border-color: rgba(234, 179, 8, 0.25);
  animation-duration: 2s;
}
.orb.thinking .orb__ring--inner {
  border-color: rgba(234, 179, 8, 0.15);
  animation-duration: 3s;
}

/* --- Speaking --- */
.orb.speaking .orb__core {
  background: radial-gradient(circle at 35% 35%, #c4b5fd, #8b5cf6 50%, #5b21b6);
  box-shadow: 0 0 30px rgba(168, 85, 247, 0.5), inset 0 -3px 6px rgba(0, 0, 0, 0.2);
}
.orb.speaking .orb__glow {
  background: radial-gradient(circle, rgba(168, 85, 247, 0.35), transparent 70%);
  animation: pulse 1s ease-in-out infinite;
}
.orb.speaking .orb__ring--outer {
  border-color: rgba(168, 85, 247, 0.25);
  animation-duration: 6s;
}
.orb.speaking .orb__ring--inner {
  border-color: rgba(168, 85, 247, 0.15);
}

@keyframes pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.7;
  }
  50% {
    transform: scale(1.12);
    opacity: 1;
  }
}

@keyframes ring-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
