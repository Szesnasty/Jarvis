<template>
  <div class="note-list">
    <div class="note-list__search">
      <input
        v-model="searchQuery"
        type="text"
        class="note-list__search-input"
        placeholder="Search notes..."
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

    <p v-if="notes.length === 0" class="note-list__empty">No notes yet</p>

    <ul v-else class="note-list__items">
      <li
        v-for="note in notes"
        :key="note.path"
        class="note-list__item"
        :class="{ 'note-list__item--active': selectedPath === note.path }"
        @click="$emit('select', note.path)"
      >
        <span class="note-list__item-title">{{ note.title || note.path }}</span>
        <span class="note-list__item-tags">{{ note.tags.join(', ') }}</span>
        <span class="note-list__item-date">{{ note.updated_at.slice(0, 10) }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import type { NoteMetadata } from '~/types'

const props = defineProps<{
  notes: NoteMetadata[]
  selectedPath: string | null
  folders: string[]
  activeFolder: string | null
}>()

const emit = defineEmits<{
  select: [path: string]
  folder: [folder: string | null]
  search: [query: string]
}>()

const searchQuery = ref('')

function onFolderClick(folder: string) {
  if (props.activeFolder === folder) {
    emit('folder', null)
  } else {
    emit('folder', folder)
  }
}

function onSearch() {
  emit('search', searchQuery.value)
}

function onClearSearch() {
  searchQuery.value = ''
  emit('search', '')
}
</script>

<style scoped>
.note-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem;
  height: 100%;
  overflow-y: auto;
}

.note-list__search {
  display: flex;
  gap: 0.5rem;
}

.note-list__search-input {
  flex: 1;
  padding: 0.5rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 0.25rem;
  background: var(--color-surface, #1a1a1a);
  color: var(--color-text, #e0e0e0);
}

.note-list__clear {
  padding: 0.5rem 0.75rem;
  background: transparent;
  border: 1px solid var(--color-border, #333);
  border-radius: 0.25rem;
  color: var(--color-text, #e0e0e0);
  cursor: pointer;
}

.note-list__folders {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.note-list__folder-btn {
  padding: 0.25rem 0.5rem;
  background: var(--color-surface, #1a1a1a);
  border: 1px solid var(--color-border, #333);
  border-radius: 0.25rem;
  color: var(--color-text, #e0e0e0);
  cursor: pointer;
  font-size: 0.85rem;
}

.note-list__folder-btn--active {
  background: var(--color-accent, #4a9eff);
  color: #fff;
}

.note-list__empty {
  color: var(--color-muted, #888);
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
  gap: 0.15rem;
  padding: 0.5rem;
  border-radius: 0.25rem;
  cursor: pointer;
}

.note-list__item:hover,
.note-list__item--active {
  background: var(--color-surface, #1a1a1a);
}

.note-list__item-title {
  font-weight: 500;
}

.note-list__item-tags {
  font-size: 0.8rem;
  color: var(--color-muted, #888);
}

.note-list__item-date {
  font-size: 0.75rem;
  color: var(--color-muted, #888);
}
</style>
