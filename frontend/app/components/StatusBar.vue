<template>
  <header class="status-bar">
    <span class="status-bar__label">Jarvis</span>
    <nav class="status-bar__nav">
      <NuxtLink to="/main" class="status-bar__link">Chat</NuxtLink>
      <NuxtLink to="/memory" class="status-bar__link">Memory</NuxtLink>
      <NuxtLink to="/graph" class="status-bar__link">Graph</NuxtLink>
      <NuxtLink to="/specialists" class="status-bar__link">Specialists</NuxtLink>
      <NuxtLink to="/settings" class="status-bar__link">Settings</NuxtLink>
    </nav>
    <span
      class="status-bar__indicator"
      :class="backendStatus"
    >
      {{ statusText }}
    </span>
  </header>
</template>

<script setup lang="ts">
const { backendStatus } = useAppState()

const statusText = computed(() => {
  switch (backendStatus.value) {
    case 'online':
      return 'Alive'
    case 'offline':
      return 'Offline'
    default:
      return 'Checking...'
  }
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
}

.status-bar__label {
  font-weight: 700;
  font-size: 0.9rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--neon-cyan);
  text-shadow: 0 0 10px var(--neon-cyan-30);
}

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
</style>
