<template>
  <div class="know-panel">
    <!-- Header bar -->
    <div class="know-panel__header">
      <div class="know-panel__header-label">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
        </svg>
        <span>Knowledge Base</span>
        <span class="know-panel__count">{{ files.length }}</span>
      </div>
    </div>

    <!-- Drop zone -->
    <div
      class="know-panel__dropzone"
      :class="{
        'know-panel__dropzone--dragover': isDragOver,
        'know-panel__dropzone--uploading': uploading,
      }"
      @dragover.prevent="isDragOver = true"
      @dragleave.prevent="isDragOver = false"
      @drop.prevent="handleDrop"
    >
      <div v-if="uploading" class="know-panel__upload-progress">
        <div class="know-panel__spinner" />
        <span>Processing...</span>
      </div>
      <div v-else class="know-panel__drop-content">
        <div class="know-panel__drop-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="17 8 12 3 7 8"/>
            <line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
        </div>
        <span class="know-panel__drop-text">Drop files here</span>
        <button class="know-panel__browse-btn" @click="triggerFileInput">or browse</button>
        <input
          ref="fileInputRef"
          type="file"
          accept=".md,.txt,.pdf,.csv,.json"
          multiple
          class="know-panel__file-input"
          @change="handleFileSelect"
        />
      </div>
    </div>

    <!-- URL ingest bar -->
    <div class="know-panel__url-bar">
      <svg class="know-panel__url-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
      </svg>
      <input
        v-model="urlInput"
        class="know-panel__url-input"
        placeholder="Paste URL to ingest..."
        @keydown.enter="handleUrlIngest"
      />
      <button
        class="know-panel__url-go"
        :disabled="!urlInput.trim() || urlIngesting"
        @click="handleUrlIngest"
      >
        <span v-if="urlIngesting" class="know-panel__spinner know-panel__spinner--small" />
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="5" y1="12" x2="19" y2="12"/>
          <polyline points="12 5 19 12 12 19"/>
        </svg>
      </button>
    </div>

    <!-- File list -->
    <div v-if="isLoading" class="know-panel__loading">
      <div class="know-panel__spinner" />
      <span>Loading files...</span>
    </div>

    <TransitionGroup v-else-if="files.length" name="file-list" tag="div" class="know-panel__files">
      <div
        v-for="file in files"
        :key="file.filename"
        class="know-panel__file"
      >
        <div class="know-panel__file-icon">
          {{ fileIcon(file.filename) }}
        </div>
        <div class="know-panel__file-info">
          <span class="know-panel__file-title">{{ file.title || file.filename }}</span>
          <span class="know-panel__file-meta">{{ formatSize(file.size) }}</span>
        </div>
        <button
          class="know-panel__file-delete"
          title="Remove file"
          @click="handleDeleteFile(file.filename)"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>
      </div>
    </TransitionGroup>

    <div v-else-if="!isLoading" class="know-panel__empty">
      No files yet — drop files or paste a URL above
    </div>

    <!-- Error display -->
    <Transition name="fade">
      <div v-if="errorMsg" class="know-panel__error" @click="errorMsg = ''">
        {{ errorMsg }}
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { SpecialistFileInfo } from '~/types'
import { useSpecialists } from '~/composables/useSpecialists'

const props = defineProps<{
  specialistId: string
}>()

const { files: allFiles, filesLoading, uploadFile, ingestUrl, removeFile } = useSpecialists()

const files = computed<SpecialistFileInfo[]>(() => allFiles.value[props.specialistId] || [])
const isLoading = computed(() => filesLoading.value[props.specialistId] || false)

const isDragOver = ref(false)
const uploading = ref(false)
const urlInput = ref('')
const urlIngesting = ref(false)
const errorMsg = ref('')
const fileInputRef = ref<HTMLInputElement | null>(null)

const ALLOWED_EXTS = new Set(['md', 'txt', 'pdf', 'csv', 'json'])
const MAX_FILE_BYTES = 50 * 1024 * 1024 // 50 MB

function triggerFileInput() {
  fileInputRef.value?.click()
}

function validateFiles(fileList: FileList): { valid: File[]; rejected: string[] } {
  const valid: File[] = []
  const rejected: string[] = []
  for (const file of Array.from(fileList)) {
    const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
    if (!ALLOWED_EXTS.has(ext)) {
      rejected.push(`${file.name} (unsupported type)`)
    } else if (file.size > MAX_FILE_BYTES) {
      rejected.push(`${file.name} (exceeds 50 MB)`)
    } else {
      valid.push(file)
    }
  }
  return { valid, rejected }
}

async function handleFiles(fileList: FileList) {
  const { valid, rejected } = validateFiles(fileList)
  if (rejected.length) {
    errorMsg.value = `Skipped: ${rejected.join(', ')}`
  }
  if (!valid.length) return

  uploading.value = true
  if (!rejected.length) errorMsg.value = ''
  try {
    for (const file of valid) {
      await uploadFile(props.specialistId, file)
    }
  } catch (err: unknown) {
    errorMsg.value = err instanceof Error ? err.message : 'Upload failed'
  } finally {
    uploading.value = false
  }
}

function handleDrop(event: DragEvent) {
  isDragOver.value = false
  const droppedFiles = event.dataTransfer?.files
  if (droppedFiles?.length) {
    handleFiles(droppedFiles)
  }
}

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files?.length) {
    handleFiles(input.files)
    input.value = ''
  }
}

async function handleUrlIngest() {
  const url = urlInput.value.trim()
  if (!url) return
  try { new URL(url) } catch {
    errorMsg.value = 'Enter a valid URL (https://...)'
    return
  }
  urlIngesting.value = true
  errorMsg.value = ''
  try {
    await ingestUrl(props.specialistId, url)
    urlInput.value = ''
  } catch (err: unknown) {
    errorMsg.value = err instanceof Error ? err.message : 'URL ingest failed'
  } finally {
    urlIngesting.value = false
  }
}

async function handleDeleteFile(filename: string) {
  errorMsg.value = ''
  try {
    await removeFile(props.specialistId, filename)
  } catch (err: unknown) {
    errorMsg.value = err instanceof Error ? err.message : 'Delete failed'
  }
}

function fileIcon(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'pdf': return '\u{1F4C4}'
    case 'md': return '\u{1F4DD}'
    case 'txt': return '\u{1F4C3}'
    case 'csv': return '\u{1F4CA}'
    case 'json': return '\u{1F4CB}'
    default: return '\u{1F4C1}'
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<style scoped>
.know-panel {
  border-top: 1px solid var(--border-subtle);
  padding: 0.875rem;
  display: flex;
  flex-direction: column;
  gap: 0.625rem;
}

/* --- Header --- */
.know-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.know-panel__header-label {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
}

.know-panel__count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  background: var(--neon-cyan-08);
  border: 1px solid var(--neon-cyan-15);
  color: var(--neon-cyan-60);
  font-size: 0.65rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

/* --- Dropzone --- */
.know-panel__dropzone {
  border: 1.5px dashed var(--border-default);
  border-radius: 8px;
  padding: 0.875rem;
  text-align: center;
  transition: all 0.25s ease;
  background: transparent;
  position: relative;
  overflow: hidden;
}

.know-panel__dropzone::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    135deg,
    transparent 0%,
    var(--neon-cyan-08) 50%,
    transparent 100%
  );
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}

.know-panel__dropzone--dragover {
  border-color: var(--neon-cyan-60);
  border-style: solid;
  box-shadow:
    0 0 20px var(--neon-cyan-08),
    inset 0 0 30px var(--neon-cyan-08);
}

.know-panel__dropzone--dragover::before {
  opacity: 1;
}

.know-panel__drop-content {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.know-panel__drop-icon {
  color: var(--text-muted);
  display: flex;
  transition: color 0.2s;
}

.know-panel__dropzone--dragover .know-panel__drop-icon {
  color: var(--neon-cyan);
}

.know-panel__drop-text {
  font-size: 0.78rem;
  color: var(--text-muted);
}

.know-panel__browse-btn {
  background: none;
  border: none;
  color: var(--neon-cyan-60);
  font-size: 0.78rem;
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
  text-underline-offset: 2px;
  transition: color 0.2s;
}

.know-panel__browse-btn:hover {
  color: var(--neon-cyan);
  text-shadow: 0 0 8px var(--neon-cyan-30);
}

.know-panel__file-input {
  display: none;
}

/* --- URL bar --- */
.know-panel__url-bar {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.35rem 0.5rem;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-base);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.know-panel__url-bar:focus-within {
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 0 2px var(--neon-cyan-08);
}

.know-panel__url-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.know-panel__url-input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 0.78rem;
  color: var(--text-primary);
  padding: 0.15rem 0;
  outline: none;
}

.know-panel__url-input::placeholder {
  color: var(--text-muted);
}

.know-panel__url-go {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  border: 1px solid var(--neon-cyan-15);
  background: var(--neon-cyan-08);
  color: var(--neon-cyan-60);
  cursor: pointer;
  flex-shrink: 0;
  transition: all 0.2s;
}

.know-panel__url-go:hover:not(:disabled) {
  background: var(--neon-cyan-15);
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan);
  box-shadow: 0 0 8px var(--neon-cyan-08);
}

.know-panel__url-go:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* --- File list --- */
.know-panel__files {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 200px;
  overflow-y: auto;
}

.know-panel__file {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.4rem 0.5rem;
  border-radius: 5px;
  transition: background 0.15s;
}

.know-panel__file:hover {
  background: var(--bg-hover);
}

.know-panel__file-icon {
  font-size: 0.85rem;
  flex-shrink: 0;
  width: 20px;
  text-align: center;
}

.know-panel__file-info {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}

.know-panel__file-title {
  font-size: 0.78rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.know-panel__file-meta {
  font-size: 0.65rem;
  color: var(--text-muted);
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}

.know-panel__file-delete {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 3px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  opacity: 0;
  transition: all 0.15s;
  flex-shrink: 0;
}

.know-panel__file:hover .know-panel__file-delete {
  opacity: 1;
}

.know-panel__file-delete:hover {
  background: rgba(239, 68, 68, 0.12);
  color: var(--neon-red);
}

/* --- States --- */
.know-panel__loading,
.know-panel__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem;
  font-size: 0.75rem;
  color: var(--text-muted);
}

.know-panel__upload-progress {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.25rem;
  font-size: 0.78rem;
  color: var(--neon-cyan-60);
}

.know-panel__error {
  font-size: 0.75rem;
  color: var(--neon-red);
  padding: 0.4rem 0.6rem;
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
  border-radius: 5px;
  cursor: pointer;
}

/* --- Spinner --- */
.know-panel__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--neon-cyan-15);
  border-top-color: var(--neon-cyan-60);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.know-panel__spinner--small {
  width: 12px;
  height: 12px;
  border-width: 1.5px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* --- Transitions --- */
.file-list-enter-active {
  transition: all 0.25s ease;
}
.file-list-leave-active {
  transition: all 0.2s ease;
}
.file-list-enter-from {
  opacity: 0;
  transform: translateX(-8px);
}
.file-list-leave-to {
  opacity: 0;
  transform: translateX(8px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
