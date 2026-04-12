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
      <div class="note-viewer__body prose" v-html="renderedHtml"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { NoteDetail } from '~/types'

const props = defineProps<{
  note: NoteDetail | null
}>()

function stripFrontmatter(content: string): string {
  const match = content.match(/^---\s*\n[\s\S]*?\n---\s*\n?/)
  return match ? content.slice(match[0].length) : content
}

const renderedHtml = computed(() => {
  if (!props.note?.content) return ''
  const body = stripFrontmatter(props.note.content)
  const raw = marked.parse(body, { async: false }) as string
  return DOMPurify.sanitize(raw)
})
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
  font-size: 0.95rem;
  line-height: 1.7;
  margin: 0;
}

.note-viewer__body :deep(h1),
.note-viewer__body :deep(h2),
.note-viewer__body :deep(h3) {
  margin-top: 1.5em;
  margin-bottom: 0.5em;
}

.note-viewer__body :deep(p) {
  margin: 0.75em 0;
}

.note-viewer__body :deep(ul),
.note-viewer__body :deep(ol) {
  padding-left: 1.5em;
  margin: 0.5em 0;
}

.note-viewer__body :deep(code) {
  background: var(--color-surface, #1a1a1a);
  padding: 0.15em 0.4em;
  border-radius: 0.25rem;
  font-size: 0.9em;
}

.note-viewer__body :deep(pre) {
  background: var(--color-surface, #1a1a1a);
  padding: 1em;
  border-radius: 0.5rem;
  overflow-x: auto;
}

.note-viewer__body :deep(pre code) {
  background: none;
  padding: 0;
}

.note-viewer__body :deep(blockquote) {
  border-left: 3px solid var(--color-muted, #888);
  padding-left: 1em;
  margin-left: 0;
  color: var(--color-muted, #888);
}

.note-viewer__body :deep(a) {
  color: var(--color-accent, #4a9eff);
  text-decoration: none;
}

.note-viewer__body :deep(a:hover) {
  text-decoration: underline;
}

.note-viewer__body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 0.75em 0;
}

.note-viewer__body :deep(th),
.note-viewer__body :deep(td) {
  border: 1px solid var(--color-border, #333);
  padding: 0.5em 0.75em;
  text-align: left;
}

.note-viewer__body :deep(input[type="checkbox"]) {
  margin-right: 0.5em;
}
</style>
