<template>
  <div class="onboarding">
    <div class="onboarding__card">
      <div class="onboarding__brand">
        <h1 class="onboarding__title">Jarvis</h1>
        <p class="onboarding__subtitle">Personal Memory &amp; Planning System</p>
      </div>

      <KeyProtectionInfo title="Your keys stay in your browser" />

      <p class="onboarding__prompt">Add at least one AI provider to get started:</p>

      <div class="onboarding__providers">
        <ProviderCard
          v-for="p in apiKeys.providers"
          :key="p.id"
          :provider="p"
          :configured="apiKeys.isConfigured(p.id)"
          :masked-key="apiKeys.getMaskedKey(p.id)"
          :remembered="apiKeys.isRemembered(p.id)"
          :show-models="true"
          @add-key="openAddKey(p)"
          @remove-key="apiKeys.removeKey(p.id)"
        />
      </div>

      <AddKeyModal
        :provider="addKeyProvider"
        :show="showAddKeyModal"
        @close="showAddKeyModal = false"
        @saved="onKeySaved"
      />

      <button
        class="onboarding__button"
        :disabled="!canCreate || loading"
        :title="!canCreate ? 'Add at least one AI provider key' : ''"
        @click="handleSubmit"
      >
        {{ loading ? 'Creating...' : 'Create Jarvis Workspace' }}
      </button>

      <p v-if="error" class="onboarding__error">{{ error }}</p>

      <div class="onboarding__help">
        <p class="onboarding__help-title">Don't have a key yet?</p>
        <p class="onboarding__help-links">
          <template v-for="(p, i) in apiKeys.providers" :key="p.id">
            <span v-if="i > 0" class="onboarding__help-sep">·</span>
            <a :href="p.docsUrl" target="_blank" rel="noopener" class="onboarding__help-link">
              {{ p.name }} →
            </a>
          </template>
        </p>
      </div>

      <p class="onboarding__settings-hint">
        You can add or change API keys anytime in <strong>Settings</strong>.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ProviderConfig } from '~/types'

const loading = ref(false)
const error = ref('')
const showAddKeyModal = ref(false)
const apiKeys = useApiKeys()
const addKeyProvider = ref<ProviderConfig>(apiKeys.providers[0]!)

const { isInitialized } = useAppState()

const canCreate = computed(() => apiKeys.hasAnyKey())

function openAddKey(provider: ProviderConfig) {
  addKeyProvider.value = provider
  showAddKeyModal.value = true
}

function onKeySaved(_providerId: string) {
  // Key saved — button will auto-enable via canCreate
}

async function handleSubmit() {
  if (!canCreate.value) return
  error.value = ''
  loading.value = true
  const { initWorkspace } = useApi()
  try {
    await initWorkspace()
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
  background: var(--bg-surface, #111122);
  border: 1px solid var(--border-default, #222);
  border-radius: 10px;
  padding: 2.5rem;
  width: 100%;
  max-width: 520px;
}

.onboarding__brand {
  text-align: center;
  margin-bottom: 1.5rem;
}

.onboarding__title {
  font-size: 2rem;
  font-weight: 300;
  letter-spacing: 0.1em;
  margin-bottom: 0.25rem;
}

.onboarding__subtitle {
  color: var(--text-muted, #888);
  font-size: 0.875rem;
}

.onboarding__prompt {
  font-size: 0.85rem;
  color: var(--text-secondary, #aaa);
  margin-bottom: 0.75rem;
}

.onboarding__providers {
  border: 1px solid var(--border-subtle, #1a1a2e);
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 1.5rem;
}

.onboarding__button {
  display: block;
  width: 100%;
  padding: 0.7rem 1.25rem;
  background: var(--neon-cyan, #02feff);
  color: var(--bg-deep, #06080d);
  border: none;
  border-radius: 6px;
  font-weight: 700;
  font-size: 0.9rem;
  cursor: pointer;
  transition: all 0.2s;
  letter-spacing: 0.02em;
}

.onboarding__button:hover:not(:disabled) {
  box-shadow: 0 0 20px rgba(2, 254, 255, 0.25), 0 0 4px rgba(2, 254, 255, 0.4);
}

.onboarding__button:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.onboarding__error {
  color: #ef4444;
  font-size: 0.8125rem;
  margin-top: 0.75rem;
  text-align: center;
}

.onboarding__help {
  margin-top: 1.5rem;
  padding: 0.65rem 0.85rem;
  border-radius: 6px;
  background: rgba(2, 254, 255, 0.03);
  border: 1px solid var(--border-subtle, #1a1a2e);
}

.onboarding__help-title {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-secondary, #aaa);
  margin-bottom: 0.3rem;
}

.onboarding__help-links {
  font-size: 0.78rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex-wrap: wrap;
}

.onboarding__help-sep {
  color: var(--text-muted, #555);
}

.onboarding__help-link {
  color: var(--neon-cyan-60, #5bb8b9);
  text-decoration: none;
}

.onboarding__help-link:hover {
  color: var(--neon-cyan, #02feff);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.onboarding__settings-hint {
  font-size: 0.75rem;
  color: var(--text-muted, #666);
  text-align: center;
  margin-top: 1rem;
}

.onboarding__settings-hint strong {
  color: var(--neon-cyan-60, #5bb8b9);
}
</style>
