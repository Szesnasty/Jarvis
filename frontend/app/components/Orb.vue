<template>
  <div class="orb-wrap">
    <svg class="orb-svg" viewBox="0 0 300 300">
      <!-- Outer tick ring -->
      <g class="orb-ticks" :class="state">
        <line
          v-for="i in 60"
          :key="'t'+i"
          :x1="150 + 130 * Math.cos((i * 6 - 90) * Math.PI / 180)"
          :y1="150 + 130 * Math.sin((i * 6 - 90) * Math.PI / 180)"
          :x2="150 + (i % 5 === 0 ? 118 : 123) * Math.cos((i * 6 - 90) * Math.PI / 180)"
          :y2="150 + (i % 5 === 0 ? 118 : 123) * Math.sin((i * 6 - 90) * Math.PI / 180)"
          :stroke-width="i % 5 === 0 ? 2 : 1"
        />
      </g>

      <!-- Outer arc 1 — slow clockwise -->
      <circle
        class="orb-arc orb-arc--1"
        :class="state"
        cx="150" cy="150" r="112"
        fill="none"
        stroke-width="2"
        stroke-linecap="round"
        stroke-dasharray="180 520"
      />

      <!-- Outer arc 2 — medium counter-clockwise -->
      <circle
        class="orb-arc orb-arc--2"
        :class="state"
        cx="150" cy="150" r="104"
        fill="none"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-dasharray="120 540"
      />

      <!-- Inner arc — fast -->
      <circle
        class="orb-arc orb-arc--3"
        :class="state"
        cx="150" cy="150" r="96"
        fill="none"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-dasharray="80 520"
      />

      <!-- Subtle halo ring -->
      <circle
        class="orb-halo"
        :class="state"
        cx="150" cy="150" r="88"
        fill="none"
        stroke-width="0.5"
      />

      <!-- Core glow -->
      <defs>
        <radialGradient id="coreGrad" cx="40%" cy="38%">
          <stop offset="0%" :stop-color="coreColors[0]" />
          <stop offset="60%" :stop-color="coreColors[1]" />
          <stop offset="100%" :stop-color="coreColors[2]" />
        </radialGradient>
        <radialGradient id="glowGrad">
          <stop offset="0%" :stop-color="glowColor" stop-opacity="0.35" />
          <stop offset="100%" stop-color="transparent" stop-opacity="0" />
        </radialGradient>
        <filter id="blur">
          <feGaussianBlur stdDeviation="14" />
        </filter>
        <filter id="coreBlur">
          <feGaussianBlur stdDeviation="8" />
        </filter>
      </defs>

      <!-- Ambient glow -->
      <circle class="orb-glow" :class="state" cx="150" cy="150" r="90" fill="url(#glowGrad)" filter="url(#blur)" />

      <!-- Secondary deep glow -->
      <circle class="orb-glow-deep" :class="state" cx="150" cy="150" r="70" fill="url(#glowGrad)" filter="url(#coreBlur)" />

      <!-- Core sphere -->
      <circle class="orb-core" :class="state" cx="150" cy="150" r="52" fill="url(#coreGrad)" />

      <!-- Specular highlight -->
      <ellipse cx="138" cy="132" rx="18" ry="12" fill="rgba(255,255,255,0.15)" />
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { OrbState } from '~/types'

const props = withDefaults(defineProps<{
  state?: OrbState
}>(), {
  state: 'idle',
})

const coreColors = computed(() => {
  switch (props.state) {
    case 'listening': return ['#b2fff9', '#02feff', '#015e5f']
    case 'thinking':  return ['#ffffff', '#67f5f7', '#027a7c']
    case 'speaking':  return ['#d0fcff', '#3ee8eb', '#0a4f51']
    default:          return ['#e0f7fa', '#cedce0', '#a8c8d0']
  }
})

const glowColor = computed(() => {
  switch (props.state) {
    case 'listening': return 'rgba(2, 254, 255, 1)'
    case 'thinking':  return 'rgba(103, 245, 247, 1)'
    case 'speaking':  return 'rgba(62, 232, 235, 1)'
    default:          return 'rgba(2, 254, 255, 1)'
  }
})
</script>

<style scoped>
.orb-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
}

.orb-svg {
  width: clamp(160px, 24vw, 260px);
  height: clamp(160px, 24vw, 260px);
  filter: drop-shadow(0 0 60px rgba(2, 254, 255, 0.3)) drop-shadow(0 0 120px rgba(2, 254, 255, 0.1));
}

/* --- Ticks --- */
.orb-ticks line {
  stroke: rgba(2, 254, 255, 0.7);
  transition: stroke 0.6s;
  filter: drop-shadow(0 0 2px rgba(2, 254, 255, 0.5));
}
.orb-ticks.listening line { stroke: rgba(2, 254, 255, 0.9); filter: drop-shadow(0 0 3px rgba(2, 254, 255, 0.6)); }
.orb-ticks.thinking line  { stroke: rgba(103, 245, 247, 0.9); filter: drop-shadow(0 0 3px rgba(103, 245, 247, 0.6)); }
.orb-ticks.speaking line  { stroke: rgba(62, 232, 235, 0.9); filter: drop-shadow(0 0 3px rgba(62, 232, 235, 0.6)); }

/* --- Arcs --- */
.orb-arc {
  stroke: rgba(2, 254, 255, 0.6);
  transition: stroke 0.6s;
  transform-origin: 150px 150px;
  filter: drop-shadow(0 0 4px rgba(2, 254, 255, 0.4));
}
.orb-arc--1 { animation: arc-spin 10s linear infinite; }
.orb-arc--2 { animation: arc-spin 7s linear infinite reverse; }
.orb-arc--3 { animation: arc-spin 5s linear infinite; }

/* Speed up on active states */
.orb-arc--1.listening, .orb-arc--1.thinking, .orb-arc--1.speaking { animation-duration: 4s; }
.orb-arc--2.listening, .orb-arc--2.thinking, .orb-arc--2.speaking { animation-duration: 3s; }
.orb-arc--3.listening, .orb-arc--3.thinking, .orb-arc--3.speaking { animation-duration: 2s; }

.orb-arc.listening { stroke: rgba(2, 254, 255, 0.8); filter: drop-shadow(0 0 6px rgba(2, 254, 255, 0.5)); }
.orb-arc.thinking  { stroke: rgba(103, 245, 247, 0.8); filter: drop-shadow(0 0 6px rgba(103, 245, 247, 0.5)); }
.orb-arc.speaking  { stroke: rgba(62, 232, 235, 0.8); filter: drop-shadow(0 0 6px rgba(62, 232, 235, 0.5)); }

/* --- Halo --- */
.orb-halo {
  stroke: rgba(2, 254, 255, 0.15);
  transition: stroke 0.6s;
}
.orb-halo.listening { stroke: rgba(2, 254, 255, 0.22); }
.orb-halo.thinking  { stroke: rgba(103, 245, 247, 0.22); }
.orb-halo.speaking  { stroke: rgba(62, 232, 235, 0.22); }

/* --- Glow pulse --- */
.orb-glow {
  animation: glow-pulse 3s ease-in-out infinite;
}
.orb-glow.listening { animation-duration: 1.2s; }
.orb-glow.thinking  { animation-duration: 0.8s; }
.orb-glow.speaking  { animation-duration: 1.5s; }

/* --- Core --- */
.orb-core {
  filter: drop-shadow(0 0 30px rgba(2, 254, 255, 0.5)) drop-shadow(0 0 60px rgba(2, 254, 255, 0.2));
  transition: filter 0.6s;
  animation: core-breathe 2.5s ease-in-out infinite;
}
.orb-core.listening { filter: drop-shadow(0 0 40px rgba(2, 254, 255, 0.7)) drop-shadow(0 0 80px rgba(2, 254, 255, 0.3)); }
.orb-core.thinking  { filter: drop-shadow(0 0 40px rgba(103, 245, 247, 0.7)) drop-shadow(0 0 80px rgba(103, 245, 247, 0.3)); }
.orb-core.speaking  { filter: drop-shadow(0 0 40px rgba(62, 232, 235, 0.7)) drop-shadow(0 0 80px rgba(62, 232, 235, 0.3)); }

@keyframes arc-spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}

.orb-glow-deep {
  animation: glow-pulse-deep 2s ease-in-out infinite;
}

@keyframes glow-pulse {
  0%, 100% { opacity: 0.5; transform: scale(1); }
  50%      { opacity: 1;   transform: scale(1.15); }
}

@keyframes glow-pulse-deep {
  0%, 100% { opacity: 0.3; transform: scale(0.95); }
  50%      { opacity: 0.8; transform: scale(1.1); }
}

@keyframes core-breathe {
  0%, 100% { opacity: 0.92; }
  50%      { opacity: 1; }
}
</style>
