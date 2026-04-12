<template>
  <div class="main-page">
    <StatusBar />
    <main class="main-page__content">
      <Orb state="idle" />
      <h1 class="main-page__title">Jarvis</h1>
      <p class="main-page__status">
        Backend: {{ backendStatus }}
      </p>
    </main>
    <footer class="main-page__footer">
      <input
        type="text"
        class="main-page__input"
        placeholder="Talk to Jarvis..."
        disabled
      />
    </footer>
  </div>
</template>

<script setup lang="ts">
const { backendStatus, checkHealth } = useAppState()

onMounted(() => {
  checkHealth()
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
  justify-content: center;
  gap: 0.5rem;
}

.main-page__title {
  font-size: 2.5rem;
  font-weight: 300;
  letter-spacing: 0.1em;
}

.main-page__status {
  font-size: 0.875rem;
  color: #888;
}

.main-page__footer {
  padding: 1rem;
  border-top: 1px solid #222;
}

.main-page__input {
  width: 100%;
}

.main-page__input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
