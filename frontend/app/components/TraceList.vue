<template>
  <div v-if="items && items.length > 0" class="trace-list">
    <button
      type="button"
      class="trace-list__toggle"
      :aria-expanded="expanded"
      @click="expanded = !expanded"
    >
      <span class="trace-list__chevron" :class="{ 'trace-list__chevron--open': expanded }">▸</span>
      Used context ({{ items.length }})
    </button>
    <ul v-if="expanded" class="trace-list__items">
      <li
        v-for="item in items"
        :key="`${item.path}-${item.reason}-${item.via}`"
        class="trace-list__item"
        :class="{ 'trace-list__item--expansion': item.reason === 'expansion' }"
      >
        <span class="trace-list__dot" :class="{ 'trace-list__dot--expansion': item.reason === 'expansion' }" />
        <NuxtLink :to="`/memory?path=${encodeURIComponent(item.path)}`" class="trace-list__path">
          {{ item.title || item.path }}
        </NuxtLink>
        <span class="trace-list__reason">{{ describe(item) }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import type { TraceItem } from '~/types'

const props = defineProps<{ items?: TraceItem[] | null }>()
const expanded = ref(false)

function describe(item: TraceItem): string {
  if (item.reason === 'expansion') {
    const tier = item.tier ? `, ${item.tier}` : ''
    return `via ${item.edge_type || item.via}${tier}`
  }
  const score = typeof item.score === 'number' ? ` ${item.score.toFixed(2)}` : ''
  return `${item.via}${score}`
}
</script>

<style scoped>
.trace-list {
  margin-top: 8px;
  font-size: 12px;
  color: var(--color-text-muted, #888);
}

.trace-list__toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: none;
  padding: 2px 4px;
  margin-left: -4px;
  color: inherit;
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  border-radius: 4px;
}

.trace-list__toggle:hover {
  background: var(--color-bg-hover, rgba(255, 255, 255, 0.05));
  color: var(--color-text, #ddd);
}

.trace-list__chevron {
  display: inline-block;
  transition: transform 0.15s ease;
  font-size: 10px;
}

.trace-list__chevron--open {
  transform: rotate(90deg);
}

.trace-list__items {
  list-style: none;
  margin: 6px 0 0 16px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.trace-list__item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 11.5px;
  line-height: 1.5;
}

.trace-list__dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
  opacity: 0.85;
}

.trace-list__dot--expansion {
  background: transparent;
  border: 1px solid currentColor;
}

.trace-list__path {
  color: var(--color-text, #ddd);
  text-decoration: none;
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-list__path:hover {
  color: var(--color-accent, #6cf);
  text-decoration: underline;
}

.trace-list__reason {
  flex-shrink: 0;
  opacity: 0.7;
}
</style>
