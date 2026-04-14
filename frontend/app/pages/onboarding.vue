<template>
  <div class="onboarding">
    <div class="onboarding__card">
      <h1 class="onboarding__title">Jarvis</h1>
      <p class="onboarding__subtitle">Personal Memory &amp; Planning System</p>

      <form class="onboarding__form" @submit.prevent="handleSubmit">
        <label class="onboarding__label" for="api-key">Anthropic API Key</label>
        <input
          id="api-key"
          v-model="apiKey"
          type="password"
          class="onboarding__input"
          placeholder="sk-ant-..."
          autocomplete="off"
        />

        <button
          type="submit"
          class="onboarding__button"
          :disabled="!apiKey.trim() || loading"
        >
          {{ loading ? 'Creating...' : 'Create Jarvis Workspace' }}
        </button>

        <p v-if="error" class="onboarding__error">{{ error }}</p>
      </form>

      <p class="onboarding__hint">
        You can add or change API keys anytime in <strong>Settings</strong>.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
const apiKey = ref('')
const loading = ref(false)
const error = ref('')

const { isInitialized } = useAppState()

async function handleSubmit() {
  error.value = ''
  loading.value = true
  const { initWorkspace } = useApi()
  try {
    await initWorkspace(apiKey.value)
    isInitialized.value = true
    await navigateTo('/main', { replace: true })
  } catch (e: unknown) {
    if (e && typeof e === 'object' && 'message' in e) {
      error.value = (e as Error).message
    } else {
      error.value = 'Connection error. Is the backend running?'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.onboarding {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 1rem;
}

.onboarding__card {
  background: #111122;
  border: 1px solid #222;
  border-radius: 8px;
  padding: 2.5rem;
  width: 100%;
  max-width: 420px;
  text-align: center;
}

.onboarding__title {
  font-size: 2rem;
  font-weight: 300;
  letter-spacing: 0.1em;
  margin-bottom: 0.25rem;
}

.onboarding__subtitle {
  color: #888;
  font-size: 0.875rem;
  margin-bottom: 2rem;
}

.onboarding__form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.onboarding__label {
  text-align: left;
  font-size: 0.875rem;
  color: #aaa;
}

.onboarding__input {
  width: 100%;
}

.onboarding__button {
  margin-top: 0.5rem;
  padding: 0.625rem 1.25rem;
  background: #6ab0f3;
  color: #0a0a0f;
  border: none;
  border-radius: 4px;
  font-weight: 600;
  cursor: pointer;
  font-size: 0.875rem;
}

.onboarding__button:hover:not(:disabled) {
  background: #8ac4f8;
}

.onboarding__button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.onboarding__error {
  color: #ef4444;
  font-size: 0.8125rem;
  margin-top: 0.25rem;
}

.onboarding__hint {
  font-size: 0.78rem;
  color: #666;
  margin-top: 1.5rem;
}

.onboarding__hint strong {
  color: #6ab0f3;
}
</style>
