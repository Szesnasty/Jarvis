<script setup lang="ts">
definePageMeta({ layout: false })

const { isInitialized, checkWorkspaceStatus } = useAppState()

onMounted(async () => {
  await checkWorkspaceStatus()
  if (isInitialized.value) {
    await navigateTo('/main', { replace: true })
  } else {
    await navigateTo('/onboarding', { replace: true })
  }
})
</script>

<template>
  <div class="jarvis-init">
    <div class="jarvis-init__spinner" />
  </div>
</template>

<style scoped>
.jarvis-init {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: var(--bg-primary, #0a0a0a);
}

.jarvis-init__spinner {
  width: 32px;
  height: 32px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-top-color: rgba(255, 255, 255, 0.6);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
