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

    <button
      class="filter-bar__orphan-btn"
      :class="{ 'filter-bar__orphan-btn--active': filters.showOrphans }"
      @click="$emit('update:filters', { ...filters, showOrphans: !filters.showOrphans })"
    >
      <span v-if="orphanCount > 0" class="filter-bar__orphan-count">{{ orphanCount }}</span>
      Orphans
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
import { computed } from 'vue'
import type { GraphNode } from '~/types'

export interface GraphFilters {
  hiddenTypes: Set<string>
  timeRange: string
  showOrphans: boolean
  searchText: string
}

// Canonical display names and colors for known node types.
// Types not listed here get an auto-generated label and grey dot.
const TYPE_META: Record<string, { label: string; color: string }> = {
  note:           { label: 'Notes',      color: 'rgba(2, 254, 255, 1)' },
  tag:            { label: 'Tags',       color: '#34d399' },
  person:         { label: 'People',     color: '#c084fc' },
  area:           { label: 'Areas',      color: '#fb923c' },
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
  'note', 'tag', 'person', 'area',
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
</style>
