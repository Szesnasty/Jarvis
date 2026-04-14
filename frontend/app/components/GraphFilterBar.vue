<template>
  <div class="filter-bar">
    <div class="filter-bar__group">
      <label class="filter-bar__toggle" v-for="t in nodeTypes" :key="t.key">
        <input type="checkbox" :checked="t.enabled" @change="$emit('update:filters', { ...filters, [t.key]: !t.enabled })" />
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

export interface GraphFilters {
  showNotes: boolean
  showTags: boolean
  showPeople: boolean
  showAreas: boolean
  timeRange: string
  showOrphans: boolean
  searchText: string
}

const props = defineProps<{
  filters: GraphFilters
  orphanCount: number
}>()

defineEmits<{
  'update:filters': [filters: GraphFilters]
}>()

const nodeTypes = computed(() => [
  { key: 'showNotes', label: 'Notes', color: 'rgba(2, 254, 255, 1)', enabled: props.filters.showNotes },
  { key: 'showTags', label: 'Tags', color: '#34d399', enabled: props.filters.showTags },
  { key: 'showPeople', label: 'People', color: '#c084fc', enabled: props.filters.showPeople },
  { key: 'showAreas', label: 'Areas', color: '#fb923c', enabled: props.filters.showAreas },
])
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
