<template>
  <div class="onboarding">
    <div class="onboarding__card" :class="{ 'onboarding__card--wide': phase === 'local' }">
      <div class="onboarding__brand">
        <h1 class="onboarding__title">Jarvis</h1>
        <p class="onboarding__subtitle">An AI workspace that remembers what matters</p>
      </div>

      <!-- Phase: Choose -->
      <template v-if="phase === 'choose'">
        <p class="onboarding__prompt">How would you like to power Jarvis?</p>

        <div class="onboarding__choices">
          <button class="onboarding__choice" @click="phase = 'cloud'">
            <span class="onboarding__choice-icon">☁️</span>
            <span class="onboarding__choice-title">Use Cloud AI</span>
            <span class="onboarding__choice-desc">Anthropic, OpenAI, Google AI</span>
            <span class="onboarding__choice-detail">Needs API key</span>
          </button>

          <button class="onboarding__choice" @click="phase = 'local'">
            <span class="onboarding__choice-icon">🖥️</span>
            <span class="onboarding__choice-title">Run Locally</span>
            <span class="onboarding__choice-desc">Private, on-device AI</span>
            <span class="onboarding__choice-detail">Free &amp; offline · No API key</span>
          </button>
        </div>

        <p class="onboarding__hint">
          You can use both! Add cloud keys and local models anytime in Settings.
        </p>
      </template>

      <!-- Phase: Cloud (existing flow) -->
      <template v-if="phase === 'cloud'">
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

        <div class="onboarding__footer">
          <button class="onboarding__back" @click="phase = 'choose'">← Back to choices</button>
        </div>
      </template>

      <!-- Phase: Local -->
      <template v-if="phase === 'local'">
        <OnboardingLocalFlow
          @model-ready="handleSubmit"
          @back="phase = 'choose'"
        />
        <p v-if="error" class="onboarding__error">{{ error }}</p>
      </template>

      <p class="onboarding__settings-hint" v-if="phase !== 'choose'">
        You can add or change AI providers anytime in <strong>Settings</strong>.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ProviderConfig } from '~/types'

type OnboardingPhase = 'choose' | 'cloud' | 'local'

const phase = ref<OnboardingPhase>('choose')
const loading = ref(false)
const error = ref('')
const showAddKeyModal = ref(false)
const apiKeys = useApiKeys()
const addKeyProvider = ref<ProviderConfig>(apiKeys.providers[0]!)

const { isInitialized } = useAppState()

const canCreate = computed(() => {
  const hasCloudKey = apiKeys.hasAnyKey()
  return hasCloudKey || phase.value === 'local'
})

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
  } catch (e: unknown) {
    // Non-fatal: workspace may already exist (e.g. re-running onboarding)
    const msg = e && typeof e === 'object' && 'message' in e ? (e as Error).message : ''
    if (!msg.includes('already') && !msg.includes('exists')) {
      error.value = msg || 'Connection error. Is the backend running?'
      loading.value = false
      return
    }
  }
  isInitialized.value = true
  loading.value = false
  await navigateTo('/main', { replace: true })
}
</script>

<style scoped>
.onboarding {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem 1rem 4rem;
  overflow-y: auto;
}

.onboarding__card {
  background: var(--bg-surface, #111122);
  border: 1px solid var(--border-default, #222);
  border-radius: 10px;
  padding: 2rem 2.5rem 2.5rem;
  width: 100%;
  max-width: 520px;
  margin: auto 0;
  transition: max-width 0.3s ease;
}

.onboarding__card--wide {
  max-width: 640px;
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
  font-size: 0.9rem;
  color: var(--text-secondary, #aaa);
  margin-bottom: 1rem;
  text-align: center;
}

/* ---- Choose Phase ---- */
.onboarding__choices {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.85rem;
  margin-bottom: 1.25rem;
}

.onboarding__choice {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  padding: 1.5rem 1rem;
  background: var(--bg-base, #0a0a1a);
  border: 1px solid var(--border-default, #222);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.onboarding__choice:hover {
  border-color: var(--neon-cyan-30);
  background: var(--bg-elevated);
  box-shadow: 0 0 16px var(--neon-cyan-08);
}

.onboarding__choice-icon {
  font-size: 1.5rem;
  margin-bottom: 0.25rem;
}

.onboarding__choice-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

.onboarding__choice-desc {
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.onboarding__choice-detail {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin-top: 0.15rem;
}

.onboarding__hint {
  font-size: 0.78rem;
  color: var(--text-muted);
  text-align: center;
  margin-top: 0.5rem;
}

/* ---- Cloud Phase ---- */
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

.onboarding__footer {
  margin-top: 1.25rem;
}

.onboarding__back {
  padding: 0.35rem 0.75rem;
  background: transparent;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.15s;
}

.onboarding__back:hover {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
}

/* ---- Local Ready ---- */
.onboarding__ready {
  text-align: center;
  padding: 1rem 0;
}

.onboarding__ready-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

.onboarding__ready-title {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 0.35rem;
}

.onboarding__ready-desc {
  font-size: 0.88rem;
  color: var(--text-secondary);
  margin-bottom: 1.25rem;
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
