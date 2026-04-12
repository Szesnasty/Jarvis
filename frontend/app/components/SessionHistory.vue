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
  max-width: 280px;
  border-right: 1px solid var(--border-default);
  padding: 0.75rem;
  background: var(--bg-base);
  overflow-y: auto;
}

.session-history__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid var(--border-subtle);
}

.session-history__title {
  font-size: 0.8rem;
  margin: 0;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.session-history__new {
  background: transparent;
  border: 1px solid var(--neon-cyan-30);
  color: var(--neon-cyan);
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.75rem;
  transition: all 0.2s;
}

.session-history__new:hover {
  background: var(--neon-cyan-08);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}

.session-history__list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.session-history__item {
  padding: 0.5rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  transition: all 0.15s;
  border: 1px solid transparent;
}

.session-history__item:hover {
  background: var(--bg-elevated);
  border-color: var(--border-subtle);
}

.session-history__item--active {
  background: var(--neon-cyan-08);
  border-color: var(--neon-cyan-15);
}

.session-history__item-title {
  font-size: 0.8rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-history__item--active .session-history__item-title {
  color: var(--neon-cyan);
}

.session-history__item-meta {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.session-history__empty {
  font-size: 0.8rem;
  color: var(--text-muted);
  text-align: center;
  padding: 1.5rem 0;
}
</style>      
