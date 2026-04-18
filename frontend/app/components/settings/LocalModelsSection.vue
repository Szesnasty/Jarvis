<template>
  <SettingsSection id="local-models" title="Local Models" :default-open="false">
    <p class="settings-page__hint">
      Run Jarvis locally — private on-device AI. Models are downloaded to your computer.
      <strong>No API key needed.</strong>
    </p>

    <!-- Runtime status card -->
    <div
      class="local-models__runtime-card"
      :class="localModels.isOllamaReady() ? 'local-models__runtime-card--ok' : 'local-models__runtime-card--missing'"
    >
      <span class="local-models__runtime-icon">{{ localModels.isOllamaReady() ? '✅' : '⚠️' }}</span>
      <div class="local-models__runtime-info">
        <span class="local-models__runtime-title">
          {{ localModels.isOllamaReady()
            ? `Ollama running${localModels.runtime.value?.version ? ' · v' + localModels.runtime.value.version : ''}`
            : 'Local runtime not detected' }}
        </span>
        <span v-if="!localModels.isOllamaReady()" class="local-models__runtime-hint">
          Install Ollama to use local models.
          <a :href="ollamaDownloadUrl" target="_blank" rel="noopener" class="settings-page__link">Download Ollama →</a>
        </span>
      </div>
      <button
        v-if="!localModels.isOllamaReady()"
        class="settings-page__btn settings-page__btn--sm"
        @click="localModels.refreshAll()"
      >
        Check Again
      </button>
    </div>

    <!-- Hardware summary card -->
    <div v-if="setupFlow.hardwareSummary.value" class="local-models__hw-card">
      <span class="local-models__hw-icon">🖥️</span>
      <div class="local-models__hw-info">
        <span class="local-models__hw-label">{{ setupFlow.hardwareSummary.value.label }}</span>
        <span class="local-models__hw-rec">{{ setupFlow.hardwareSummary.value.recommendation }}</span>
      </div>
    </div>

    <!-- Installed models -->
    <div v-if="installedLocalModels.length > 0" class="local-models__group">
      <h3 class="local-models__group-title">Installed models</h3>
      <div class="local-models__installed-list">
        <div
          v-for="m in installedLocalModels"
          :key="m.model_id"
          class="local-models__installed-row"
          :class="{ 'local-models__installed-row--active': m.active }"
        >
          <div class="local-models__installed-info">
            <span class="local-models__installed-name">{{ m.label }}</span>
            <span class="local-models__quality" :title="qualityDots(m.preset).label">
              <span
                v-for="i in qualityDots(m.preset).filled"
                :key="'f'+i"
                class="local-models__dot local-models__dot--filled"
                :style="{ '--dot-index': i }"
              />
              <span
                v-for="i in qualityDots(m.preset).empty"
                :key="'e'+i"
                class="local-models__dot local-models__dot--empty"
              />
            </span>
            <span v-if="m.active" class="local-models__installed-badge">Active</span>
            <span class="local-models__installed-meta">{{ m.download_size_gb }} GB · Context {{ m.context_window }}</span>
          </div>
          <div class="local-models__installed-actions">
            <button
              v-if="!m.active"
              class="settings-page__btn settings-page__btn--sm"
              @click="localModels.selectModel(m.model_id)"
            >Set active</button>
            <button
              class="settings-page__btn settings-page__btn--sm"
              @click="localModels.warmUpModel(m.ollama_model)"
            >Warm up</button>
            <button
              class="settings-page__btn settings-page__btn--sm settings-page__btn--danger"
              @click="handleDeleteModel(m)"
            >Remove</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Recommended models — max 3 -->
    <div v-if="localModels.recommendedModels.value.length > 0" class="local-models__group">
      <h3 class="local-models__group-title">Recommended for your hardware</h3>
      <div class="local-models__grid">
        <LocalModelCard
          v-for="m in localModels.recommendedModels.value.slice(0, 3)"
          :key="m.model_id"
          :model="m"
          :pulling="localModels.pulling.value === m.model_id"
          :progress="localModels.pulling.value === m.model_id ? localModels.pullProgress.value : null"
          :disabled="!localModels.isOllamaReady()"
          @pull="localModels.pullModel($event)"
          @select="localModels.selectModel($event)"
          @cancel="localModels.cancelPull()"
        />
      </div>
    </div>

    <!-- More models (collapsed) -->
    <details v-if="nonRecommendedModels.length > 0" class="local-models__all">
      <summary class="local-models__all-toggle">
        Show all local models ({{ nonRecommendedModels.length }})
      </summary>
      <div class="local-models__grid">
        <LocalModelCard
          v-for="m in nonRecommendedModels"
          :key="m.model_id"
          :model="m"
          :pulling="localModels.pulling.value === m.model_id"
          :progress="localModels.pulling.value === m.model_id ? localModels.pullProgress.value : null"
          :disabled="!localModels.isOllamaReady()"
          compact
          @pull="localModels.pullModel($event)"
          @select="localModels.selectModel($event)"
          @cancel="localModels.cancelPull()"
        />
      </div>
    </details>

    <!-- Advanced connection settings -->
    <details class="local-models__advanced">
      <summary class="local-models__all-toggle">Advanced connection settings</summary>
      <div class="local-models__url">
        <label class="local-models__url-label">Ollama URL</label>
        <div class="local-models__url-row">
          <input
            type="text"
            class="settings-page__input"
            :value="localModels.baseUrl.value"
            @change="localModels.setBaseUrl(($event.target as HTMLInputElement).value)"
            placeholder="http://localhost:11434"
          />
          <button class="settings-page__btn" @click="localModels.refreshAll()">
            Test Connection
          </button>
        </div>
      </div>
    </details>

    <p v-if="localModels.error.value" class="local-models__error">
      {{ localModels.error.value }}
    </p>
  </SettingsSection>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import SettingsSection from '~/components/settings/SettingsSection.vue'
import { qualityDots } from '~/composables/settings/useSharpen'

const localModels = useLocalModels()
const setupFlow = useLocalSetupFlow()

const ollamaDownloadUrl = computed(() => {
  const urls: Record<string, string> = {
    macos: 'https://ollama.com/download/mac',
    windows: 'https://ollama.com/download/windows',
    linux: 'https://ollama.com/download/linux',
  }
  return urls[setupFlow.detectedOS.value] ?? 'https://ollama.com/download'
})

const installedLocalModels = computed(() =>
  localModels.catalog.value.filter(m => m.installed),
)

const nonRecommendedModels = computed(() => {
  const recIds = new Set(localModels.recommendedModels.value.slice(0, 3).map(m => m.model_id))
  return localModels.catalog.value.filter(m => !m.installed && !recIds.has(m.model_id))
})

async function handleDeleteModel(model: { ollama_model: string }) {
  await localModels.deleteModel(model.ollama_model)
  await localModels.refreshAll()
}

onMounted(() => {
  localModels.refreshAll()
})
</script>
