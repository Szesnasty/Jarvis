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
      <template v-for="node in tree" :key="nodeKey(node)">
        <!-- Plain note row -->
        <li
          v-if="node.kind === 'note'"
          class="note-list__item"
          :class="{ 'note-list__item--active': selectedPath === node.note.path }"
          @click="$emit('select', node.note.path)"
        >
          <div class="note-list__item-row">
            <span class="note-list__item-title">{{ node.note.title || node.note.path }}</span>
            <span
              v-if="hasPending(node.note.path)"
              class="note-list__sc-dot"
              title="Smart Connect suggestions pending review"
            ></span>
            <button
              class="note-list__delete"
              title="Delete note"
              @click.stop="confirmDelete(node.note)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
          <span v-if="node.note.tags.length" class="note-list__item-tags">{{ node.note.tags.join(', ') }}</span>
          <span class="note-list__item-date">{{ node.note.updated_at.slice(0, 10) }}</span>
        </li>

        <!-- Document row (PDF section split etc.) -->
        <template v-else>
          <li
            class="note-list__item note-list__item--document"
            :class="{ 'note-list__item--active': selectedPath === node.index.path }"
            @click="toggleDoc(node.index.path)"
          >
            <div class="note-list__item-row">
              <span
                class="note-list__chevron"
                :class="{ 'note-list__chevron--open': isExpanded(node.index.path) }"
                aria-hidden="true"
              >▸</span>
              <span class="note-list__item-title">{{ node.index.title || node.index.path }}</span>
              <span class="note-list__section-count">{{ node.sections.length }} {{ node.sections.length === 1 ? 'section' : 'sections' }}</span>
              <span
                v-if="documentHasPending(node)"
                class="note-list__sc-dot"
                title="Smart Connect suggestions pending review"
              ></span>
              <button
                class="note-list__open-index"
                title="Open document index"
                @click.stop="$emit('select', node.index.path)"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
              </button>
              <button
                class="note-list__delete"
                title="Delete document and all sections"
                @click.stop="confirmDeleteDocument(node)"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"/>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                  <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                </svg>
              </button>
            </div>
            <span class="note-list__item-date">{{ node.index.updated_at.slice(0, 10) }}</span>
          </li>

          <li
            v-for="section in (isExpanded(node.index.path) ? node.sections : [])"
            :key="section.path"
            class="note-list__item note-list__item--section"
            :class="{ 'note-list__item--active': selectedPath === section.path }"
            @click="$emit('select', section.path)"
          >
            <div class="note-list__item-row">
              <span class="note-list__section-num">{{ String(section.section_index ?? '').padStart(2, '0') }}</span>
              <span class="note-list__item-title">{{ section.title || section.path }}</span>
              <span
                v-if="hasPending(section.path)"
                class="note-list__sc-dot"
                title="Smart Connect suggestions pending review"
              ></span>
            </div>
          </li>
        </template>
      </template>
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

    <ConfirmDialog
      :visible="deleteDocTarget !== null"
      :loading="deleting"
      title="Delete document?"
      :message="`&quot;${deleteDocTarget?.index.title || ''}&quot; and ${deleteDocTarget?.sections.length ?? 0} section${(deleteDocTarget?.sections.length ?? 0) === 1 ? '' : 's'} will be permanently removed.`"
      confirm-label="Delete"
      @confirm="handleDeleteDocument"
      @cancel="deleteDocTarget = null"
    />
  </div>
</template>

<script setup lang="ts">
import type { NoteMetadata, NoteTreeNode } from '~/types'
import { buildNoteTree, sortNoteTreeByRecency } from '~/composables/useNoteTree'

type SearchMode = 'keyword' | 'semantic' | 'hybrid'

const props = defineProps<{
  notes: NoteMetadata[]
  selectedPath: string | null
  folders: string[]
  activeFolder: string | null
  loading?: boolean
  onDelete: (path: string) => Promise<void>
  /** Relative paths (inside memory/) that have pending Smart Connect suggestions. */
  pendingPaths?: Set<string>
}>()

const emit = defineEmits<{
  select: [path: string]
  folder: [folder: string | null]
  search: [query: string, mode: SearchMode]
}>()

const searchQuery = ref('')
const searchMode = ref<SearchMode>('keyword')
const deleteTarget = ref<NoteMetadata | null>(null)
type DocumentNode = Extract<NoteTreeNode, { kind: 'document' }>
const deleteDocTarget = ref<DocumentNode | null>(null)
const deleting = ref(false)

// Step 28b — group split documents (PDF / future) under one expandable row.
const tree = computed<NoteTreeNode[]>(() => sortNoteTreeByRecency(buildNoteTree(props.notes)))

// Per-document expanded state, persisted across Memory ↔ Graph navigation.
const expanded = useState<Record<string, boolean>>('noteTreeExpanded', () => ({}))

function nodeKey(node: NoteTreeNode): string {
  return node.kind === 'document' ? `doc:${node.index.path}` : `note:${node.note.path}`
}

function isExpanded(path: string): boolean {
  // Auto-expand every document while a search is active so matching sections
  // are visible without the user having to click each parent open.
  if (searchQuery.value.trim()) return true
  return !!expanded.value[path]
}

function toggleDoc(path: string) {
  expanded.value = { ...expanded.value, [path]: !expanded.value[path] }
}

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

function confirmDeleteDocument(node: DocumentNode) {
  deleteDocTarget.value = node
}

async function handleDeleteDocument() {
  const target = deleteDocTarget.value
  if (!target) return
  deleting.value = true
  try {
    // Sections first so the index doesn't briefly point at deleted children.
    for (const section of target.sections) {
      await props.onDelete(section.path)
    }
    await props.onDelete(target.index.path)
  } finally {
    deleting.value = false
    deleteDocTarget.value = null
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

/** Returns true if a note (or any section of a document) has pending SC suggestions. */
function hasPending(path: string): boolean {
  return props.pendingPaths?.has(path) ?? false
}

/** For document nodes: badge if any section OR the index note has suggestions. */
function documentHasPending(node: Extract<NoteTreeNode, { kind: 'document' }>): boolean {
  const pending = props.pendingPaths
  if (!pending) return false
  if (pending.has(node.index.path)) return true
  return node.sections.some(s => pending.has(s.path))
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

/* Step 28b — document grouping styles. */
.note-list__item--document {
  cursor: pointer;
}

.note-list__chevron {
  display: inline-block;
  flex-shrink: 0;
  width: 14px;
  font-size: 0.7rem;
  color: var(--text-muted);
  transition: transform 0.15s ease;
  line-height: 1;
}

.note-list__chevron--open {
  transform: rotate(90deg);
}

.note-list__open-index {
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

.note-list__item:hover .note-list__open-index {
  opacity: 0.6;
}

.note-list__open-index:hover {
  opacity: 1 !important;
  color: var(--neon-cyan);
  background: var(--bg-elevated);
}

.note-list__section-count {
  flex-shrink: 0;
  font-size: 0.7rem;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* Smart Connect pending-review badge — same style as spec-card__active-dot */
.note-list__sc-dot {
  flex-shrink: 0;
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--neon-cyan, #78dcff);
  border: 1.5px solid var(--bg-surface, #0e1117);
  box-shadow: 0 0 6px var(--neon-cyan-60, rgba(120, 220, 255, 0.6));
  cursor: default;
  animation: sc-dot-pulse 2s ease-in-out infinite;
  margin-left: 0.3rem;
  align-self: center;
}

@keyframes sc-dot-pulse {
  0%, 100% { box-shadow: 0 0 4px var(--neon-cyan-30, rgba(120, 220, 255, 0.3)); }
  50%       { box-shadow: 0 0 10px var(--neon-cyan-60, rgba(120, 220, 255, 0.6)); }
}

.note-list__item--document .note-list__item-title {
  font-weight: 600;
}

.note-list__item--section {
  margin-left: 1.25rem;
  padding-left: 0.6rem;
  border-left: 1px solid var(--border-subtle);
  border-radius: 0 8px 8px 0;
}

.note-list__item--section .note-list__item-row {
  gap: 0.5rem;
}

.note-list__item--section .note-list__item-title {
  font-weight: 400;
  font-size: 0.85rem;
  color: var(--text-secondary);
}

.note-list__item--section.note-list__item--active .note-list__item-title {
  color: var(--neon-cyan);
}

.note-list__section-num {
  flex-shrink: 0;
  font-size: 0.7rem;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  min-width: 1.5rem;
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
