<template>
  <div class="filter-bar">
    <div class="filter-bar__group">
      <label class="filter-bar__toggle" v-for="t in nodeTypes" :key="t.type">
        <input type="checkbox" :checked="t.enabled" @change="toggleType(t.type)" />
        <span class="filter-bar__toggle-dot" :style="{ background: t.color }"></span>
        <span class="filter-bar__toggle-label">{{ t.label }}</span>
      </label>
    </div>

    <div class="filter-bar__group">
      <select class="filter-bar__select" :value="filters.timeRange" @change="$emit('update:filters', { ...filters, timeRange: ($event.target as HTMLSelectElement).value })">
        <option value="all">All time</option>
        <option value="7d">Last 7 days</option>
        <option value="30d">Last 30 days</option>
        <option value="90d">Last 90 days</option>
      </select>
    </div>

    <div v-if="sprintOptions.length > 0" class="filter-bar__sprints" ref="sprintMenuRef">
      <button
        type="button"
        class="filter-bar__sprint-btn"
        :class="{ 'filter-bar__sprint-btn--active': filters.selectedSprints.size > 0 }"
        @click="sprintMenuOpen = !sprintMenuOpen"
      >
        <span class="filter-bar__sprint-dot"></span>
        <span v-if="filters.selectedSprints.size === 0">Sprints</span>
        <span v-else>Sprints · {{ filters.selectedSprints.size }}</span>
        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true"><path d="M2 3.5 L5 6.5 L8 3.5" fill="none" stroke="currentColor" stroke-width="1.2" /></svg>
      </button>
      <div v-if="sprintMenuOpen" class="filter-bar__sprint-menu">
        <div class="filter-bar__sprint-menu-head">
          <span>{{ sprintOptions.length }} sprint{{ sprintOptions.length === 1 ? '' : 's' }}</span>
          <button
            type="button"
            class="filter-bar__sprint-clear"
            :disabled="filters.selectedSprints.size === 0"
            @click="clearSprints"
          >Clear</button>
        </div>
        <div class="filter-bar__sprint-list">
          <label
            v-for="s in sprintOptions"
            :key="s.id"
            class="filter-bar__sprint-row"
          >
            <input
              type="checkbox"
              :checked="filters.selectedSprints.has(s.id)"
              @change="toggleSprint(s.id)"
            />
            <span class="filter-bar__sprint-label">{{ s.label }}</span>
            <span
              v-if="s.state"
              class="filter-bar__sprint-state"
              :class="`filter-bar__sprint-state--${s.state}`"
            >{{ s.state }}</span>
            <button
              type="button"
              class="filter-bar__sprint-only"
              title="Select only this sprint"
              @click.prevent.stop="selectOnly(s.id)"
            >only</button>
          </label>
        </div>
      </div>
    </div>

    <button
      class="filter-bar__orphan-btn"
      :class="{ 'filter-bar__orphan-btn--active': filters.showOrphans }"
      @click="$emit('update:filters', { ...filters, showOrphans: !filters.showOrphans })"
    >
      <span v-if="orphanCount > 0" class="filter-bar__orphan-count">{{ orphanCount }}</span>
      Orphans
    </button>

    <button
      class="filter-bar__orphan-btn"
      :class="{ 'filter-bar__orphan-btn--active': filters.hideHubs }"
      :title="`Hide nodes with more than ${filters.hubThreshold} edges (folder/index hubs)`"
      @click="$emit('update:filters', { ...filters, hideHubs: !filters.hideHubs })"
    >
      Hide hubs
    </button>

    <button
      class="filter-bar__glow-btn"
      :title="`Node glow: ${filters.glowLevel}`"
      @click="cycleGlow"
    >
      <span class="filter-bar__glow-dot" :class="`filter-bar__glow-dot--${filters.glowLevel}`"></span>
      Glow: {{ filters.glowLevel }}
    </button>

    <input
      class="filter-bar__search"
      type="text"
      placeholder="Search nodes…"
      :value="filters.searchText"
      @input="$emit('update:filters', { ...filters, searchText: ($event.target as HTMLInputElement).value })"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import type { GraphNode } from '~/types'

export interface GraphFilters {
  hiddenTypes: Set<string>
  timeRange: string
  showOrphans: boolean
  searchText: string
  /** Selected sprint node ids (e.g. "sprint:sprint-42"). Empty set = show all sprints. */
  selectedSprints: Set<string>
  /** Node glow intensity: off (pure perf), normal (current), high (full bloom), mono (elegant b/w). */
  glowLevel: 'off' | 'normal' | 'high' | 'mono'
  /** Hide nodes whose edge degree exceeds {@link hubThreshold} — kills folder/index hubs that drown real links. */
  hideHubs: boolean
  /** Edge-count above which a node is treated as a hub and hidden. */
  hubThreshold: number
}

// Canonical display names and colors for known node types.
// Types not listed here get an auto-generated label and grey dot.
const TYPE_META: Record<string, { label: string; color: string }> = {
  note:           { label: 'Notes',      color: 'rgba(2, 254, 255, 1)' },
  tag:            { label: 'Tags',       color: '#34d399' },
  person:         { label: 'People',     color: '#c084fc' },
  area:           { label: 'Areas',      color: '#fb923c' },
  org:            { label: 'Org',        color: '#facc15' },
  project:        { label: 'Project',    color: '#f472b6' },
  place:          { label: 'Places',     color: '#22d3ee' },
  source:         { label: 'Source',     color: '#a3e635' },
  batch:          { label: 'Batch',      color: '#94a3b8' },
  jira_issue:     { label: 'Issues',     color: '#60a5fa' },
  jira_epic:      { label: 'Epics',      color: '#f472b6' },
  jira_project:   { label: 'Projects',   color: '#facc15' },
  jira_person:    { label: 'Jira People', color: '#c084fc' },
  jira_sprint:    { label: 'Sprints',    color: '#22d3ee' },
  jira_label:     { label: 'Labels',     color: '#a3e635' },
  jira_component: { label: 'Components', color: '#f97316' },
}

// Preferred display order — types listed first appear first in the bar.
const TYPE_ORDER: string[] = [
  'note', 'tag', 'person', 'area', 'org', 'project', 'place', 'source', 'batch',
  'jira_issue', 'jira_epic', 'jira_sprint', 'jira_project',
  'jira_person', 'jira_label', 'jira_component',
]

const props = defineProps<{
  filters: GraphFilters
  orphanCount: number
  /** All nodes currently loaded — used to auto-discover which types exist. */
  allNodes: GraphNode[]
}>()

const emit = defineEmits<{
  'update:filters': [filters: GraphFilters]
}>()

function toggleType(type: string) {
  const next = new Set(props.filters.hiddenTypes)
  if (next.has(type)) {
    next.delete(type)
  } else {
    next.add(type)
  }
  emit('update:filters', { ...props.filters, hiddenTypes: next })
}

// --- Sprint multi-select ---------------------------------------------------
const sprintMenuOpen = ref(false)
const sprintMenuRef = ref<HTMLDivElement | null>(null)

interface SprintOption {
  id: string
  label: string
  state: string // "active" | "closed" | "future" | ""
  number: number // parsed sprint number for sorting, -Infinity if unknown
}

const sprintOptions = computed<SprintOption[]>(() => {
  const sprints = props.allNodes.filter(n => n.type === 'jira_sprint')
  const opts: SprintOption[] = sprints.map(n => {
    const m = n.label.match(/(\d+)/)
    const num = m ? parseInt(m[1], 10) : Number.NEGATIVE_INFINITY
    return { id: n.id, label: n.label, state: n.folder || '', number: num }
  })
  // Newest (highest number) first; active sprints bubble up on ties.
  opts.sort((a, b) => {
    if (b.number !== a.number) return b.number - a.number
    if (a.state === 'active' && b.state !== 'active') return -1
    if (b.state === 'active' && a.state !== 'active') return 1
    return a.label.localeCompare(b.label)
  })
  return opts
})

function toggleSprint(id: string) {
  const next = new Set(props.filters.selectedSprints)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  emit('update:filters', { ...props.filters, selectedSprints: next })
}

function clearSprints() {
  emit('update:filters', { ...props.filters, selectedSprints: new Set<string>() })
}

function selectOnly(id: string) {
  emit('update:filters', { ...props.filters, selectedSprints: new Set([id]) })
}

function onDocClick(ev: MouseEvent) {
  if (!sprintMenuOpen.value) return
  const el = sprintMenuRef.value
  if (el && !el.contains(ev.target as Node)) sprintMenuOpen.value = false
}
onMounted(() => document.addEventListener('mousedown', onDocClick))
onBeforeUnmount(() => document.removeEventListener('mousedown', onDocClick))

// --- Glow cycle ------------------------------------------------------------
function cycleGlow() {
  const order: GraphFilters['glowLevel'][] = ['off', 'normal', 'high', 'mono']
  const i = order.indexOf(props.filters.glowLevel)
  const next = order[(i + 1) % order.length]
  emit('update:filters', { ...props.filters, glowLevel: next })
}

const nodeTypes = computed(() => {
  // Discover types actually present in the data.
  const present = new Set(props.allNodes.map(n => n.type))
  // Sort: known types in preferred order first, then any extras alphabetically.
  const sorted = [...present].sort((a, b) => {
    const ai = TYPE_ORDER.indexOf(a)
    const bi = TYPE_ORDER.indexOf(b)
    if (ai >= 0 && bi >= 0) return ai - bi
    if (ai >= 0) return -1
    if (bi >= 0) return 1
    return a.localeCompare(b)
  })
  return sorted.map(type => {
    const meta = TYPE_META[type]
    return {
      type,
      label: meta?.label ?? type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
      color: meta?.color ?? '#9ca3af',
      enabled: !props.filters.hiddenTypes.has(type),
    }
  })
})
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.4rem 1.25rem;
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-surface);
  flex-wrap: wrap;
}

.filter-bar__group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.filter-bar__toggle {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  cursor: pointer;
  font-size: 0.72rem;
  color: var(--text-secondary);
  user-select: none;
}

.filter-bar__toggle input {
  display: none;
}

.filter-bar__toggle-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  transition: opacity 0.15s;
}

.filter-bar__toggle input:not(:checked) ~ .filter-bar__toggle-dot {
  opacity: 0.25;
}

.filter-bar__toggle input:not(:checked) ~ .filter-bar__toggle-label {
  opacity: 0.4;
  text-decoration: line-through;
}

.filter-bar__select {
  font-size: 0.72rem;
  padding: 0.2rem 0.4rem;
  background: var(--bg-base);
  border: 1px solid var(--border-default);
  border-radius: 4px;
  color: var(--text-secondary);
  cursor: pointer;
}

.filter-bar__orphan-btn {
  font-size: 0.72rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  border: 1px solid var(--border-default);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.3rem;
  transition: all 0.15s;
}

.filter-bar__orphan-btn:hover {
  border-color: var(--neon-cyan-30);
  color: var(--text-secondary);
}

.filter-bar__orphan-btn--active {
  border-color: rgba(251, 113, 133, 0.5);
  color: rgb(251, 113, 133);
  background: rgba(251, 113, 133, 0.08);
}

.filter-bar__orphan-count {
  font-size: 0.65rem;
  background: rgba(251, 113, 133, 0.2);
  color: rgb(251, 113, 133);
  padding: 0.05rem 0.35rem;
  border-radius: 8px;
  min-width: 1rem;
  text-align: center;
}

.filter-bar__search {
  font-size: 0.72rem;
  padding: 0.2rem 0.5rem;
  background: var(--bg-base);
  border: 1px solid var(--border-default);
  border-radius: 4px;
  color: var(--text-primary);
  margin-left: auto;
  width: 140px;
  transition: all 0.15s;
}

.filter-bar__search:focus {
  outline: none;
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 8px var(--neon-cyan-08);
}

/* --- Glow toggle --- */
.filter-bar__glow-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  border: 1px solid var(--border-default);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  text-transform: capitalize;
}
.filter-bar__glow-btn:hover {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
}
.filter-bar__glow-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22d3ee;
  transition: box-shadow 0.15s;
}
.filter-bar__glow-dot--off {
  background: rgba(148, 163, 184, 0.6);
  box-shadow: none;
}
.filter-bar__glow-dot--normal {
  background: #22d3ee;
  box-shadow: 0 0 4px rgba(34, 211, 238, 0.6);
}
.filter-bar__glow-dot--high {
  background: #22d3ee;
  box-shadow: 0 0 10px rgba(34, 211, 238, 1), 0 0 16px rgba(34, 211, 238, 0.6);
}
.filter-bar__glow-dot--mono {
  background: #f5f5f5;
  box-shadow: none;
  border: 1px solid rgba(255, 255, 255, 0.3);
}

/* --- Sprint multi-select --- */
.filter-bar__sprints {
  position: relative;
}

.filter-bar__sprint-btn {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  border: 1px solid var(--border-default);
  background: var(--bg-base);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.filter-bar__sprint-btn:hover {
  border-color: var(--neon-cyan-30);
  color: var(--text-primary);
}

.filter-bar__sprint-btn--active {
  border-color: rgba(34, 211, 238, 0.6);
  color: rgb(34, 211, 238);
  background: rgba(34, 211, 238, 0.08);
}

.filter-bar__sprint-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22d3ee;
}

.filter-bar__sprint-menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 40;
  min-width: 240px;
  max-width: 320px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  overflow: hidden;
}

.filter-bar__sprint-menu-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 0.6rem;
  font-size: 0.68rem;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-default);
  background: var(--bg-base);
}

.filter-bar__sprint-clear {
  font-size: 0.68rem;
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0.1rem 0.3rem;
  border-radius: 3px;
}
.filter-bar__sprint-clear:not(:disabled):hover {
  color: rgb(251, 113, 133);
}
.filter-bar__sprint-clear:disabled {
  opacity: 0.3;
  cursor: default;
}

.filter-bar__sprint-list {
  max-height: 320px;
  overflow-y: auto;
  padding: 0.25rem 0;
}

.filter-bar__sprint-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.25rem 0.6rem;
  font-size: 0.72rem;
  color: var(--text-secondary);
  cursor: pointer;
  user-select: none;
}
.filter-bar__sprint-row:hover {
  background: var(--bg-base);
}
.filter-bar__sprint-row input {
  margin: 0;
  accent-color: #22d3ee;
}
.filter-bar__sprint-label {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.filter-bar__sprint-state {
  font-size: 0.6rem;
  padding: 0.05rem 0.35rem;
  border-radius: 8px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  border: 1px solid var(--border-default);
  color: var(--text-muted);
}
.filter-bar__sprint-state--active {
  color: rgb(34, 211, 238);
  border-color: rgba(34, 211, 238, 0.5);
  background: rgba(34, 211, 238, 0.1);
}
.filter-bar__sprint-state--closed {
  color: var(--text-muted);
}
.filter-bar__sprint-state--future {
  color: rgb(167, 139, 250);
  border-color: rgba(167, 139, 250, 0.4);
  background: rgba(167, 139, 250, 0.08);
}
.filter-bar__sprint-only {
  font-size: 0.6rem;
  background: transparent;
  border: 1px solid var(--border-default);
  color: var(--text-muted);
  padding: 0.05rem 0.35rem;
  border-radius: 3px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.1s;
}
.filter-bar__sprint-row:hover .filter-bar__sprint-only {
  opacity: 1;
}
.filter-bar__sprint-only:hover {
  color: rgb(34, 211, 238);
  border-color: rgba(34, 211, 238, 0.5);
}
</style>
