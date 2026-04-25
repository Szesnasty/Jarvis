<template>
  <div class="import-dialog" v-if="visible">
    <div class="import-dialog__backdrop" @click="$emit('close')" />
    <div class="import-dialog__panel">
      <h2 class="import-dialog__title">Import File</h2>

      <!-- Mode switch -->
      <div class="import-dialog__modes">
        <button
          type="button"
          class="import-dialog__mode-btn"
          :class="{ 'import-dialog__mode-btn--active': mode === 'generic' }"
          @click="setMode('generic')"
        >
          Generic
        </button>
        <button
          type="button"
          class="import-dialog__mode-btn"
          :class="{ 'import-dialog__mode-btn--active': mode === 'jira' }"
          @click="setMode('jira')"
        >
          Jira
        </button>
      </div>

      <p class="import-dialog__hint">
        <template v-if="mode === 'generic'">
          Saves the file as a note in your memory. Works for Markdown, text, PDF, CSV/XML.
          Embeddings + FTS are generated automatically.
        </template>
        <template v-else>
          Full Jira pipeline: per-issue notes under <code>memory/jira/{PROJECT}/</code>,
          structured DB (issues, links, history), embeddings, and graph relations.
          Accepts Jira XML or CSV exports.
        </template>
      </p>

      <div
        class="import-dialog__dropzone"
        @dragover.prevent
        @drop.prevent="handleDrop"
      >
        <p v-if="mode === 'generic'">Drag &amp; drop one or more files here, or</p>
        <p v-else>Drag &amp; drop a file here or</p>
        <input
          ref="fileInput"
          type="file"
          :accept="acceptAttr"
          :multiple="mode === 'generic'"
          class="import-dialog__file-input"
          @change="handleFileSelect"
        />
        <button class="import-dialog__browse-btn" @click="($refs.fileInput as HTMLInputElement).click()">
          Browse
        </button>
      </div>

      <div v-if="selectedFiles.length === 1 && selectedFiles[0]" class="import-dialog__selected">
        <p>{{ selectedFiles[0].name }} ({{ Math.round(selectedFiles[0].size / 1024) }}KB)</p>
      </div>
      <ul v-else-if="selectedFiles.length > 1" class="import-dialog__file-list">
        <li
          v-for="(f, idx) in selectedFiles"
          :key="`${f.name}-${idx}`"
          class="import-dialog__file-row"
          :class="fileStatuses[idx] ? `import-dialog__file-row--${fileStatuses[idx].state}` : ''"
        >
          <span class="import-dialog__file-name" :title="f.name">{{ f.name }}</span>
          <span class="import-dialog__file-meta">
            {{ Math.round(f.size / 1024) }}KB
            <span v-if="fileStatuses[idx]?.state === 'pending'" class="import-dialog__file-status">queued</span>
            <span v-else-if="fileStatuses[idx]?.state === 'uploading'" class="import-dialog__file-status">…</span>
            <span v-else-if="fileStatuses[idx]?.state === 'ok'" class="import-dialog__file-status import-dialog__file-status--ok">✓</span>
            <span v-else-if="fileStatuses[idx]?.state === 'error'" class="import-dialog__file-status import-dialog__file-status--error" :title="fileStatuses[idx]?.error">✗</span>
            <button
              v-if="!uploading"
              type="button"
              class="import-dialog__file-remove"
              @click="removeFile(idx)"
              aria-label="Remove file"
            >×</button>
          </span>
        </li>
      </ul>

      <!-- Generic options -->
      <div v-if="mode === 'generic'" class="import-dialog__options">
        <label class="import-dialog__label">Target folder</label>
        <select v-model="targetFolder" class="import-dialog__select">
          <option value="knowledge">knowledge</option>
          <option value="inbox">inbox</option>
          <option value="projects">projects</option>
          <option value="areas">areas</option>
        </select>
      </div>

      <!-- Jira options -->
      <div v-else class="import-dialog__options">
        <label class="import-dialog__label">Project filter (optional)</label>
        <input
          v-model="projectFilter"
          type="text"
          class="import-dialog__input"
          placeholder="e.g. PROJ,OPS  (comma-separated; empty = import all)"
        />
        <p class="import-dialog__sublabel">
          Only issues whose project key matches will be imported. Leave empty for full export.
        </p>
      </div>

      <div v-if="uploading" class="import-dialog__progress">
        <template v-if="selectedFiles.length > 1">
          Importing {{ uploadProgress.done }} of {{ uploadProgress.total }}…
        </template>
        <template v-else>
          Importing{{ mode === 'jira' ? ' (parsing + indexing + embedding)' : '' }}...
        </template>
      </div>

      <div v-if="error" class="import-dialog__error">{{ error }}</div>
      <div v-if="success" class="import-dialog__success">{{ success }}</div>

      <!-- Recent Jira imports -->
      <div v-if="mode === 'jira'" class="import-dialog__recent">
        <div class="import-dialog__recent-header">
          <h3 class="import-dialog__recent-title">Recent Jira imports</h3>
          <button
            type="button"
            class="import-dialog__refresh-btn"
            :disabled="recentLoading"
            @click="loadRecentImports"
          >
            {{ recentLoading ? '...' : 'Refresh' }}
          </button>
        </div>
        <div v-if="recentError" class="import-dialog__error">{{ recentError }}</div>
        <ul v-if="recentImports.length" class="import-dialog__recent-list">
          <li
            v-for="row in recentImports"
            :key="row.id"
            class="import-dialog__recent-row"
            :class="`import-dialog__recent-row--${row.status}`"
          >
            <div class="import-dialog__recent-line">
              <span class="import-dialog__recent-name" :title="row.filename">
                {{ row.filename }}
              </span>
              <span class="import-dialog__recent-status">{{ row.status }}</span>
            </div>
            <div class="import-dialog__recent-meta">
              {{ formatDate(row.started_at) }}
              · {{ row.issue_count }} issues
              ({{ row.inserted }} new, {{ row.updated }} upd)
              <span v-if="row.project_keys?.length">
                · {{ row.project_keys.join(', ') }}
              </span>
            </div>
            <div v-if="row.error" class="import-dialog__recent-error">
              {{ row.error }}
            </div>
          </li>
        </ul>
        <p v-else-if="!recentLoading && !recentError" class="import-dialog__recent-empty">
          No imports yet.
        </p>
      </div>

      <div class="import-dialog__actions">
        <button class="import-dialog__cancel-btn" @click="$emit('close')">Cancel</button>
        <button
          class="import-dialog__import-btn"
          :disabled="selectedFiles.length === 0 || uploading"
          @click="handleImport"
        >
          <template v-if="selectedFiles.length > 1">Import {{ selectedFiles.length }} files</template>
          <template v-else>Import</template>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useIngestStatus } from '~/composables/useIngestStatus'

const ingest = useIngestStatus()

defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  close: []
  imported: [result: Record<string, unknown>]
}>()

type Mode = 'generic' | 'jira'

interface JiraImportRow {
  id: number
  filename: string
  format: string
  project_keys: string[]
  issue_count: number
  inserted: number
  updated: number
  skipped: number
  bytes_processed: number
  duration_ms: number
  status: string
  error?: string | null
  started_at: string
  finished_at?: string | null
}

const mode = ref<Mode>('generic')
const selectedFiles = ref<File[]>([])
const targetFolder = ref('knowledge')
const projectFilter = ref('')
const uploading = ref(false)
const error = ref('')
const success = ref('')

type FileState = 'pending' | 'uploading' | 'ok' | 'error'
interface FileStatus { state: FileState; error?: string }
const fileStatuses = ref<FileStatus[]>([])
const uploadProgress = ref<{ done: number; total: number }>({ done: 0, total: 0 })

const recentImports = ref<JiraImportRow[]>([])
const recentLoading = ref(false)
const recentError = ref('')

const acceptAttr = computed(() =>
  mode.value === 'jira' ? '.xml,.csv' : '.md,.txt,.pdf,.csv,.xml,.json'
)

function setMode(next: Mode) {
  if (mode.value === next) return
  mode.value = next
  // Reset files when switching modes (extension constraints differ).
  selectedFiles.value = []
  fileStatuses.value = []
  error.value = ''
  success.value = ''
  if (next === 'jira' && recentImports.value.length === 0) {
    loadRecentImports()
  }
}

function acceptFiles(list: FileList | null | undefined) {
  if (!list || list.length === 0) return
  // In jira mode keep single-file behaviour; in generic mode accept many.
  const incoming = Array.from(list)
  if (mode.value === 'jira') {
    const f = incoming[0]
    if (!f || !validateFile(f)) return
    selectedFiles.value = [f]
    fileStatuses.value = [{ state: 'pending' }]
  } else {
    const valid: File[] = []
    for (const f of incoming) {
      if (validateFile(f)) valid.push(f)
      else return
    }
    // Append rather than replace so user can drop in batches.
    selectedFiles.value = [...selectedFiles.value, ...valid]
    fileStatuses.value = selectedFiles.value.map(() => ({ state: 'pending' }))
  }
  error.value = ''
  success.value = ''
}

function handleFileSelect(event: Event) {
  const input = event.target as HTMLInputElement
  acceptFiles(input.files)
  // Allow re-selecting the same file after a remove.
  input.value = ''
}

function handleDrop(event: DragEvent) {
  acceptFiles(event.dataTransfer?.files)
}

function removeFile(idx: number) {
  selectedFiles.value = selectedFiles.value.filter((_, i) => i !== idx)
  fileStatuses.value = fileStatuses.value.filter((_, i) => i !== idx)
}

function validateFile(file: File): boolean {
  if (mode.value === 'jira') {
    const name = file.name.toLowerCase()
    if (!name.endsWith('.xml') && !name.endsWith('.csv')) {
      error.value = 'Jira mode accepts only .xml or .csv exports.'
      return false
    }
  }
  return true
}

async function handleImport() {
  if (selectedFiles.value.length === 0) return
  uploading.value = true
  error.value = ''
  success.value = ''

  try {
    if (mode.value === 'jira') {
      // Jira import is single-file by design (one export = one batch).
      await importJira(selectedFiles.value[0]!)
    } else {
      await importGenericBatch()
    }
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : 'Import failed'
  } finally {
    uploading.value = false
  }
}

async function importGenericBatch() {
  const files = selectedFiles.value
  uploadProgress.value = { done: 0, total: files.length }
  let okCount = 0
  let failCount = 0
  const lastErrors: string[] = []

  // Bounded parallel upload. The backend is now non-blocking (pdfplumber
  // runs in a threadpool, SQLite has a 30 s busy_timeout) so we can run a
  // few uploads at once and the user gets per-file XHR progress in the
  // StatusBar.
  const CONCURRENCY = 3
  let nextIndex = 0
  let doneSoFar = 0

  const runOne = async (i: number) => {
    fileStatuses.value[i] = { state: 'uploading' }
    const file = files[i]!
    try {
      const result = await importGeneric(file)
      fileStatuses.value[i] = { state: 'ok' }
      okCount += 1
      emit('imported', result)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Import failed'
      fileStatuses.value[i] = { state: 'error', error: msg }
      failCount += 1
      if (lastErrors.length < 3) lastErrors.push(`${file.name}: ${msg}`)
    } finally {
      doneSoFar += 1
      uploadProgress.value = { done: doneSoFar, total: files.length }
    }
  }

  const worker = async () => {
    while (true) {
      const i = nextIndex++
      if (i >= files.length) return
      await runOne(i)
    }
  }

  const workerCount = Math.min(CONCURRENCY, files.length)
  await Promise.all(Array.from({ length: workerCount }, () => worker()))

  if (failCount === 0) {
    success.value = `Imported ${okCount} ${okCount === 1 ? 'file' : 'files'}.`
  } else if (okCount === 0) {
    error.value = `All ${failCount} imports failed. ${lastErrors.join('; ')}`
  } else {
    success.value = `Imported ${okCount} of ${files.length}.`
    error.value = `${failCount} failed: ${lastErrors.join('; ')}`
  }
}

async function importGeneric(file: File): Promise<Record<string, unknown>> {
  // Use the shared uploadFile() so the StatusBar pill shows real
  // bytes-uploaded progress for each file.
  const result = await ingest.uploadFile('/api/memory/ingest', file, {
    folder: targetFolder.value,
  })
  return (result || {}) as Record<string, unknown>
}

async function importJira(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  const filter = projectFilter.value.trim()
  if (filter) formData.append('project_filter', filter)

  const result = await $fetch<{
    status: string
    filename: string
    format: string
    stats: {
      issue_count: number
      inserted: number
      updated: number
      skipped: number
      bytes_processed: number
      project_keys: string[]
    }
  }>('/api/jira/import', {
    method: 'POST',
    body: formData,
  })

  const s = result.stats
  const projects = s.project_keys.length ? ` [${s.project_keys.join(', ')}]` : ''
  success.value =
    `Jira ${result.format.toUpperCase()}: ${s.issue_count} issues ` +
    `(${s.inserted} new, ${s.updated} updated, ${s.skipped} skipped)${projects}`
  emit('imported', result as unknown as Record<string, unknown>)
  // Refresh history so the user sees their new batch immediately.
  loadRecentImports()
}

async function loadRecentImports() {
  recentLoading.value = true
  recentError.value = ''
  try {
    const rows = await $fetch<JiraImportRow[]>('/api/jira/imports?limit=10')
    recentImports.value = rows
  } catch (err: unknown) {
    recentError.value =
      err instanceof Error ? err.message : 'Failed to load Jira import history'
  } finally {
    recentLoading.value = false
  }
}

function formatDate(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleString()
  } catch {
    return iso
  }
}

// Lazy-load history when dialog becomes visible while in Jira mode.
watch(
  () => mode.value,
  (m) => {
    if (m === 'jira' && recentImports.value.length === 0) {
      loadRecentImports()
    }
  }
)
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
  min-width: 440px;
  max-width: 560px;
  max-height: 90vh;
  overflow-y: auto;
}
.import-dialog__title {
  margin: 0 0 1rem;
  font-size: 1.2rem;
}
.import-dialog__modes {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.import-dialog__mode-btn {
  flex: 1;
  padding: 0.45rem 0.75rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 6px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 0.9rem;
}
.import-dialog__mode-btn--active {
  background: var(--color-primary, #60a5fa);
  color: #fff;
  border-color: var(--color-primary, #60a5fa);
}
.import-dialog__hint {
  font-size: 0.8rem;
  opacity: 0.7;
  margin: 0 0 1rem;
  line-height: 1.4;
}
.import-dialog__hint code {
  background: rgba(255, 255, 255, 0.08);
  padding: 0 0.25rem;
  border-radius: 3px;
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
.import-dialog__file-list {
  margin: 0.75rem 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  max-height: 180px;
  overflow-y: auto;
}
.import-dialog__file-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.55rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.02);
  font-size: 0.82rem;
}
.import-dialog__file-row--ok {
  border-left: 3px solid #22c55e;
}
.import-dialog__file-row--error {
  border-left: 3px solid #ef4444;
}
.import-dialog__file-row--uploading {
  border-left: 3px solid #60a5fa;
}
.import-dialog__file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.import-dialog__file-meta {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.75rem;
  opacity: 0.75;
  white-space: nowrap;
}
.import-dialog__file-status {
  font-size: 0.78rem;
  opacity: 0.85;
}
.import-dialog__file-status--ok {
  color: #22c55e;
}
.import-dialog__file-status--error {
  color: #ef4444;
}
.import-dialog__file-remove {
  background: transparent;
  border: none;
  color: inherit;
  opacity: 0.5;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0 0.2rem;
}
.import-dialog__file-remove:hover {
  opacity: 1;
  color: #ef4444;
}
.import-dialog__options {
  margin-top: 1rem;
}
.import-dialog__label {
  font-size: 0.85rem;
  display: block;
  margin-bottom: 0.25rem;
}
.import-dialog__sublabel {
  font-size: 0.75rem;
  opacity: 0.6;
  margin: 0.35rem 0 0;
}
.import-dialog__select,
.import-dialog__input {
  padding: 0.4rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 4px;
  background: transparent;
  color: inherit;
  width: 100%;
  font: inherit;
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
.import-dialog__recent {
  margin-top: 1.5rem;
  padding-top: 1rem;
  border-top: 1px solid var(--color-border, #333);
}
.import-dialog__recent-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}
.import-dialog__recent-title {
  margin: 0;
  font-size: 0.95rem;
}
.import-dialog__refresh-btn {
  padding: 0.25rem 0.6rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 4px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 0.8rem;
}
.import-dialog__refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.import-dialog__recent-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.import-dialog__recent-row {
  padding: 0.5rem 0.7rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.02);
}
.import-dialog__recent-row--ok {
  border-left: 3px solid #22c55e;
}
.import-dialog__recent-row--error,
.import-dialog__recent-row--failed {
  border-left: 3px solid #ef4444;
}
.import-dialog__recent-line {
  display: flex;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.85rem;
}
.import-dialog__recent-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.import-dialog__recent-status {
  text-transform: uppercase;
  font-size: 0.7rem;
  opacity: 0.7;
}
.import-dialog__recent-meta {
  font-size: 0.75rem;
  opacity: 0.65;
  margin-top: 0.2rem;
}
.import-dialog__recent-error {
  font-size: 0.75rem;
  color: #ef4444;
  margin-top: 0.25rem;
}
.import-dialog__recent-empty {
  font-size: 0.8rem;
  opacity: 0.6;
  margin: 0.5rem 0 0;
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
