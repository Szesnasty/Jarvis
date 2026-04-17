<template>
  <div class="import-dialog" v-if="visible">
    <div class="import-dialog__backdrop" @click="$emit('close')" />
    <div class="import-dialog__panel">
      <h2 class="import-dialog__title">Import File</h2>

      <div
        class="import-dialog__dropzone"
        @dragover.prevent
        @drop.prevent="handleDrop"
      >
        <p>Drag & drop a file here or</p>
        <input
          ref="fileInput"
          type="file"
          accept=".md,.txt,.pdf,.csv,.xml"
          class="import-dialog__file-input"
          @change="handleFileSelect"
        />
        <button class="import-dialog__browse-btn" @click="($refs.fileInput as HTMLInputElement).click()">
          Browse
        </button>
      </div>

      <div v-if="selectedFile" class="import-dialog__selected">
        <p>{{ selectedFile.name }} ({{ Math.round(selectedFile.size / 1024) }}KB)</p>
      </div>

      <div class="import-dialog__options">
        <label class="import-dialog__label">Target folder</label>
        <select v-model="targetFolder" class="import-dialog__select">
          <option value="knowledge">knowledge</option>
          <option value="inbox">inbox</option>
          <option value="projects">projects</option>
          <option value="areas">areas</option>
        </select>
      </div>

      <div v-if="uploading" class="import-dialog__progress">
        Importing...
      </div>

      <div v-if="error" class="import-dialog__error">{{ error }}</div>
      <div v-if="success" class="import-dialog__success">{{ success }}</div>

      <div class="import-dialog__actions">
        <button class="import-dialog__cancel-btn" @click="$emit('close')">Cancel</button>
        <button
          class="import-dialog__import-btn"
          :disabled="!selectedFile || uploading"
          @click="handleImport"
        >
          Import
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  imported: [result: Record<string, unknown>]
}>()

const selectedFile = ref<File | null>(null)
const targetFolder = ref('knowledge')
const uploading = ref(false)
const error = ref('')
const success = ref('')

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files && input.files[0]) {
    selectedFile.value = input.files[0]
    error.value = ''
    success.value = ''
  }
}

function handleDrop(event: DragEvent) {
  const files = event.dataTransfer?.files
  if (files && files[0]) {
    selectedFile.value = files[0]
    error.value = ''
    success.value = ''
  }
}

async function handleImport() {
  if (!selectedFile.value) return
  uploading.value = true
  error.value = ''
  success.value = ''

  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('folder', targetFolder.value)

  try {
    const result = await $fetch<Record<string, unknown>>('/api/memory/ingest', {
      method: 'POST',
      body: formData,
    })
    // Structured imports (CSV/XML) return { notes: [...], total_notes, format }
    if (result.total_notes) {
      success.value = `Imported ${result.total_notes} notes from ${result.source} (${result.format})`
    } else {
      success.value = `Imported: ${result.path}`
    }
    emit('imported', result)
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : 'Import failed'
  } finally {
    uploading.value = false
  }
}
</script>

<style scoped>
.import-dialog__backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 99;
}
.import-dialog__panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: #1a1a2e;
  border: 1px solid var(--color-border, #333);
  border-radius: 12px;
  padding: 2rem;
  z-index: 100;
  min-width: 400px;
  max-width: 500px;
}
.import-dialog__title {
  margin: 0 0 1rem;
  font-size: 1.2rem;
}
.import-dialog__dropzone {
  border: 2px dashed var(--color-border, #333);
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
}
.import-dialog__file-input {
  display: none;
}
.import-dialog__browse-btn {
  margin-top: 0.5rem;
  padding: 0.4rem 1.25rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 4px;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.import-dialog__selected {
  margin-top: 0.75rem;
  font-size: 0.9rem;
  opacity: 0.8;
}
.import-dialog__options {
  margin-top: 1rem;
}
.import-dialog__label {
  font-size: 0.85rem;
  display: block;
  margin-bottom: 0.25rem;
}
.import-dialog__select {
  padding: 0.4rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 4px;
  background: transparent;
  color: inherit;
  width: 100%;
}
.import-dialog__progress {
  margin-top: 0.75rem;
  opacity: 0.7;
}
.import-dialog__error {
  margin-top: 0.75rem;
  color: #ef4444;
}
.import-dialog__success {
  margin-top: 0.75rem;
  color: #22c55e;
}
.import-dialog__actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 1.5rem;
}
.import-dialog__cancel-btn,
.import-dialog__import-btn {
  padding: 0.5rem 1.25rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 4px;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.import-dialog__import-btn {
  background: var(--color-primary, #60a5fa);
  color: #fff;
}
.import-dialog__import-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
