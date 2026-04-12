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
  padding: 1.5rem;
  height: 100%;
  overflow-y: auto;
}

.note-viewer__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
}

.note-viewer__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 1rem;
}

.note-viewer__title {
  margin: 0;
  font-size: 1.5rem;
  color: var(--text-primary);
}

.note-viewer__date {
  font-size: 0.85rem;
  color: var(--text-muted);
}

.note-viewer__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1.25rem;
  padding-bottom: 0.85rem;
  border-bottom: 1px solid var(--border-default);
}

.note-viewer__meta-tag {
  font-size: 0.78rem;
  padding: 0.2rem 0.6rem;
  background: var(--neon-cyan-08);
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  color: var(--text-secondary);
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
  color: var(--text-primary);
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
  background: var(--bg-surface);
  padding: 0.15em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
  color: var(--neon-cyan);
}

.note-viewer__body :deep(pre) {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  padding: 1em;
  border-radius: 8px;
  overflow-x: auto;
}

.note-viewer__body :deep(pre code) {
  background: none;
  padding: 0;
  color: var(--text-primary);
}

.note-viewer__body :deep(blockquote) {
  border-left: 3px solid var(--neon-cyan-30);
  padding-left: 1em;
  margin-left: 0;
  color: var(--text-secondary);
}

.note-viewer__body :deep(a) {
  color: var(--neon-cyan-60);
  text-decoration: none;
}

.note-viewer__body :deep(a:hover) {
  color: var(--neon-cyan);
  text-shadow: 0 0 6px var(--neon-cyan-15);
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
