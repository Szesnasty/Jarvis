<template>
  <div class="settings-page">
    <h1 class="settings-page__title">Settings</h1>

    <!-- API Key -->
    <section class="settings-page__section">
      <h2 class="settings-page__section-title">API Key</h2>
      <div class="settings-page__field">
        <span class="settings-page__masked-key">{{ apiKeySet ? '••••••••' : 'Not set' }}</span>
        <input
          v-model="newApiKey"
          type="password"
          class="settings-page__input"
          placeholder="Enter new API key"
        />
        <button class="settings-page__btn" @click="updateApiKey">Update Key</button>
      </div>
    </section>

    <!-- Workspace -->
    <section class="settings-page__section">
      <h2 class="settings-page__section-title">Workspace</h2>
      <p class="settings-page__path">{{ workspacePath }}</p>
    </section>

    <!-- Voice -->
    <section class="settings-page__section">
      <h2 class="settings-page__section-title">Voice Settings</h2>
      <label class="settings-page__toggle">
        <input type="checkbox" v-model="autoSpeak" @change="updateVoicePrefs" />
        Auto-speak responses
      </label>
    </section>

    <!-- Actions -->
    <section class="settings-page__section">
      <h2 class="settings-page__section-title">Maintenance</h2>
      <div class="settings-page__actions">
        <button class="settings-page__btn" @click="reindexMemory">Reindex Memory</button>
        <button class="settings-page__btn" @click="rebuildGraphAction">Rebuild Graph</button>
      </div>
    </section>

    <!-- Token Usage -->
    <section class="settings-page__section">
      <h2 class="settings-page__section-title">Token Usage</h2>
      <div class="settings-page__usage" v-if="usage">
        <p>Total tokens: {{ usage.total }}</p>
        <p>Requests: {{ usage.request_count }}</p>
        <p>Est. cost: ${{ usage.cost_estimate }}</p>
      </div>
    </section>

    <!-- Obsidian -->
    <ObsidianHelper />

    <!-- Status -->
    <p v-if="statusMsg" class="settings-page__status">{{ statusMsg }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const apiKeySet = ref(false)
const workspacePath = ref('')
const newApiKey = ref('')
const autoSpeak = ref(false)
const usage = ref<{ total: number; request_count: number; cost_estimate: number } | null>(null)
const statusMsg = ref('')

onMounted(async () => {
  try {
    const resp = await $fetch<{
      workspace_path: string
      api_key_set: boolean
      voice: { auto_speak: string; tts_voice: string }
    }>('/api/settings')
    workspacePath.value = resp.workspace_path
    apiKeySet.value = resp.api_key_set
    autoSpeak.value = resp.voice.auto_speak === 'true'
  } catch { /* ignore */ }

  try {
    usage.value = await $fetch('/api/settings/usage')
  } catch { /* ignore */ }
})

async function updateApiKey() {
  if (!newApiKey.value.trim()) return
  try {
    await $fetch('/api/settings/api-key', { method: 'PATCH', body: { api_key: newApiKey.value } })
    apiKeySet.value = true
    newApiKey.value = ''
    statusMsg.value = 'API key updated'
  } catch {
    statusMsg.value = 'Failed to update API key'
  }
}

async function updateVoicePrefs() {
  try {
    await $fetch('/api/settings/voice', { method: 'PATCH', body: { auto_speak: String(autoSpeak.value) } })
  } catch { /* ignore */ }
}

async function reindexMemory() {
  try {
    const resp = await $fetch<{ indexed: number }>('/api/memory/reindex', { method: 'POST' })
    statusMsg.value = `Reindexed ${resp.indexed} notes`
  } catch {
    statusMsg.value = 'Reindex failed'
  }
}

async function rebuildGraphAction() {
  try {
    await $fetch('/api/graph/rebuild', { method: 'POST' })
    statusMsg.value = 'Graph rebuilt'
  } catch {
    statusMsg.value = 'Rebuild failed'
  }
}
</script>

<style scoped>
.settings-page {
  max-width: 700px;
  margin: 0 auto;
  padding: 2rem;
  height: calc(100vh - 40px);
  overflow-y: auto;
}
.settings-page__title {
  font-size: 1.5rem;
  margin-bottom: 1.5rem;
}
.settings-page__section {
  margin-bottom: 1.5rem;
  padding: 1rem;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
}
.settings-page__section-title {
  font-size: 1rem;
  margin-bottom: 0.75rem;
}
.settings-page__field {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.settings-page__masked-key {
  font-family: monospace;
  opacity: 0.6;
}
.settings-page__input {
  padding: 0.4rem 0.75rem;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  background: var(--bg-base);
  color: inherit;
  flex: 1;
  min-width: 200px;
}
.settings-page__input:focus {
  outline: none;
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}
.settings-page__btn {
  padding: 0.4rem 1rem;
  border: 1px solid var(--neon-cyan-30);
  border-radius: 4px;
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
  cursor: pointer;
  transition: all 0.2s;
}
.settings-page__btn:hover {
  background: rgba(2, 254, 255, 0.15);
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 12px var(--neon-cyan-08);
  text-shadow: 0 0 6px var(--neon-cyan-30);
}
.settings-page__path {
  font-family: monospace;
  font-size: 0.85rem;
  opacity: 0.7;
}
.settings-page__toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}
.settings-page__actions {
  display: flex;
  gap: 0.75rem;
}
.settings-page__usage p {
  margin: 0.2rem 0;
  font-size: 0.9rem;
}
.settings-page__status {
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  background: var(--neon-cyan-08);
  border: 1px solid var(--neon-cyan-30);
  border-radius: 4px;
  font-size: 0.9rem;
  color: var(--neon-cyan);
}
</style>
