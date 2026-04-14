<template>
  <div class="memory-page">
    <aside class="memory-page__sidebar">
      <div class="memory-page__toolbar">
        <h2 class="memory-page__title">Memory</h2>
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
      <NoteList
        :notes="notes"
        :selected-path="selectedPath"
        :folders="folders"
        :active-folder="activeFolder"
        :loading="loadingNotes"
        :on-delete="onDeleteNote"
        @select="onSelectNote"
        @folder="onFolderChange"
        @search="onSearch"
      />
    </aside>
    <section class="memory-page__viewer">
      <NoteViewer :note="selectedNote" />
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
import type { NoteMetadata, NoteDetail } from '~/types'

const { fetchNotes, fetchNote, deleteNote } = useApi()

const notes = ref<NoteMetadata[]>([])
const selectedPath = ref<string | null>(null)
const selectedNote = ref<NoteDetail | null>(null)
const activeFolder = ref<string | null>(null)
const searchQuery = ref('')
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
    const params: { folder?: string; search?: string } = {}
    if (activeFolder.value) params.folder = activeFolder.value
    if (searchQuery.value) params.search = searchQuery.value
    const result = await fetchNotes(params)
    notes.value = Array.isArray(result) ? result : []
  } finally {
    loadingNotes.value = false
  }
}

async function onSelectNote(path: string) {
  selectedPath.value = path
  selectedNote.value = await fetchNote(path)
}

async function onFolderChange(folder: string | null) {
  activeFolder.value = folder
  searchQuery.value = ''
  await loadNotes()
}

async function onSearch(query: string) {
  searchQuery.value = query
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

async function onDeleteNote(path: string) {
  await deleteNote(path)
  notes.value = notes.value.filter(n => n.path !== path)
  if (selectedPath.value === path) {
    selectedPath.value = null
    selectedNote.value = null
  }
}

const _onMemoryChanged = () => loadNotes()

onMounted(() => {
  loadNotes()
  window.addEventListener('jarvis:memory-changed', _onMemoryChanged)
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
