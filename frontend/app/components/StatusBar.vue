<template>
  <header class="status-bar">
    <span class="status-bar__label" :class="{ 'status-bar__label--hidden': chatActive }">Jarvis</span>

    <nav class="status-bar__nav" :class="{ 'status-bar__nav--open': menuOpen }">
      <NuxtLink to="/main" class="status-bar__link" @click="menuOpen = false">Chat</NuxtLink>
      <NuxtLink to="/memory" class="status-bar__link" @click="menuOpen = false">Memory</NuxtLink>
      <NuxtLink to="/graph" class="status-bar__link" @click="menuOpen = false">Graph</NuxtLink>
      <NuxtLink to="/specialists" class="status-bar__link" @click="menuOpen = false">Specialists</NuxtLink>
      <NuxtLink to="/settings" class="status-bar__link" @click="menuOpen = false">Settings</NuxtLink>
    </nav>

    <!-- Backdrop to close menu when tapping outside -->
    <div
      v-if="menuOpen"
      class="status-bar__backdrop"
      @click="menuOpen = false"
    />

    <span
      class="status-bar__indicator"
      :class="backendStatus"
    >
      {{ statusText }}
    </span>

    <button
      class="status-bar__hamburger"
      :class="{ 'status-bar__hamburger--open': menuOpen }"
      aria-label="Toggle navigation"
      @click="menuOpen = !menuOpen"
    >
      <span class="status-bar__hamburger-line" />
      <span class="status-bar__hamburger-line" />
      <span class="status-bar__hamburger-line" />
    </button>
  </header>
</template>

<script setup lang="ts">
import { useLocalModels } from '~/composables/useLocalModels'
import { useApiKeys } from '~/composables/useApiKeys'

const { backendStatus, chatActive } = useAppState()
const menuOpen = ref(false)
const { activeProvider } = useApiKeys()
const localModels = useLocalModels()

const route = useRoute()
watch(() => route.path, () => {
  menuOpen.value = false
})

const statusText = computed(() => {
  const base = backendStatus.value === 'online' ? 'Alive' : backendStatus.value === 'offline' ? 'Offline' : 'Checking...'
  if (activeProvider.value === 'ollama' && localModels.activeModel.value) {
    const modelName = localModels.activeModel.value.label
    const ollamaOk = localModels.runtime.value?.reachable && !localModels.ollamaDown.value
    return `${base} · ${modelName} (local) · ${ollamaOk ? '🟢' : '🔴'}`
  }
  return base
})
</script>

<style scoped>
.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 1.25rem;
  background-color: var(--bg-base);
  border-bottom: 1px solid var(--border-default);
  backdrop-filter: blur(12px);
  position: relative;
  z-index: 100;
}

.status-bar__label {
  font-weight: 700;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--neon-cyan);
  text-shadow: 0 0 10px var(--neon-cyan-30);
  transition: opacity 0.5s ease, transform 0.5s ease;
  min-width: 56px;
}

.status-bar__label--hidden {
  opacity: 0;
  pointer-events: none;
}

/* ── Hamburger button ── */
.status-bar__hamburger {
  display: none;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  width: 32px;
  height: 32px;
  padding: 4px;
  background: none;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
}

.status-bar__hamburger:hover {
  border-color: var(--border-subtle);
  background-color: var(--neon-cyan-08);
}

.status-bar__hamburger-line {
  display: block;
  width: 100%;
  height: 2px;
  background-color: var(--text-secondary);
  border-radius: 1px;
  transition: transform 0.3s ease, opacity 0.3s ease, background-color 0.2s;
}

.status-bar__hamburger:hover .status-bar__hamburger-line {
  background-color: var(--neon-cyan);
}

/* Hamburger → X animation */
.status-bar__hamburger--open .status-bar__hamburger-line:nth-child(1) {
  transform: translateY(6px) rotate(45deg);
  background-color: var(--neon-cyan);
}

.status-bar__hamburger--open .status-bar__hamburger-line:nth-child(2) {
  opacity: 0;
}

.status-bar__hamburger--open .status-bar__hamburger-line:nth-child(3) {
  transform: translateY(-6px) rotate(-45deg);
  background-color: var(--neon-cyan);
}

/* ── Navigation ── */
.status-bar__nav {
  display: flex;
  gap: 0.25rem;
  flex: 1;
  justify-content: center;
}

.status-bar__link {
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.85rem;
  padding: 0.3rem 0.75rem;
  border-radius: 6px;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.status-bar__link:hover {
  color: var(--text-primary);
  background-color: var(--neon-cyan-08);
  border-color: var(--border-subtle);
  text-shadow: 0 0 6px var(--neon-cyan-15);
}

.status-bar__link.router-link-active {
  color: var(--neon-cyan);
  background-color: var(--neon-cyan-08);
  border-color: var(--neon-cyan-30);
  text-shadow: 0 0 8px var(--neon-cyan-30);
  box-shadow: 0 0 12px var(--neon-cyan-08);
}

/* ── Status indicator ── */
.status-bar__indicator {
  font-size: 0.75rem;
  padding: 0.15rem 0.6rem;
  border-radius: 9999px;
  border: 1px solid transparent;
}

.status-bar__indicator.online {
  color: var(--neon-green);
  background-color: rgba(34, 197, 94, 0.08);
  border-color: rgba(34, 197, 94, 0.2);
  text-shadow: 0 0 6px rgba(34, 197, 94, 0.3);
}

.status-bar__indicator.offline {
  color: var(--neon-red);
  background-color: rgba(239, 68, 68, 0.08);
  border-color: rgba(239, 68, 68, 0.2);
}

.status-bar__indicator.unknown {
  color: var(--neon-yellow);
  background-color: rgba(234, 179, 8, 0.08);
  border-color: rgba(234, 179, 8, 0.2);
}

/* ── Backdrop (mobile only) ── */
.status-bar__backdrop {
  display: none;
}

/* ═══════════════════════════════════════════════
   Responsive — collapse nav below 640px
   ═══════════════════════════════════════════════ */
@media (max-width: 640px) {
  .status-bar__hamburger {
    display: flex;
  }

  .status-bar__nav {
    /* Off-canvas dropdown */
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    flex-direction: column;
    gap: 0;
    background-color: var(--bg-base);
    border-bottom: 1px solid var(--border-default);
    padding: 0;
    max-height: 0;
    overflow: hidden;
    opacity: 0;
    transition: max-height 0.35s cubic-bezier(0.4, 0, 0.2, 1),
                opacity 0.25s ease,
                padding 0.3s ease;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    z-index: 200;
  }

  .status-bar__nav--open {
    max-height: 320px;
    opacity: 1;
    padding: 0.5rem 0;
  }

  .status-bar__link {
    padding: 0.65rem 1.25rem;
    border-radius: 0;
    font-size: 0.9rem;
    border: none;
    border-left: 2px solid transparent;
    transition: all 0.15s ease;
  }

  .status-bar__link:hover {
    border-radius: 0;
    border-color: transparent;
    border-left-color: var(--neon-cyan-30);
    background-color: var(--neon-cyan-08);
  }

  .status-bar__link.router-link-active {
    border-radius: 0;
    border-color: transparent;
    border-left-color: var(--neon-cyan);
    background-color: var(--neon-cyan-08);
    box-shadow: none;
  }

  .status-bar__backdrop {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 99;
    background: rgba(0, 0, 0, 0.4);
  }
}
</style>
