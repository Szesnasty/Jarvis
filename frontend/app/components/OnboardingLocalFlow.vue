<script setup lang="ts">
const emit = defineEmits<{
  (e: 'model-ready'): void
  (e: 'back'): void
}>()

const localModels = useLocalModels()
const showAll = ref(false)

onMounted(() => {
  localModels.refreshAll()
})

async function handlePull(modelId: string) {
  await localModels.pullModel(modelId)
  // After pull, auto-select the model
  const model = localModels.catalog.value.find(m => m.model_id === modelId)
  if (model?.installed) {
    await localModels.selectModel(modelId)
    emit('model-ready')
  }
}

async function handleSelect(modelId: string) {
  await localModels.selectModel(modelId)
  emit('model-ready')
}

const displayModels = computed(() => {
  if (showAll.value) return localModels.catalog.value
  return localModels.recommendedModels.value.slice(0, 3)
})

const isPulling = computed(() => !!localModels.pulling.value)
</script>

<template>
  <div class="local-flow">
    <h2 class="local-flow__title">Local AI Setup</h2>

    <!-- Loading state -->
    <div v-if="localModels.loading.value" class="local-flow__loading">
      Detecting your hardware...
    </div>

    <template v-else>
      <!-- Ollama Status -->
      <OllamaStatus
        :runtime="localModels.runtime.value"
        :hardware="localModels.hardware.value"
        :loading="localModels.loading.value"
        @refresh="localModels.refreshAll()"
      />

      <!-- Model recommendations (only when Ollama is running) -->
      <template v-if="localModels.isOllamaReady()">
        <!-- Currently pulling -->
        <div v-if="isPulling" class="local-flow__pulling">
          <p class="local-flow__pulling-hint">
            This may take a few minutes depending on your internet connection.
          </p>
        </div>

        <!-- Model list -->
        <div v-if="!isPulling" class="local-flow__models">
          <p class="local-flow__models-title">
            Recommended for your computer:
          </p>

          <div class="local-flow__model-list">
            <LocalModelCard
              v-for="m in displayModels"
              :key="m.model_id"
              :model="m"
              :pulling="localModels.pulling.value === m.model_id"
              :progress="localModels.pulling.value === m.model_id ? localModels.pullProgress.value : null"
              @pull="handlePull"
              @select="handleSelect"
            />
          </div>

          <button
            v-if="!showAll && localModels.catalog.value.length > 3"
            class="local-flow__show-all"
            @click="showAll = true"
          >
            Show all models ({{ localModels.catalog.value.length }})
          </button>
        </div>
      </template>

      <!-- Error -->
      <p v-if="localModels.error.value" class="local-flow__error">
        {{ localModels.error.value }}
      </p>
    </template>

    <div class="local-flow__footer">
      <button class="local-flow__back" @click="emit('back')">
        ← Back to choices
      </button>
    </div>
  </div>
</template>

<style scoped>
.local-flow {
  width: 100%;
}

.local-flow__title {
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 1rem;
  text-align: center;
  color: var(--text-primary);
}

.local-flow__loading {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted);
  font-size: 0.88rem;
}

.local-flow__pulling {
  margin-top: 1rem;
}

.local-flow__pulling-hint {
  font-size: 0.82rem;
  color: var(--text-muted);
  text-align: center;
  margin-top: 0.5rem;
}

.local-flow__models {
  margin-top: 1.25rem;
}

.local-flow__models-title {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-bottom: 0.75rem;
}

.local-flow__model-list {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.local-flow__show-all {
  display: block;
  width: 100%;
  margin-top: 0.65rem;
  padding: 0.45rem;
  background: transparent;
  border: 1px dashed var(--border-default);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.15s;
}

.local-flow__show-all:hover {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
}

.local-flow__error {
  margin-top: 0.65rem;
  font-size: 0.8rem;
  color: rgba(248, 113, 113, 0.9);
  background: rgba(248, 113, 113, 0.06);
  border: 1px solid rgba(248, 113, 113, 0.2);
  border-radius: 6px;
  padding: 0.45rem 0.7rem;
}

.local-flow__footer {
  margin-top: 1.5rem;
  display: flex;
  justify-content: flex-start;
}

.local-flow__back {
  padding: 0.35rem 0.75rem;
  background: transparent;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 0.82rem;
  cursor: pointer;
  transition: all 0.15s;
}

.local-flow__back:hover {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
}
</style>
