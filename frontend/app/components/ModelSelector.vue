<script setup lang="ts">
import { useApiKeys, MODEL_CATALOG, type ModelInfo } from '~/composables/useApiKeys'

const { activeProvider, activeModel, selectModel, configuredProviders, providers } = useApiKeys()

const isOpen = ref(false)
const selectorRef = ref<HTMLElement | null>(null)

const currentModelInfo = computed<ModelInfo | undefined>(() => {
  const catalog = MODEL_CATALOG[activeProvider.value]
  return catalog?.find(m => m.id === activeModel.value)
})

const currentProviderConfig = computed(() =>
  providers.find(p => p.id === activeProvider.value),
)

const availableProviders = computed(() => configuredProviders())

function handleSelect(providerId: string, modelId: string): void {
  selectModel(providerId, modelId)
  isOpen.value = false
}

function costBadge(cost: 1 | 2 | 3): string {
  if (cost === 1) return '$'
  if (cost === 2) return '$$'
  return '$$$'
}

function costClass(cost: 1 | 2 | 3): string {
  if (cost === 1) return 'model-selector__cost--budget'
  if (cost === 2) return 'model-selector__cost--standard'
  return 'model-selector__cost--premium'
}

// Close on outside click
function handleClickOutside(e: MouseEvent): void {
  if (selectorRef.value && !selectorRef.value.contains(e.target as Node)) {
    isOpen.value = false
  }
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))
</script>

<template>
  <div ref="selectorRef" class="model-selector" :class="{ 'model-selector--open': isOpen }">
    <button
      class="model-selector__trigger"
      :title="currentModelInfo?.label ?? activeModel"
      @click.stop="isOpen = !isOpen"
    >
      <span class="model-selector__trigger-icon" v-html="currentProviderConfig?.icon ?? ''" />
      <span class="model-selector__trigger-label">{{ currentModelInfo?.label ?? activeModel }}</span>
      <svg class="model-selector__chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="6 9 12 15 18 9" />
      </svg>
    </button>

    <Transition name="dropdown">
      <div v-if="isOpen" class="model-selector__dropdown">
        <template v-for="provider in availableProviders" :key="provider.id">
          <div class="model-selector__group-header">
            <span class="model-selector__group-icon" v-html="provider.icon" />
            <span>{{ provider.name }}</span>
          </div>
          <button
            v-for="model in MODEL_CATALOG[provider.id]"
            :key="model.id"
            class="model-selector__option"
            :class="{ 'model-selector__option--active': activeModel === model.id && activeProvider === provider.id }"
            @click="handleSelect(provider.id, model.id)"
          >
            <span class="model-selector__option-label">{{ model.label }}</span>
            <span class="model-selector__cost" :class="costClass(model.cost)">{{ costBadge(model.cost) }}</span>
            <svg
              v-if="activeModel === model.id && activeProvider === provider.id"
              class="model-selector__check"
              width="14" height="14" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
            >
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </button>
        </template>

        <div v-if="availableProviders.length === 0" class="model-selector__empty">
          No API keys configured
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.model-selector {
  position: relative;
}

.model-selector__trigger {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.6rem;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.8rem;
  height: 36px;
  transition: all 0.2s;
  white-space: nowrap;
  max-width: 180px;
}

.model-selector__trigger:hover {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
  background: var(--bg-elevated);
}

.model-selector--open .model-selector__trigger {
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 0 2px var(--neon-cyan-08);
}

.model-selector__trigger-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.model-selector__trigger-icon :deep(svg) {
  width: 14px;
  height: 14px;
}

.model-selector__trigger-label {
  overflow: hidden;
  text-overflow: ellipsis;
}

.model-selector__chevron {
  flex-shrink: 0;
  transition: transform 0.2s;
  opacity: 0.6;
}

.model-selector--open .model-selector__chevron {
  transform: rotate(180deg);
}

.model-selector__dropdown {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  min-width: 220px;
  max-width: 280px;
  max-height: 360px;
  overflow-y: auto;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: 10px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4), 0 0 1px rgba(2, 254, 255, 0.1);
  padding: 0.35rem 0;
  z-index: 100;
}

.model-selector__group-header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.75rem 0.25rem;
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.model-selector__group-header:not(:first-child) {
  border-top: 1px solid var(--border-subtle);
  margin-top: 0.25rem;
  padding-top: 0.55rem;
}

.model-selector__group-icon {
  width: 14px;
  height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.7;
}

.model-selector__group-icon :deep(svg) {
  width: 12px;
  height: 12px;
}

.model-selector__option {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  width: 100%;
  padding: 0.4rem 0.75rem 0.4rem 1.7rem;
  border: none;
  background: none;
  color: var(--text-primary);
  font-size: 0.82rem;
  cursor: pointer;
  transition: background 0.15s;
  text-align: left;
}

.model-selector__option:hover {
  background: var(--neon-cyan-08);
}

.model-selector__option--active {
  color: var(--neon-cyan);
}

.model-selector__option-label {
  flex: 1;
}

.model-selector__cost {
  font-size: 0.68rem;
  font-weight: 600;
  padding: 0.1rem 0.3rem;
  border-radius: 4px;
  line-height: 1;
}

.model-selector__cost--budget {
  color: rgba(74, 222, 128, 0.9);
  background: rgba(74, 222, 128, 0.1);
}

.model-selector__cost--standard {
  color: rgba(251, 191, 36, 0.9);
  background: rgba(251, 191, 36, 0.1);
}

.model-selector__cost--premium {
  color: rgba(251, 146, 60, 0.9);
  background: rgba(251, 146, 60, 0.1);
}

.model-selector__check {
  flex-shrink: 0;
  color: var(--neon-cyan);
}

.model-selector__empty {
  padding: 1rem;
  text-align: center;
  font-size: 0.8rem;
  color: var(--text-muted);
}

/* Scrollbar */
.model-selector__dropdown::-webkit-scrollbar {
  width: 4px;
}
.model-selector__dropdown::-webkit-scrollbar-thumb {
  background: var(--neon-cyan-15);
  border-radius: 2px;
}

/* Transition */
.dropdown-enter-active {
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.dropdown-leave-active {
  transition: all 0.15s ease;
}
.dropdown-enter-from {
  opacity: 0;
  transform: translateY(8px) scale(0.97);
}
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.97);
}
</style>
