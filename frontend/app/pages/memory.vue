<template>
  <div class="memory-page">
    <aside class="memory-page__sidebar">
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
  min-height: 100vh;
}

.memory-page__sidebar {
  width: 320px;
  border-right: 1px solid var(--color-border, #333);
  flex-shrink: 0;
}

.memory-page__viewer {
  flex: 1;
}
</style>
