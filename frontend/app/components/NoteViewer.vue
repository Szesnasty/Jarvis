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
      <div v-if="note.frontmatter && Object.keys(filteredFrontmatter).length > 0" class="note-viewer__meta">
        <span
          v-for="(value, key) in filteredFrontmatter"
          :key="String(key)"
          class="note-viewer__meta-tag"
        >
          {{ key }}: {{ Array.isArray(value) ? value.join(', ') : value }}
        </span>
      </div>
      <!-- Step 29 — ownership panel -->
      <div class="note-viewer__ownership" v-click-outside="closeDropdown">
        <span class="note-viewer__owner-label">Owned by:</span>

        <!-- current owner chips (each clickable to remove) -->
        <button
          v-for="specId in ownerSpecialists"
          :key="specId"
          class="note-viewer__owner-chip is-spec"
          :title="`Remove ${specialistLabel(specId)}`"
          :disabled="savingOwnership"
          @click="removeOwner(specId)"
        >{{ specialistLabel(specId) }} ×</button>

        <!-- visibility pill -->
        <span
          v-if="ownerSpecialists.length"
          class="note-viewer__owner-chip"
          :class="{ 'is-private': visibility === 'private' }"
        >{{ visibility }}</span>

        <!-- empty state -->
        <span v-if="!ownerSpecialists.length" class="note-viewer__owner-empty">shared with everyone</span>

        <!-- add-specialist trigger -->
        <div class="note-viewer__owner-add-wrap">
          <button
            v-if="availableSpecialists.length"
            class="note-viewer__owner-add-btn"
            :disabled="savingOwnership"
            @click.stop="dropdownOpen = !dropdownOpen"
          >+ Assign</button>

          <!-- dropdown -->
          <div v-if="dropdownOpen" class="note-viewer__owner-dropdown">
            <label class="note-viewer__owner-dropdown-priv">
              <input v-model="pendingPrivate" type="checkbox" />
              Private (only these specialists)
            </label>
            <button
              v-for="spec in availableSpecialists"
              :key="spec.id"
              class="note-viewer__owner-dropdown-item"
              :class="{ 'is-selected': pendingSelected.includes(spec.id) }"
              @click.stop="togglePending(spec.id)"
            >
              <span class="note-viewer__owner-dropdown-icon">{{ spec.icon }}</span>
              {{ spec.name }}
              <span v-if="pendingSelected.includes(spec.id)" class="note-viewer__owner-dropdown-check">✓</span>
            </button>
            <div class="note-viewer__owner-dropdown-actions">
              <button class="note-viewer__owner-dropdown-save" :disabled="!pendingSelected.length || savingOwnership" @click="applyPending">Apply</button>
              <button class="note-viewer__owner-dropdown-cancel" @click="closeDropdown">Cancel</button>
            </div>
          </div>
        </div>

        <!-- clear button -->
        <button
          v-if="ownerSpecialists.length"
          class="note-viewer__owner-clear"
          :disabled="savingOwnership"
          @click="clearOwnership"
        >Make shared</button>
      </div>
      <SuggestionsPanel
        :note="note"
        @open="(p: string) => $emit('open', p)"
        @changed="$emit('changed')"
      />
      <div class="note-viewer__body prose" v-html="renderedHtml"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { NoteDetail, SpecialistSummary } from '~/types'
import { useApi } from '~/composables/useApi'

const props = defineProps<{
  note: NoteDetail | null
  specialists?: SpecialistSummary[]
  activeSpecialistId?: string | null
}>()

const emit = defineEmits<{
  (e: 'open', path: string): void
  (e: 'changed'): void
}>()

const { updateNoteOwnership } = useApi()
const savingOwnership = ref(false)
const dropdownOpen = ref(false)
const pendingSelected = ref<string[]>([])
const pendingPrivate = ref(true)

const ownerSpecialists = computed<string[]>(() => {
  const fm = props.note?.frontmatter as Record<string, unknown> | undefined
  const raw = fm?.specialists
  return Array.isArray(raw) ? (raw as string[]) : []
})

const visibility = computed<'shared' | 'private'>(() => {
  const fm = props.note?.frontmatter as Record<string, unknown> | undefined
  return fm?.visibility === 'private' ? 'private' : 'shared'
})

const availableSpecialists = computed(() =>
  (props.specialists ?? []).filter((s) => !ownerSpecialists.value.includes(s.id))
)

function specialistLabel(id: string): string {
  return (props.specialists ?? []).find((s) => s.id === id)?.name ?? id
}

function openDropdown() {
  pendingSelected.value = []
  pendingPrivate.value = true
  dropdownOpen.value = true
}

function closeDropdown() {
  dropdownOpen.value = false
}

function togglePending(id: string) {
  const idx = pendingSelected.value.indexOf(id)
  if (idx === -1) pendingSelected.value.push(id)
  else pendingSelected.value.splice(idx, 1)
}

async function applyPending() {
  if (!props.note || !pendingSelected.value.length || savingOwnership.value) return
  savingOwnership.value = true
  dropdownOpen.value = false
  try {
    const newOwners = [...new Set([...ownerSpecialists.value, ...pendingSelected.value])]
    await updateNoteOwnership(props.note.path, {
      specialists: newOwners,
      visibility: pendingPrivate.value ? 'private' : 'shared',
    })
    emit('changed')
  } finally {
    savingOwnership.value = false
    pendingSelected.value = []
  }
}

async function removeOwner(specId: string) {
  if (!props.note || savingOwnership.value) return
  savingOwnership.value = true
  try {
    const newOwners = ownerSpecialists.value.filter((id) => id !== specId)
    await updateNoteOwnership(props.note.path, {
      specialists: newOwners,
      visibility: newOwners.length ? visibility.value : 'shared',
    })
    emit('changed')
  } finally {
    savingOwnership.value = false
  }
}

async function clearOwnership() {
  if (!props.note || savingOwnership.value) return
  savingOwnership.value = true
  try {
    await updateNoteOwnership(props.note.path, { specialists: [], visibility: 'shared' })
    emit('changed')
  } finally {
    savingOwnership.value = false
  }
}

// v-click-outside directive
const vClickOutside = {
  mounted(el: HTMLElement, binding: { value: () => void }) {
    ;(el as any).__clickOutside = (e: MouseEvent) => {
      if (!el.contains(e.target as Node)) binding.value()
    }
    setTimeout(() => document.addEventListener('click', (el as any).__clickOutside), 0)
  },
  unmounted(el: HTMLElement) {
    document.removeEventListener('click', (el as any).__clickOutside)
  },
}

// Smart Connect output hidden from raw frontmatter chip strip.
const HIDDEN_FRONTMATTER_KEYS = new Set(['suggested_related', 'aliases_matched', 'specialists', 'visibility'])

const filteredFrontmatter = computed(() => {
  const fm = props.note?.frontmatter ?? {}
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(fm)) {
    if (!HIDDEN_FRONTMATTER_KEYS.has(k)) out[k] = v
  }
  return out
})

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

/* Step 29 — ownership panel */
.note-viewer__ownership {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 1.25rem;
  padding-bottom: 0.85rem;
  border-bottom: 1px solid var(--border-default);
  position: relative;
}

.note-viewer__owner-label {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

.note-viewer__owner-empty {
  font-size: 0.78rem;
  color: var(--text-muted);
  font-style: italic;
}

/* chip used for both visibility pill and specialist names */
.note-viewer__owner-chip {
  font-size: 0.78rem;
  padding: 0.18rem 0.55rem;
  border-radius: 6px;
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  color: var(--text-secondary);
  cursor: default;
}

/* specialist chips are also buttons — add hover for remove */
button.note-viewer__owner-chip {
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
button.note-viewer__owner-chip:hover:not(:disabled) {
  background: var(--neon-pink-08, rgba(255, 64, 128, 0.12));
  color: var(--neon-pink, #ff4080);
  border-color: var(--neon-pink, #ff4080);
}

.note-viewer__owner-chip.is-private {
  background: var(--neon-pink-08, rgba(255, 64, 128, 0.08));
  color: var(--neon-pink, #ff4080);
  border-color: var(--neon-pink, #ff4080);
}

.note-viewer__owner-chip.is-spec {
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
  border-color: var(--neon-cyan);
}

/* + Assign button */
.note-viewer__owner-add-wrap {
  position: relative;
}

.note-viewer__owner-add-btn {
  font-size: 0.78rem;
  padding: 0.18rem 0.6rem;
  background: transparent;
  border: 1px dashed var(--border-default);
  color: var(--text-muted);
  border-radius: 6px;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
}
.note-viewer__owner-add-btn:hover:not(:disabled) {
  color: var(--neon-cyan);
  border-color: var(--neon-cyan);
}

/* dropdown */
.note-viewer__owner-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 200;
  min-width: 210px;
  background: var(--bg-elevated, #1a1a2e);
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 0.5rem 0;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}

.note-viewer__owner-dropdown-priv {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.75rem;
  font-size: 0.78rem;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 1px solid var(--border-subtle);
  margin-bottom: 0.25rem;
}
.note-viewer__owner-dropdown-priv input {
  accent-color: var(--neon-cyan);
}

.note-viewer__owner-dropdown-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  width: 100%;
  padding: 0.4rem 0.75rem;
  font-size: 0.85rem;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s;
}
.note-viewer__owner-dropdown-item:hover {
  background: var(--bg-hover, rgba(255,255,255,0.05));
  color: var(--text-primary);
}
.note-viewer__owner-dropdown-item.is-selected {
  color: var(--neon-cyan);
}

.note-viewer__owner-dropdown-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

.note-viewer__owner-dropdown-check {
  margin-left: auto;
  color: var(--neon-cyan);
  font-size: 0.8rem;
}

.note-viewer__owner-dropdown-actions {
  display: flex;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem 0.25rem;
  border-top: 1px solid var(--border-subtle);
  margin-top: 0.25rem;
}

.note-viewer__owner-dropdown-save {
  flex: 1;
  padding: 0.3rem 0.75rem;
  font-size: 0.8rem;
  background: var(--neon-cyan);
  color: #000;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-weight: 600;
}
.note-viewer__owner-dropdown-save:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.note-viewer__owner-dropdown-cancel {
  padding: 0.3rem 0.75rem;
  font-size: 0.8rem;
  background: transparent;
  border: 1px solid var(--border-default);
  color: var(--text-muted);
  border-radius: 5px;
  cursor: pointer;
}

/* Make shared link */
.note-viewer__owner-clear {
  margin-left: auto;
  font-size: 0.75rem;
  padding: 0.18rem 0.55rem;
  background: transparent;
  border: 1px solid var(--border-subtle);
  color: var(--text-muted);
  border-radius: 6px;
  cursor: pointer;
}
.note-viewer__owner-clear:hover:not(:disabled) {
  color: var(--neon-pink, #ff4080);
  border-color: var(--neon-pink, #ff4080);
}
.note-viewer__owner-clear:disabled { opacity: 0.4; cursor: not-allowed; }

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
