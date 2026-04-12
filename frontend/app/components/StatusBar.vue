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
      return 'Online'
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
  padding: 0.5rem 1rem;
  background-color: #111122;
  border-bottom: 1px solid #222;
}

.status-bar__label {
  font-weight: 600;
  font-size: 0.875rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.status-bar__nav {
  display: flex;
  gap: 1rem;
  flex: 1;
  justify-content: center;
}

.status-bar__link {
  color: #9ca3af;
  text-decoration: none;
  font-size: 0.85rem;
  padding: 0.25rem 0.5rem;
  border-radius: 6px;
  transition: color 0.15s, background-color 0.15s;
}

.status-bar__link:hover {
  color: #e5e7eb;
  background-color: rgba(255, 255, 255, 0.05);
}

.status-bar__link.router-link-active {
  color: #60a5fa;
  background-color: rgba(96, 165, 250, 0.1);
}

.status-bar__indicator {
  font-size: 0.75rem;
  padding: 0.125rem 0.5rem;
  border-radius: 9999px;
}

.status-bar__indicator.online {
  color: #22c55e;
  background-color: rgba(34, 197, 94, 0.1);
}

.status-bar__indicator.offline {
  color: #ef4444;
  background-color: rgba(239, 68, 68, 0.1);
}

.status-bar__indicator.unknown {
  color: #eab308;
  background-color: rgba(234, 179, 8, 0.1);
}
</style>
