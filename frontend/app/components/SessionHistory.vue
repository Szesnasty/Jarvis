<template>
  <div class="session-history">
    <div class="session-history__header">
      <h3 class="session-history__title">Sessions</h3>
      <button class="session-history__new" @click="$emit('new-session')">+ New</button>
    </div>
    <ul v-if="sessions.length" class="session-history__list">
      <li
        v-for="s in sessions"
        :key="s.session_id"
        class="session-history__item"
        :class="{ 'session-history__item--active': s.session_id === activeSessionId }"
        @click="$emit('select', s.session_id)"
      >
        <span class="session-history__item-title">{{ s.title || 'Untitled' }}</span>
        <span class="session-history__item-meta">{{ formatDate(s.created_at) }} · {{ s.message_count }} msgs</span>
      </li>
    </ul>
    <p v-else class="session-history__empty">No past sessions</p>
  </div>
</template>

<script setup lang="ts">
import type { SessionMetadata } from '~/types'

defineProps<{
  sessions: SessionMetadata[]
  activeSessionId: string | null
}>()

defineEmits<{
  select: [sessionId: string]
  'new-session': []
}>()

function formatDate(iso: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.session-history {
  width: 100%;
  max-width: 300px;
  border-right: 1px solid #333;
  padding: 0.5rem;
}

.session-history__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.session-history__title {
  font-size: 0.85rem;
  margin: 0;
  color: #ccc;
}

.session-history__new {
  background: none;
  border: 1px solid #555;
  color: #ccc;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.75rem;
}

.session-history__list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.session-history__item {
  padding: 0.4rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.session-history__item:hover {
  background: #2a2a2a;
}

.session-history__item--active {
  background: #333;
}

.session-history__item-title {
  font-size: 0.8rem;
  color: #eee;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-history__item-meta {
  font-size: 0.7rem;
  color: #888;
}

.session-history__empty {
  font-size: 0.8rem;
  color: #666;
  text-align: center;
  padding: 1rem 0;
}
</style>
