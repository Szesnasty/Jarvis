<template>
  <div class="main-page">
    <StatusBar />
    <main class="main-page__content">
      <Orb :state="orbState" />
      <ChatPanel
        :messages="messages"
        :current-response="currentResponse"
        :is-loading="isLoading"
        :tool-activity="toolActivity"
        @send="sendMessage"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import type { OrbState } from '~/types'

const { backendStatus, checkHealth } = useAppState()
const { messages, currentResponse, isLoading, toolActivity, init, sendMessage } = useChat()

const orbState = computed<OrbState>(() => {
  if (isLoading.value) return 'thinking'
  return 'idle'
})

onMounted(() => {
  checkHealth()
  init()
})
</script>

<style scoped>
.main-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main-page__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding-top: 2rem;
}
</style>
