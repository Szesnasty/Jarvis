<template>
  <div class="note-viewer">
    <div v-if="!note" class="note-viewer__empty">
      <p>Select a note to view</p>
    </div>
    <div v-else class="note-viewer__content">
      <header class="note-viewer__header">
        <h2 class="note-viewer__title">{{ note.title }}</h2>
        <span class="note-viewer__date">{{ note.updated_at.slice(0, 10) }}</span>
      </header>
      <div v-if="note.frontmatter && Object.keys(note.frontmatter).length > 0" class="note-viewer__meta">
        <span
          v-for="(value, key) in note.frontmatter"
          :key="String(key)"
          class="note-viewer__meta-tag"
        >
          {{ key }}: {{ Array.isArray(value) ? value.join(', ') : value }}
        </span>
      </div>
      <pre class="note-viewer__body">{{ note.content }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { NoteDetail } from '~/types'

defineProps<{
  note: NoteDetail | null
}>()
</script>

<style scoped>
.note-viewer {
  padding: 1rem;
  height: 100%;
  overflow-y: auto;
}

.note-viewer__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--color-muted, #888);
}

.note-viewer__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.75rem;
}

.note-viewer__title {
  margin: 0;
  font-size: 1.5rem;
}

.note-viewer__date {
  font-size: 0.85rem;
  color: var(--color-muted, #888);
}

.note-viewer__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--color-border, #333);
}

.note-viewer__meta-tag {
  font-size: 0.8rem;
  padding: 0.15rem 0.5rem;
  background: var(--color-surface, #1a1a1a);
  border-radius: 0.25rem;
  color: var(--color-muted, #888);
}

.note-viewer__body {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
  font-size: 0.95rem;
  line-height: 1.6;
  margin: 0;
}
</style>
