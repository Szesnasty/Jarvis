<template>
  <div class="session-history">
    <div class="session-history__header">
      <h3 class="session-history__title">
        Sessions
        <HelpIcon
          inline
          aria-label="What are sessions?"
          text="Each session is one conversation with Jarvis, stored in app/sessions/. Switching sessions changes the chat history Claude sees on the next turn — your memory notes are shared across all sessions. Click + New to start fresh; delete a session to forget that thread entirely."
        />
      </h3>
      <button class="session-history__new" @click="$emit('new-session')">+ New</button>
    </div>
    <div v-if="loading" class="session-history__loading">
      <span class="session-history__spinner" />
      <span class="session-history__loading-text">Loading sessions…</span>
    </div>
    <ul v-else-if="sessions.length" class="session-history__list">
      <li
        v-for="s in sessions"
        :key="s.session_id"
        class="session-history__item"
        :class="{ 'session-history__item--active': s.session_id === activeSessionId }"
        @click="$emit('select', s.session_id)"
      >
        <div class="session-history__item-row">
          <span class="session-history__item-title">{{ s.title || 'Untitled' }}</span>
          <button
            class="session-history__delete"
            title="Delete session"
            @click.stop="confirmDelete(s)"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
              <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
            </svg>
          </button>
        </div>
        <span class="session-history__item-meta">{{ formatDate(s.created_at) }} · {{ s.message_count }} msgs</span>
      </li>
    </ul>
    <p v-else class="session-history__empty">No past sessions</p>

    <ConfirmDialog
      :visible="deleteTarget !== null"
      :loading="deleting"
      title="Delete conversation?"
      :message="`&quot;${deleteTarget?.title || 'Untitled'}&quot; will be permanently removed.`"
      confirm-label="Delete"
      @confirm="handleDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<script setup lang="ts">
import type { SessionMetadata } from '~/types'

const props = defineProps<{
  sessions: SessionMetadata[]
  activeSessionId: string | null
  loading?: boolean
  onDelete: (sessionId: string) => Promise<void>
}>()

const emit = defineEmits<{
  select: [sessionId: string]
  'new-session': []
}>()

const deleteTarget = ref<SessionMetadata | null>(null)
const deleting = ref(false)

function confirmDelete(session: SessionMetadata) {
  deleteTarget.value = session
}

async function handleDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await props.onDelete(deleteTarget.value.session_id)
  } finally {
    deleting.value = false
    deleteTarget.value = null
  }
}

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
  display: inline-flex;
  align-items: center;
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

.session-history__item-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
}

.session-history__item-row .session-history__item-title {
  flex: 1;
  min-width: 0;
}

.session-history__delete {
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

.session-history__item:hover .session-history__delete {
  opacity: 0.6;
}

.session-history__delete:hover {
  opacity: 1 !important;
  color: rgba(239, 68, 68, 0.9);
  background: rgba(239, 68, 68, 0.1);
  box-shadow: 0 0 10px rgba(239, 68, 68, 0.15);
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

.session-history__loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
  padding: 2rem 0;
}

.session-history__spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--neon-cyan-15);
  border-top-color: var(--neon-cyan);
  border-radius: 50%;
  animation: session-spin 0.7s linear infinite;
}

.session-history__loading-text {
  font-size: 0.75rem;
  color: var(--text-muted);
}

@keyframes session-spin {
  to { transform: rotate(360deg); }
}
</style>      
