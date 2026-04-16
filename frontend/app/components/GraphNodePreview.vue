<template>
  <aside class="node-preview">
    <div class="node-preview__header">
      <span class="node-preview__type-badge" :style="{ background: typeColor }">{{ node.type }}</span>
      <button class="node-preview__close" @click="$emit('close')">✕</button>
    </div>

    <h3 class="node-preview__title">{{ detail?.node.label ?? node.label }}</h3>
    <p v-if="node.folder" class="node-preview__folder">{{ node.folder }}</p>

    <!-- Loading state -->
    <div v-if="loading" class="node-preview__loading">Loading…</div>

    <template v-if="detail && !loading">
      <!-- Preview text for notes -->
      <div v-if="renderedPreview" class="node-preview__excerpt-wrapper">
        <div
          class="node-preview__excerpt prose-sm"
          :class="{ 'node-preview__excerpt--collapsed': !expanded }"
          v-html="renderedPreview"
        ></div>
        <button
          v-if="isLongPreview"
          class="node-preview__expand-btn"
          @click="expanded = !expanded"
        >{{ expanded ? 'Collapse ▲' : 'Show more ▼' }}</button>
      </div>

      <!-- Stats -->
      <div class="node-preview__stats">
        <span>{{ detail.degree }} connections</span>
        <span>{{ detail.neighbor_count }} neighbors</span>
      </div>

      <!-- Connected tags -->
      <div v-if="detail.connected_tags.length" class="node-preview__section">
        <h4 class="node-preview__section-label">Tags</h4>
        <div class="node-preview__chips">
          <button
            v-for="tag in detail.connected_tags"
            :key="tag"
            class="node-preview__chip node-preview__chip--tag"
            @click="$emit('navigate-node', `tag:${tag}`)"
          >{{ tag }}</button>
        </div>
      </div>

      <!-- Connected people -->
      <div v-if="detail.connected_people.length" class="node-preview__section">
        <h4 class="node-preview__section-label">People</h4>
        <div class="node-preview__chips">
          <button
            v-for="person in detail.connected_people"
            :key="person"
            class="node-preview__chip node-preview__chip--person"
            @click="$emit('navigate-node', `person:${person}`)"
          >{{ person }}</button>
        </div>
      </div>

      <!-- Connected notes -->
      <div v-if="detail.connected_notes.length" class="node-preview__section">
        <h4 class="node-preview__section-label">Notes</h4>
        <ul class="node-preview__note-list">
          <li
            v-for="n in detail.connected_notes.slice(0, 8)"
            :key="n.id"
            class="node-preview__note-item"
            @click="$emit('navigate-node', n.id)"
          >{{ n.label }}</li>
        </ul>
      </div>

      <!-- Semantic connections -->
      <div v-if="similarEdges?.length" class="node-preview__section">
        <h4 class="node-preview__section-label">Semantic Connections</h4>
        <ul class="node-preview__note-list">
          <li
            v-for="edge in similarEdges.slice(0, 5)"
            :key="`${edge.source}-${edge.target}`"
            class="node-preview__semantic-item"
            @click="$emit('navigate-node', otherNodeId(edge))"
          >
            <span class="node-preview__semantic-label">{{ otherNodeLabel(edge) }}</span>
            <span class="node-preview__semantic-weight">{{ Math.round((edge.weight ?? 0) * 100) }}%</span>
          </li>
        </ul>
      </div>

      <!-- Actions -->
      <div class="node-preview__actions">
        <button class="node-preview__action-btn" @click="$emit('ask-about', node.id)">
          Ask about this
        </button>
        <button
          v-if="node.type === 'note'"
          class="node-preview__action-btn node-preview__action-btn--secondary"
          @click="$emit('open-in-memory', node.id.replace('note:', ''))"
        >
          Open in Memory
        </button>
      </div>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { GraphNode, GraphNodeDetail, GraphEdge } from '~/types'
import { useApi } from '~/composables/useApi'

const props = defineProps<{
  node: GraphNode
  similarEdges?: GraphEdge[]
}>()

defineEmits<{
  close: []
  'navigate-node': [nodeId: string]
  'ask-about': [nodeId: string]
  'open-in-memory': [path: string]
}>()

const { fetchNodeDetail } = useApi()
const detail = ref<GraphNodeDetail | null>(null)
const loading = ref(false)
const expanded = ref(false)

const typeColor: Record<string, string> = {
  note: 'rgba(2, 254, 255, 0.25)',
  tag: 'rgba(52, 211, 153, 0.25)',
  person: 'rgba(192, 132, 252, 0.25)',
  area: 'rgba(251, 146, 60, 0.25)',
}

const renderedPreview = computed(() => {
  if (!detail.value?.preview) return ''
  const raw = marked.parse(detail.value.preview, { async: false, breaks: true, gfm: true }) as string
  return DOMPurify.sanitize(raw)
})

const isLongPreview = computed(() => (detail.value?.preview?.length ?? 0) > 300)

async function loadDetail(nodeId: string) {
  loading.value = true
  detail.value = null
  expanded.value = false
  try {
    detail.value = await fetchNodeDetail(nodeId)
  } catch {
    // silently fail — the header info is enough
  } finally {
    loading.value = false
  }
}

watch(() => props.node.id, (id) => loadDetail(id), { immediate: true })

function otherNodeId(edge: GraphEdge): string {
  return edge.source === props.node.id ? edge.target : edge.source
}

function otherNodeLabel(edge: GraphEdge): string {
  const id = otherNodeId(edge)
  // Strip prefix like "note:" or "tag:"
  const colon = id.indexOf(':')
  return colon >= 0 ? id.slice(colon + 1) : id
}
</script>

<style scoped>
.node-preview {
  width: 280px;
  border-left: 1px solid var(--border-default);
  background: var(--bg-base);
  padding: 1rem;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.node-preview__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.node-preview__type-badge {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  color: var(--text-secondary);
}

.node-preview__close {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.2rem;
}

.node-preview__close:hover {
  color: var(--text-primary);
}

.node-preview__title {
  font-size: 1rem;
  margin: 0;
  color: var(--neon-cyan);
  line-height: 1.3;
}

.node-preview__folder {
  font-size: 0.7rem;
  color: var(--text-muted);
  margin: 0;
}

.node-preview__loading {
  font-size: 0.75rem;
  color: var(--text-muted);
  font-style: italic;
}

.node-preview__excerpt-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.node-preview__excerpt {
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
  border-left: 2px solid var(--neon-cyan-30);
  padding-left: 0.6rem;
  overflow-y: auto;
}

.node-preview__excerpt--collapsed {
  max-height: 120px;
  overflow: hidden;
  mask-image: linear-gradient(to bottom, black 60%, transparent 100%);
  -webkit-mask-image: linear-gradient(to bottom, black 60%, transparent 100%);
}

.node-preview__expand-btn {
  background: none;
  border: none;
  color: var(--neon-cyan);
  font-size: 0.7rem;
  cursor: pointer;
  padding: 0.15rem 0;
  text-align: left;
  opacity: 0.8;
  transition: opacity 0.15s;
}

.node-preview__expand-btn:hover {
  opacity: 1;
}

.node-preview__excerpt :deep(p) {
  margin: 0.25rem 0;
}

.node-preview__excerpt :deep(strong) {
  color: var(--text-primary);
  font-weight: 600;
}

.node-preview__excerpt :deep(em) {
  color: var(--text-secondary);
}

.node-preview__excerpt :deep(h1),
.node-preview__excerpt :deep(h2),
.node-preview__excerpt :deep(h3) {
  font-size: 0.85rem;
  margin: 0.3rem 0 0.15rem;
  color: var(--text-primary);
}

.node-preview__excerpt :deep(ul),
.node-preview__excerpt :deep(ol) {
  margin: 0.2rem 0;
  padding-left: 1.2rem;
}

.node-preview__excerpt :deep(code) {
  font-size: 0.72rem;
  background: var(--bg-surface);
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
}

.node-preview__stats {
  display: flex;
  gap: 1rem;
  font-size: 0.7rem;
  color: var(--text-muted);
}

.node-preview__section {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.node-preview__section-label {
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  margin: 0;
}

.node-preview__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.node-preview__chip {
  font-size: 0.7rem;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.node-preview__chip:hover {
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan);
}

.node-preview__chip--tag {
  border-color: rgba(52, 211, 153, 0.2);
}

.node-preview__chip--person {
  border-color: rgba(192, 132, 252, 0.2);
}

.node-preview__note-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.node-preview__note-item {
  font-size: 0.75rem;
  color: var(--text-secondary);
  padding: 0.25rem 0.4rem;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}

.node-preview__note-item:hover {
  background: var(--bg-surface);
  color: var(--neon-cyan);
}

.node-preview__actions {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: auto;
  padding-top: 0.5rem;
}

.node-preview__action-btn {
  font-size: 0.78rem;
  padding: 0.45rem 0.75rem;
  border-radius: 6px;
  border: 1px solid var(--neon-cyan-30);
  background: rgba(2, 254, 255, 0.08);
  color: var(--neon-cyan);
  cursor: pointer;
  transition: all 0.2s;
  text-align: center;
}

.node-preview__action-btn:hover {
  background: rgba(2, 254, 255, 0.15);
  box-shadow: 0 0 12px rgba(2, 254, 255, 0.1);
}

.node-preview__action-btn--secondary {
  border-color: var(--border-default);
  background: transparent;
  color: var(--text-secondary);
}

.node-preview__action-btn--secondary:hover {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
}

.node-preview__semantic-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.25rem 0;
  cursor: pointer;
  border-radius: 4px;
  transition: background 0.15s;
}

.node-preview__semantic-item:hover {
  background: var(--bg-surface);
}

.node-preview__semantic-label {
  font-size: 0.75rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.node-preview__semantic-weight {
  font-size: 0.65rem;
  color: rgba(165, 180, 252, 0.8);
  font-weight: 600;
  margin-left: 0.5rem;
  flex-shrink: 0;
}
</style>
