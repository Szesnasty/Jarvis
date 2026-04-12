<template>
  <div class="memory-page">
    <aside class="memory-page__sidebar">
      <div class="memory-page__toolbar">
        <h2 class="memory-page__title">Memory</h2>
        <button class="memory-page__import-btn" @click="showImport = true">
          + Import file
        </button>
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
  min-height: calc(100vh - 40px);
}

.memory-page__sidebar {
  width: 320px;
  border-right: 1px solid var(--color-border, #333);
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.memory-page__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1rem 0.5rem;
  gap: 0.5rem;
}

.memory-page__title {
  margin: 0;
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #9ca3af;
}

.memory-page__import-btn {
  padding: 0.35rem 0.75rem;
  border: 1px solid #333;
  border-radius: 6px;
  background: #60a5fa;
  color: #fff;
  font-size: 0.8rem;
  cursor: pointer;
}

.memory-page__import-btn:hover {
  background: #3b82f6;
}

.memory-page__viewer {
  flex: 1;
}
</style>
