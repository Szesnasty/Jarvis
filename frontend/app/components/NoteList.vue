<template>
  <div class="note-list">
    <div class="note-list__search">
      <input
        v-model="searchQuery"
        type="text"
        class="note-list__search-input"
        :placeholder="searchPlaceholder"
        @keydown.enter="onSearch"
      />
      <button
        v-if="searchQuery"
        class="note-list__clear"
        @click="onClearSearch"
      >
        Clear
      </button>
    </div>
    <div class="note-list__modes" role="tablist" aria-label="Search mode">
      <button
        v-for="mode in searchModes"
        :key="mode.value"
        type="button"
        class="note-list__mode-btn"
        :class="{ 'note-list__mode-btn--active': searchMode === mode.value }"
        :title="mode.tooltip"
        :aria-pressed="searchMode === mode.value"
        @click="onChangeMode(mode.value)"
      >
        <span class="note-list__mode-icon">{{ mode.icon }}</span>
        {{ mode.label }}
      </button>
    </div>

    <div class="note-list__folders">
      <button
        v-for="folder in folders"
        :key="folder"
        class="note-list__folder-btn"
        :class="{ 'note-list__folder-btn--active': activeFolder === folder }"
        @click="onFolderClick(folder)"
      >
        {{ folder }}
      </button>
    </div>

    <div v-if="loading" class="note-list__loading">
      <span class="note-list__spinner" />
      <span class="note-list__loading-text">Loading notes…</span>
    </div>

    <p v-else-if="notes.length === 0" class="note-list__empty">No notes yet</p>

    <ul v-else class="note-list__items">
      <li
        v-for="note in notes"
        :key="note.path"
        class="note-list__item"
        :class="{ 'note-list__item--active': selectedPath === note.path }"
        @click="$emit('select', note.path)"
      >
        <div class="note-list__item-row">
          <span class="note-list__item-title">{{ note.title || note.path }}</span>
          <button
            class="note-list__delete"
            title="Delete note"
            @click.stop="confirmDelete(note)"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
              <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
        <span class="note-list__item-tags">{{ note.tags.join(', ') }}</span>
        <span class="note-list__item-date">{{ note.updated_at.slice(0, 10) }}</span>
      </li>
    </ul>

    <ConfirmDialog
      :visible="deleteTarget !== null"
      :loading="deleting"
      title="Delete note?"
      :message="`&quot;${deleteTarget?.title || deleteTarget?.path || ''}&quot; will be permanently removed from memory.`"
      confirm-label="Delete"
      @confirm="handleDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<script setup lang="ts">
import type { NoteMetadata } from '~/types'

type SearchMode = 'keyword' | 'semantic' | 'hybrid'

const props = defineProps<{
  notes: NoteMetadata[]
  selectedPath: string | null
  folders: string[]
  activeFolder: string | null
  loading?: boolean
  onDelete: (path: string) => Promise<void>
}>()

const emit = defineEmits<{
  select: [path: string]
  folder: [folder: string | null]
  search: [query: string, mode: SearchMode]
}>()

const searchQuery = ref('')
const searchMode = ref<SearchMode>('keyword')
const deleteTarget = ref<NoteMetadata | null>(null)
const deleting = ref(false)

const searchModes: { value: SearchMode; label: string; icon: string; tooltip: string }[] = [
  { value: 'keyword', label: 'Keyword', icon: '🔍', tooltip: 'Exact word match via BM25' },
  { value: 'semantic', label: 'Semantic', icon: '🧠', tooltip: 'Meaning-based search via embeddings' },
  { value: 'hybrid', label: 'Hybrid', icon: '⚡', tooltip: 'Combined BM25 + embeddings + graph' },
]

const searchPlaceholder = computed(() => {
  if (searchMode.value === 'semantic') return 'Ask by meaning…'
  if (searchMode.value === 'hybrid') return 'Hybrid search…'
  return 'Search notes...'
})

function onChangeMode(mode: SearchMode) {
  if (searchMode.value === mode) return
  searchMode.value = mode
  if (searchQuery.value) emit('search', searchQuery.value, mode)
}

function confirmDelete(note: NoteMetadata) {
  deleteTarget.value = note
}

async function handleDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await props.onDelete(deleteTarget.value.path)
  } finally {
    deleting.value = false
    deleteTarget.value = null
  }
}

function onFolderClick(folder: string) {
  if (props.activeFolder === folder) {
    emit('folder', null)
  } else {
    emit('folder', folder)
  }
}

function onSearch() {
  emit('search', searchQuery.value, searchMode.value)
}

function onClearSearch() {
  searchQuery.value = ''
  emit('search', '', searchMode.value)
}
</script>

<style scoped>
.note-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem 1.25rem;
  height: 100%;
  overflow-y: auto;
}

.note-list__search {
  display: flex;
  gap: 0.5rem;
}

.note-list__search-input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  background: var(--bg-surface);
  color: var(--text-primary);
}

.note-list__clear {
  padding: 0.5rem 0.75rem;
  background: transparent;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.note-list__clear:hover {
  color: var(--neon-cyan);
  border-color: var(--neon-cyan-30);
}

.note-list__modes {
  display: flex;
  gap: 0.25rem;
}

.note-list__mode-btn {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  padding: 0.3rem 0.5rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.72rem;
  transition: all 0.2s;
}

.note-list__mode-btn:hover {
  color: var(--neon-cyan);
  border-color: var(--neon-cyan-30);
}

.note-list__mode-btn--active {
  background: var(--neon-cyan-08);
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan);
  box-shadow: 0 0 8px var(--neon-cyan-08);
}

.note-list__mode-icon {
  font-size: 0.85rem;
  line-height: 1;
}

.note-list__folders {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.note-list__folder-btn {
  padding: 0.3rem 0.65rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 6px;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.2s;
}

.note-list__folder-btn:hover {
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan);
}

.note-list__folder-btn--active {
  background: var(--neon-cyan-08);
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}

.note-list__empty {
  color: var(--text-muted);
  text-align: center;
  padding: 2rem 0;
}

.note-list__items {
  list-style: none;
  padding: 0;
  margin: 0;
}

.note-list__item {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0.6rem 0.65rem;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
}

.note-list__item:hover {
  background: var(--bg-elevated);
  border-color: var(--border-subtle);
}

.note-list__item--active {
  background: var(--neon-cyan-08);
  border-color: var(--neon-cyan-15);
}

.note-list__item--active .note-list__item-title {
  color: var(--neon-cyan);
}

.note-list__item-title {
  font-weight: 500;
  font-size: 0.9rem;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.note-list__item-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.note-list__delete {
  flex-shrink: 0;
  opacity: 0;
  background: none;
  border: none;
  padding: 0.2rem;
  border-radius: 4px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
}

.note-list__item:hover .note-list__delete {
  opacity: 0.6;
}

.note-list__delete:hover {
  opacity: 1 !important;
  color: rgba(239, 68, 68, 0.9);
  background: rgba(239, 68, 68, 0.1);
  box-shadow: 0 0 10px rgba(239, 68, 68, 0.15);
}

.note-list__item-tags {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.note-list__item-date {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.note-list__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
  padding: 2.5rem 0;
}

.note-list__spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--neon-cyan-15);
  border-top-color: var(--neon-cyan);
  border-radius: 50%;
  animation: note-spin 0.7s linear infinite;
}

.note-list__loading-text {
  font-size: 0.75rem;
  color: var(--text-muted);
}

@keyframes note-spin {
  to { transform: rotate(360deg); }
}
</style>
