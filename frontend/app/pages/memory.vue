<template>
  <div class="memory-page">
    <aside class="memory-page__sidebar">
      <div class="memory-page__toolbar">
        <h2 class="memory-page__title">
          Memory
          <SmartConnectStatus aria-label="Smart Connect coverage for this workspace" />
        </h2>
        <div class="memory-page__toolbar-actions">
          <div class="memory-page__import-group" :class="{ open: showImportMenu }">
            <button class="memory-page__import-trigger" @click="showImportMenu = !showImportMenu">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              Import
              <svg class="memory-page__chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
            <Transition name="dropdown">
              <div v-if="showImportMenu" v-click-outside="() => showImportMenu = false" class="memory-page__import-dropdown">
                <button class="memory-page__dropdown-item" @click="showImport = true; showImportMenu = false">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>
                  <span class="memory-page__dropdown-label">
                    <strong>File</strong>
                    <small>Upload from disk</small>
                  </span>
                </button>
                <button class="memory-page__dropdown-item" @click="showUrlImport = true; showImportMenu = false">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                  <span class="memory-page__dropdown-label">
                    <strong>URL</strong>
                    <small>Import from link</small>
                  </span>
                </button>
              </div>
            </Transition>
          </div>
        </div>
      </div>
      <!-- Hide orphan banner when SC has processed every section (sections_unprocessed=0)
           because remaining orphans are in a final state and no user action is available. -->
      <div v-if="orphans.length > 0 && (coverage?.sections_unprocessed ?? 1) > 0" class="memory-page__orphans">
        <span class="memory-page__orphans-text">
          <strong>{{ orphans.length }}</strong> note{{ orphans.length === 1 ? '' : 's' }} need linking.
        </span>
        <button class="memory-page__orphans-link" @click="onShowFirstOrphan">Review</button>
      </div>
      <BulkPromoteBanner
        :pending-strong="coverage?.pending_strong_suggestions ?? 0"
        :pending-notes="coverage?.pending_strong_notes ?? 0"
        @review="onReviewFirstStrong"
        @promoted="onBulkPromoted"
      />
      <NoteList
        :notes="notes"
        :selected-path="selectedPath"
        :folders="folders"
        :active-folder="activeFolder"
        :loading="loadingNotes"
        :on-delete="onDeleteNote"
        @select="onSelectNote"
        @folder="onFolderChange"
        @search="(q, mode) => onSearch(q, mode)"
      />
    </aside>
    <section class="memory-page__viewer">
      <NoteViewer
        :note="selectedNote"
        @open="onSelectNote"
        @changed="onSuggestionChanged"
      />
    </section>
    <ImportDialog
      :visible="showImport"
      @close="showImport = false"
      @imported="onImported"
    />
    <LinkIngestDialog
      v-model="showUrlImport"
      @imported="onUrlImported"
    />
  </div>
</template>

<script setup lang="ts">
import type { NoteMetadata, NoteDetail, SemanticOrphan } from '~/types'

type SearchMode = 'keyword' | 'semantic' | 'hybrid'

const { fetchNotes, semanticSearchNotes, fetchNote, deleteNote, fetchSemanticOrphans, fetchConnectionsCoverage } = useApi()

type Coverage = Awaited<ReturnType<typeof fetchConnectionsCoverage>>

const notes = ref<NoteMetadata[]>([])
const orphans = ref<SemanticOrphan[]>([])
const coverage = ref<Coverage | null>(null)
const selectedPath = ref<string | null>(null)
const selectedNote = ref<NoteDetail | null>(null)
const activeFolder = ref<string | null>(null)
const searchQuery = ref('')
const searchMode = ref<SearchMode>('keyword')
const showImport = ref(false)
const showUrlImport = ref(false)
const showImportMenu = ref(false)
const loadingNotes = ref(false)

const vClickOutside = {
  mounted(el: HTMLElement, binding: { value: () => void }) {
    (el as any).__clickOutside = (e: MouseEvent) => {
      if (!el.contains(e.target as Node)) binding.value()
    }
    setTimeout(() => document.addEventListener('click', (el as any).__clickOutside), 0)
  },
  unmounted(el: HTMLElement) {
    document.removeEventListener('click', (el as any).__clickOutside)
  },
}

const folders = computed(() => {
  const list = Array.isArray(notes.value) ? notes.value : []
  const set = new Set(list.map((n) => n.folder))
  return Array.from(set).sort()
})

async function loadNotes() {
  loadingNotes.value = true
  try {
    if (!searchQuery.value || searchMode.value !== 'semantic') {
      const params: { folder?: string; search?: string; limit: number } = { limit: 200 }
      if (activeFolder.value) params.folder = activeFolder.value
      if (searchQuery.value) params.search = searchQuery.value
      const result = await fetchNotes(params)
      notes.value = Array.isArray(result) ? result : []
      return
    }

    const res = await semanticSearchNotes(searchQuery.value, 20)
    if (res.mode === 'unavailable') {
      notes.value = []
      return
    }

    const paths = (res.results || []).map((h) => h.path)
    if (paths.length === 0) {
      notes.value = []
      return
    }

    const all = await fetchNotes({ limit: 200 })
    const byPath = new Map((all || []).map((n) => [n.path, n]))
    notes.value = paths
      .map((p) => byPath.get(p))
      .filter((n): n is NoteMetadata => Boolean(n))
  } finally {
    loadingNotes.value = false
  }
}

// Per-document expansion state lives in NoteList via useState('noteTreeExpanded').
// We touch it here so that selecting a section (e.g. via the orphan "Review"
// button or any deep link) auto-expands its parent document — otherwise the
// section is hidden inside a collapsed row and the user sees nothing change.
const expandedDocs = useState<Record<string, boolean>>('noteTreeExpanded', () => ({}))

async function onSelectNote(path: string) {
  selectedPath.value = path
  selectedNote.value = await fetchNote(path)
  // If this note is a section of a split document, ensure its parent row is
  // expanded so the user can see the selection in the sidebar.
  const note = notes.value.find((n) => n.path === path)
  if (note?.parent) {
    expandedDocs.value = { ...expandedDocs.value, [note.parent]: true }
  }
}

async function onFolderChange(folder: string | null) {
  activeFolder.value = folder
  searchQuery.value = ''
  await loadNotes()
}

async function onSearch(query: string, mode: SearchMode = 'keyword') {
  searchQuery.value = query
  searchMode.value = mode
  activeFolder.value = null
  await loadNotes()
}

async function onImported() {
  showImport.value = false
  await loadNotes()
}

async function onUrlImported() {
  showUrlImport.value = false
  await loadNotes()
}

async function onSuggestionChanged() {
  // Reload the open note so the suggestions panel reflects the new
  // frontmatter (promoted item moved to `related`, dismissed item gone,
  // re-run produced fresh `suggested_related`).
  if (selectedPath.value) {
    selectedNote.value = await fetchNote(selectedPath.value)
  }
  // Orphan + coverage counts may shift after promote / dismiss / re-run.
  void loadOrphans()
  void loadCoverage()
}

async function loadOrphans() {
  try {
    orphans.value = await fetchSemanticOrphans()
  } catch {
    orphans.value = []
  }
}

async function loadCoverage() {
  try {
    coverage.value = await fetchConnectionsCoverage()
  } catch {
    coverage.value = null
  }
}

async function onShowFirstOrphan() {
  const first = orphans.value[0]
  if (!first) return
  // SemanticOrphan ids are `note:<path>`; strip the prefix.
  const path = first.id.startsWith('note:') ? first.id.slice('note:'.length) : first.id
  await onSelectNote(path)
}

async function onReviewFirstStrong() {
  // Open the first note that has a strong suggestion so the user can
  // inspect what 'Keep all' would actually do.
  const candidate = notes.value.find((n) => {
    const arr = (n as { suggested_related?: Array<{ confidence?: number }> }).suggested_related
    return Array.isArray(arr) && arr.some((s) => (s.confidence ?? 0) >= 0.8)
  })
  if (candidate) await onSelectNote(candidate.path)
}

async function onBulkPromoted() {
  // After bulk promote, reload everything that depends on suggestion state.
  await Promise.all([loadNotes(), loadOrphans(), loadCoverage()])
  if (selectedPath.value) {
    selectedNote.value = await fetchNote(selectedPath.value)
  }
}

async function onDeleteNote(path: string) {
  await deleteNote(path)
  notes.value = notes.value.filter(n => n.path !== path)
  if (selectedPath.value === path) {
    selectedPath.value = null
    selectedNote.value = null
  }
}

const _onMemoryChanged = () => { loadNotes(); loadOrphans(); loadCoverage() }

onMounted(() => {
  loadNotes()
  loadOrphans()
  loadCoverage()
  window.addEventListener('jarvis:memory-changed', _onMemoryChanged)
  // No coverage timer here — SmartConnectStatus.vue already polls /coverage
  // every 10 s. Adding a second timer doubles the request rate for no gain.
})

onUnmounted(() => {
  window.removeEventListener('jarvis:memory-changed', _onMemoryChanged)
})
</script>

<style scoped>
.memory-page {
  display: flex;
  height: calc(100vh - 40px);
}

.memory-page__sidebar {
  width: 340px;
  border-right: 1px solid var(--border-default);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-base);
}

.memory-page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem 0.75rem;
  gap: 0.75rem;
  border-bottom: 1px solid var(--border-subtle);
}

.memory-page__toolbar-actions {
  display: flex;
  gap: 0.5rem;
}

.memory-page__orphans {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--neon-cyan-20, rgba(0, 200, 255, 0.2));
  font-size: 0.82rem;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  background: var(--neon-cyan-08, rgba(0, 200, 255, 0.08));
  flex-shrink: 0;
}

.memory-page__orphans-text {
  line-height: 1.3;
}

.memory-page__orphans-link {
  background: none;
  border: 1px solid var(--neon-cyan, #00c8ff);
  color: var(--neon-cyan, #00c8ff);
  font-size: 0.78rem;
  padding: 0.3rem 0.75rem;
  border-radius: 5px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
}

.memory-page__orphans-link:hover {
  border-color: var(--neon-cyan, #00c8ff);
  background: var(--neon-cyan-16, rgba(0, 200, 255, 0.16));
}

.memory-page__title {
  margin: 0;
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-secondary);
}

/* Import dropdown trigger */
.memory-page__import-group {
  position: relative;
}

.memory-page__import-trigger {
  padding: 0.4rem 0.7rem;
  border: 1px solid var(--neon-cyan-30);
  border-radius: 8px;
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  white-space: nowrap;
}

.memory-page__import-trigger:hover,
.memory-page__import-group.open .memory-page__import-trigger {
  background: rgba(2, 254, 255, 0.15);
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 15px var(--neon-cyan-08);
}

.memory-page__chevron {
  transition: transform 0.2s ease;
  opacity: 0.6;
}

.memory-page__import-group.open .memory-page__chevron {
  transform: rotate(180deg);
  opacity: 1;
}

/* Dropdown panel */
.memory-page__import-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 190px;
  background: var(--bg-elevated);
  border: 1px solid var(--neon-cyan-30);
  border-radius: 10px;
  padding: 0.35rem;
  z-index: 50;
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.5),
    0 0 1px var(--neon-cyan-30),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.memory-page__dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  width: 100%;
  padding: 0.55rem 0.7rem;
  border: none;
  border-radius: 7px;
  background: transparent;
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
}

.memory-page__dropdown-item svg {
  color: var(--neon-cyan-60);
  flex-shrink: 0;
  transition: color 0.15s;
}

.memory-page__dropdown-item:hover {
  background: var(--neon-cyan-08);
}

.memory-page__dropdown-item:hover svg {
  color: var(--neon-cyan);
}

.memory-page__dropdown-label {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}

.memory-page__dropdown-label strong {
  font-size: 0.8rem;
  font-weight: 600;
}

.memory-page__dropdown-label small {
  font-size: 0.68rem;
  color: var(--text-muted);
  font-weight: 400;
}

/* Dropdown transition */
.dropdown-enter-active {
  transition: all 0.15s ease-out;
}
.dropdown-leave-active {
  transition: all 0.1s ease-in;
}
.dropdown-enter-from {
  opacity: 0;
  transform: translateY(-4px) scale(0.97);
}
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-2px) scale(0.98);
}

.memory-page__viewer {
  flex: 1;
  background: var(--bg-deep);
}
</style>
