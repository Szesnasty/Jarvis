<template>
  <div class="memory-page">
    <aside class="memory-page__sidebar">
      <div class="memory-page__toolbar">
        <h2 class="memory-page__title">Memory</h2>
        <div class="memory-page__toolbar-actions">
          <button class="memory-page__import-btn" @click="showImport = true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>
            Import file
          </button>
          <button class="memory-page__import-btn" @click="showUrlImport = true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
            Import URL
          </button>
        </div>
      </div>
      <NoteList
        :notes="notes"
        :selected-path="selectedPath"
        :folders="folders"
        :active-folder="activeFolder"
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

const folders = computed(() => {
  const set = new Set(notes.value.map((n) => n.folder))
  return Array.from(set).sort()
})

async function loadNotes() {
  const params: { folder?: string; search?: string } = {}
  if (activeFolder.value) params.folder = activeFolder.value
  if (searchQuery.value) params.search = searchQuery.value
  notes.value = await fetchNotes(params)
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

onMounted(() => {
  loadNotes()
})

defineExpose({ deleteNote: async (path: string) => {
  await deleteNote(path)
  notes.value = notes.value.filter((n) => n.path !== path)
  if (selectedPath.value === path) {
    selectedPath.value = null
    selectedNote.value = null
  }
}})
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

.memory-page__import-btn {
  padding: 0.4rem 0.85rem;
  border: 1px solid var(--neon-cyan-30);
  border-radius: 8px;
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.memory-page__import-btn:hover {
  background: rgba(2, 254, 255, 0.15);
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 15px var(--neon-cyan-08);
  text-shadow: 0 0 6px var(--neon-cyan-30);
}

.memory-page__viewer {
  flex: 1;
  background: var(--bg-deep);
}
</style>
