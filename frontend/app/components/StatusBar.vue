<template>
  <header class="status-bar">
    <span class="status-bar__label">Jarvis</span>
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
