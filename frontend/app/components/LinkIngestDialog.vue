<template>
  <div class="link-dialog" v-if="modelValue">
    <div class="link-dialog__backdrop" @click="$emit('update:modelValue', false)" />
    <div class="link-dialog__panel">
      <div class="link-dialog__header">
        <h2 class="link-dialog__title">Import from URL</h2>
        <button class="link-dialog__close" @click="$emit('update:modelValue', false)">✕</button>
      </div>

      <label class="link-dialog__label">URL</label>
      <input
        v-model="url"
        type="url"
        class="link-dialog__input"
        placeholder="https://..."
        @input="onUrlChange"
      />

      <div v-if="urlType === 'youtube'" class="link-dialog__badge link-dialog__badge--yt">
        🎬 YouTube video detected
      </div>
      <div v-else-if="urlType === 'webpage'" class="link-dialog__badge link-dialog__badge--web">
        📄 Web article detected
      </div>
      <div v-else-if="url.trim() && urlType === 'invalid'" class="link-dialog__badge link-dialog__badge--err">
        ❌ Invalid URL
      </div>

      <label class="link-dialog__label">Save to folder</label>
      <select v-model="folder" class="link-dialog__select">
        <option value="knowledge">knowledge</option>
        <option value="inbox">inbox</option>
        <option value="projects">projects</option>
        <option value="areas">areas</option>
      </select>

      <label class="link-dialog__checkbox-label">
        <input v-model="summarize" type="checkbox" />
        AI Summary (uses API credits)
      </label>

      <div v-if="loading" class="link-dialog__progress">Importing...</div>
      <div v-if="error" class="link-dialog__error">{{ error }}</div>
      <div v-if="result" class="link-dialog__success">
        ✅ Saved: {{ result.path }}<br />
        {{ result.word_count.toLocaleString() }} words · {{ result.type }}
        <template v-if="result.summary"><br />{{ result.summary }}</template>
      </div>

      <div class="link-dialog__actions">
        <button class="link-dialog__cancel-btn" @click="$emit('update:modelValue', false)">Cancel</button>
        <button
          class="link-dialog__import-btn"
          :disabled="!canImport"
          @click="handleImport"
        >
          Import
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { UrlIngestResult } from '~/types'

defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  imported: [result: UrlIngestResult]
}>()

const { ingestUrl } = useApi()

const url = ref('')
const folder = ref('knowledge')
const summarize = ref(false)
const loading = ref(false)
const error = ref('')
const result = ref<UrlIngestResult | null>(null)

type UrlType = 'youtube' | 'webpage' | 'invalid' | null

const YT_RE = /(?:youtube\.com\/watch\?.*v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([\w-]{11})/
const URL_RE = /^https?:\/\/.+/

const urlType = ref<UrlType>(null)

function detectUrlType(value: string): UrlType {
  const trimmed = value.trim()
  if (!trimmed) return null
  if (!URL_RE.test(trimmed)) return 'invalid'
  if (YT_RE.test(trimmed)) return 'youtube'
  return 'webpage'
}

function onUrlChange() {
  urlType.value = detectUrlType(url.value)
  error.value = ''
  result.value = null
}

const canImport = computed(() => {
  return !loading.value && (urlType.value === 'youtube' || urlType.value === 'webpage')
})

async function handleImport() {
  if (!canImport.value) return
  loading.value = true
  error.value = ''
  result.value = null

  try {
    const res = await ingestUrl(url.value.trim(), folder.value, summarize.value)
    result.value = res
    emit('imported', res)
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : 'Import failed'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.link-dialog__backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
}
.link-dialog__panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: #1a1a2e;
  border: 1px solid var(--color-border, #333);
  border-radius: 12px;
  padding: 2rem;
  z-index: 100;
  min-width: 420px;
  max-width: 500px;
}
.link-dialog__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1rem;
}
.link-dialog__title {
  margin: 0;
  font-size: 1.2rem;
}
.link-dialog__close {
  background: none;
  border: none;
  color: inherit;
  font-size: 1.2rem;
  cursor: pointer;
  opacity: 0.6;
}
.link-dialog__close:hover {
  opacity: 1;
}
.link-dialog__label {
  display: block;
  font-size: 0.85rem;
  margin-top: 1rem;
  margin-bottom: 0.25rem;
  color: #9ca3af;
}
.link-dialog__input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 6px;
  background: transparent;
  color: inherit;
  font-size: 0.95rem;
  box-sizing: border-box;
}
.link-dialog__select {
  width: 100%;
  padding: 0.4rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 6px;
  background: transparent;
  color: inherit;
}
.link-dialog__badge {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}
.link-dialog__badge--yt {
  color: #f87171;
  background: rgba(248, 113, 113, 0.1);
}
.link-dialog__badge--web {
  color: #60a5fa;
  background: rgba(96, 165, 250, 0.1);
}
.link-dialog__badge--err {
  color: #ef4444;
}
.link-dialog__checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 1rem;
  font-size: 0.9rem;
  cursor: pointer;
}
.link-dialog__progress {
  margin-top: 0.75rem;
  opacity: 0.7;
}
.link-dialog__error {
  margin-top: 0.75rem;
  color: #ef4444;
}
.link-dialog__success {
  margin-top: 0.75rem;
  color: #22c55e;
  font-size: 0.9rem;
  line-height: 1.5;
}
.link-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1.5rem;
}
.link-dialog__cancel-btn,
.link-dialog__import-btn {
  padding: 0.5rem 1.25rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 6px;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.link-dialog__import-btn {
  background: var(--color-primary, #60a5fa);
  color: #fff;
}
.link-dialog__import-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
