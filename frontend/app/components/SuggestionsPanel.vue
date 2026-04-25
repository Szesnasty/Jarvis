<template>
  <section v-if="suggestions.length > 0 || aliasesMatched.length > 0" class="suggestions">
    <header class="suggestions__header">
      <h3
        class="suggestions__title"
        title="Smart Connect ran automatically when this note was ingested. These are candidate links it found — keep the ones that fit, dismiss the rest. Re-run only if you have changed the note or want fresh suggestions."
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 2 L15 8.5 L22 9.5 L17 14.5 L18.5 22 L12 18 L5.5 22 L7 14.5 L2 9.5 L9 8.5 Z"/>
        </svg>
        Smart Connect
      </h3>
      <div class="suggestions__header-actions">
        <template v-if="confirmKeepAll">
          <span class="suggestions__confirm-text">Keep {{ strongCount }} suggested links?</span>
          <button class="suggestions__btn-text" @click="confirmKeepAll = false">Cancel</button>
          <button class="suggestions__btn suggestions__btn--promote" @click="doKeepAll">Keep all</button>
        </template>
        <template v-else>
          <button
            v-if="showKeepAll"
            class="suggestions__btn suggestions__btn--keep-all"
            :disabled="busy === '__keep_all__'"
            @click="onKeepAll"
          >
            {{ busy === '__keep_all__' ? 'Linking…' : `Keep all (${strongCount})` }}
          </button>
          <button
            class="suggestions__rerun"
            :disabled="!!busy"
            :title="`Re-run Smart Connect for this note (mode=${mode})`"
            @click="onRerun"
          >
            {{ busy === 'rerun' ? 'Running…' : 'Re-run' }}
          </button>
        </template>
      </div>
    </header>

    <p v-if="aliasesMatched.length > 0" class="suggestions__aliases">
      Matched aliases: <span v-for="a in aliasesMatched" :key="a" class="suggestions__alias">{{ a }}</span>
    </p>

    <ul v-if="suggestions.length > 0" class="suggestions__list">
      <li
        v-for="s in suggestions"
        :key="s.path"
        class="suggestions__item"
        :class="`suggestions__item--${tierOf(s.confidence)}`"
      >
        <button class="suggestions__path" :title="s.path" @click="$emit('open', s.path)">
          {{ pathLabel(s.path) }}
        </button>
        <div class="suggestions__meta">
          <span class="suggestions__confidence">{{ Math.round(s.confidence * 100) }}%</span>
          <span v-for="m in s.methods" :key="m" class="suggestions__method">{{ m }}</span>
          <span
            v-if="s.score_breakdown && Object.keys(s.score_breakdown).length > 0"
            class="suggestions__why"
            tabindex="0"
            :aria-label="`Why: ${whyText(s)}`"
            :data-tooltip="whyText(s)"
            title=""
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            <span class="suggestions__why-tooltip" role="tooltip">
              <strong>Why this suggestion?</strong>
              <span v-for="(val, key) in s.score_breakdown" :key="key" class="suggestions__why-row">
                <span class="suggestions__why-method">{{ key }}</span>
                <span class="suggestions__why-val">{{ val.toFixed(2) }}</span>
              </span>
              <span class="suggestions__why-divider"></span>
              <span class="suggestions__why-row suggestions__why-row--total">
                <span class="suggestions__why-method">total</span>
                <span class="suggestions__why-val">{{ s.confidence.toFixed(2) }}</span>
              </span>
            </span>
          </span>
        </div>
        <div class="suggestions__actions">
          <button
            class="suggestions__btn suggestions__btn--promote"
            :disabled="busy === s.path"
            title="Promote to related"
            @click="onPromote(s.path)"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
            Keep
          </button>
          <button
            class="suggestions__btn suggestions__btn--dismiss"
            :disabled="busy === s.path"
            title="Dismiss this suggestion forever"
            @click="onDismiss(s.path)"
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            Dismiss
          </button>
        </div>
      </li>
    </ul>
    <p v-else-if="aliasesMatched.length === 0" class="suggestions__empty">No suggestions yet.</p>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { NoteDetail, SuggestedLink } from '~/types'

const props = defineProps<{ note: NoteDetail | null }>()
const emit = defineEmits<{
  (e: 'open', path: string): void
  (e: 'changed'): void
}>()

const { dismissSuggestion, promoteSuggestion, rerunConnect } = useApi()
const { show: showSnackbar } = useSnackbar()

const busy = ref<string | null>(null)
const confirmKeepAll = ref(false)
const mode: 'fast' | 'aggressive' = 'fast'

const suggestions = computed<SuggestedLink[]>(() => {
  const raw = props.note?.frontmatter?.suggested_related
  if (!Array.isArray(raw)) return []
  return raw.filter((s): s is SuggestedLink =>
    !!s && typeof s === 'object' && typeof (s as SuggestedLink).path === 'string',
  )
})

const aliasesMatched = computed<string[]>(() => {
  const raw = props.note?.frontmatter?.aliases_matched
  return Array.isArray(raw) ? raw.filter((x): x is string => typeof x === 'string') : []
})

const strongSuggestions = computed<SuggestedLink[]>(() =>
  suggestions.value.filter(s => s.confidence >= 0.8),
)

const strongCount = computed(() => strongSuggestions.value.length)

/** Show "Keep all (N)" only when 2 ≤ strong count ≤ 5. */
const showKeepAll = computed(() => strongCount.value >= 2 && strongCount.value <= 5)

function tierOf(c: number): 'strong' | 'normal' | 'weak' {
  if (c >= 0.8) return 'strong'
  if (c >= 0.6) return 'normal'
  return 'weak'
}

function pathLabel(p: string): string {
  const last = p.split('/').pop() ?? p
  return last.replace(/\.md$/, '')
}

function whyText(s: SuggestedLink): string {
  if (!s.score_breakdown) return ''
  const lines = Object.entries(s.score_breakdown)
    .map(([k, v]) => `${k}: ${v.toFixed(2)}`)
    .join(', ')
  return `${lines} → total: ${s.confidence.toFixed(2)}`
}

async function onPromote(target: string): Promise<void> {
  if (!props.note) return
  busy.value = target
  try {
    await promoteSuggestion(props.note.path, target)
    showSnackbar(`Linked to ${pathLabel(target)}`, { type: 'success' })
    emit('changed')
  } catch (e: unknown) {
    showSnackbar(`Could not promote: ${(e as Error).message}`, { type: 'error' })
  } finally {
    busy.value = null
  }
}

async function onDismiss(target: string): Promise<void> {
  if (!props.note) return
  busy.value = target
  try {
    await dismissSuggestion(props.note.path, target)
    showSnackbar(`Dismissed ${pathLabel(target)}`, { type: 'info' })
    emit('changed')
  } catch (e: unknown) {
    showSnackbar(`Could not dismiss: ${(e as Error).message}`, { type: 'error' })
  } finally {
    busy.value = null
  }
}

function onKeepAll(): void {
  if (strongCount.value >= 4) {
    confirmKeepAll.value = true
  } else {
    void doKeepAll()
  }
}

async function doKeepAll(): Promise<void> {
  if (!props.note) return
  confirmKeepAll.value = false
  busy.value = '__keep_all__'
  const targets = strongSuggestions.value.map(s => s.path)
  let promoted = 0
  try {
    for (const target of targets) {
      await promoteSuggestion(props.note.path, target)
      promoted++
    }
    showSnackbar(`Linked ${promoted} notes`, { type: 'success' })
    emit('changed')
  } catch (e: unknown) {
    showSnackbar(`Keep all failed: ${(e as Error).message}`, { type: 'error' })
    if (promoted > 0) emit('changed')
  } finally {
    busy.value = null
  }
}

async function onRerun(): Promise<void> {
  if (!props.note) return
  busy.value = 'rerun'
  try {
    await rerunConnect(props.note.path, mode)
    showSnackbar('Smart Connect re-run', { type: 'success' })
    emit('changed')
  } catch (e: unknown) {
    showSnackbar(`Re-run failed: ${(e as Error).message}`, { type: 'error' })
  } finally {
    busy.value = null
  }
}
</script>

<style scoped>
.suggestions {
  margin: 1.25rem 0;
  padding: 0.85rem 1rem;
  border: 1px solid var(--border-default);
  border-radius: 10px;
  background: var(--neon-cyan-04, rgba(0, 200, 255, 0.04));
}

.suggestions__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.6rem;
}

.suggestions__title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-secondary);
}

.suggestions__rerun {
  font-size: 0.75rem;
  padding: 0.25rem 0.6rem;
  background: transparent;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  color: var(--text-secondary);
  cursor: pointer;
}

.suggestions__rerun:hover:not(:disabled) {
  color: var(--text-primary);
  border-color: var(--neon-cyan, #00c8ff);
}

.suggestions__rerun:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.suggestions__aliases {
  margin: 0 0 0.6rem;
  font-size: 0.78rem;
  color: var(--text-muted);
}

.suggestions__alias {
  display: inline-block;
  margin-left: 0.35rem;
  padding: 0.05rem 0.4rem;
  background: var(--neon-cyan-08, rgba(0, 200, 255, 0.08));
  border-radius: 4px;
  color: var(--text-secondary);
}

.suggestions__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.suggestions__item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.35rem 0.75rem;
  align-items: center;
  padding: 0.5rem 0.65rem;
  background: var(--bg-elevated, rgba(255, 255, 255, 0.02));
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  border-left: 3px solid var(--border-subtle);
}

.suggestions__item--strong { border-left-color: var(--success, #4ade80); }
.suggestions__item--normal { border-left-color: var(--neon-cyan, #00c8ff); }
.suggestions__item--weak   { border-left-color: var(--text-muted, #888); }

.suggestions__path {
  background: none;
  border: none;
  padding: 0;
  font-size: 0.88rem;
  font-weight: 500;
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  text-overflow: ellipsis;
  overflow: hidden;
  white-space: nowrap;
}

.suggestions__path:hover {
  color: var(--neon-cyan, #00c8ff);
  text-decoration: underline;
}

.suggestions__meta {
  grid-column: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  font-size: 0.7rem;
  color: var(--text-muted);
}

.suggestions__confidence {
  font-weight: 600;
  color: var(--text-secondary);
}

.suggestions__method {
  padding: 0.05rem 0.35rem;
  background: var(--bg-base, rgba(0, 0, 0, 0.2));
  border-radius: 3px;
}

.suggestions__actions {
  grid-row: 1 / span 2;
  grid-column: 2;
  display: flex;
  gap: 0.35rem;
}

.suggestions__btn {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.72rem;
  padding: 0.25rem 0.55rem;
  border: 1px solid var(--border-default);
  border-radius: 5px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}

.suggestions__btn:disabled { opacity: 0.5; cursor: not-allowed; }

.suggestions__btn--promote:hover:not(:disabled) {
  border-color: var(--success, #4ade80);
  color: var(--success, #4ade80);
}

.suggestions__btn--dismiss:hover:not(:disabled) {
  border-color: var(--danger, #f87171);
  color: var(--danger, #f87171);
}

.suggestions__empty {
  margin: 0;
  font-size: 0.8rem;
  color: var(--text-muted);
}

.suggestions__header-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.suggestions__confirm-text {
  font-size: 0.75rem;
  color: var(--text-secondary);
}

.suggestions__btn-text {
  background: none;
  border: none;
  font-size: 0.75rem;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0.2rem 0.3rem;
}

.suggestions__btn-text:hover {
  color: var(--text-primary);
}

.suggestions__btn--keep-all {
  font-size: 0.72rem;
  padding: 0.25rem 0.6rem;
  background: transparent;
  border: 1px solid var(--success, #4ade80);
  border-radius: 6px;
  color: var(--success, #4ade80);
  cursor: pointer;
}

.suggestions__btn--keep-all:hover:not(:disabled) {
  background: rgba(74, 222, 128, 0.1);
}

.suggestions__btn--keep-all:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* "Why?" info icon + tooltip */
.suggestions__why {
  position: relative;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  color: var(--text-muted);
}

.suggestions__why:hover,
.suggestions__why:focus-visible {
  color: var(--neon-cyan, #00c8ff);
  outline: none;
}

.suggestions__why-tooltip {
  display: none;
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  z-index: 200;
  min-width: 160px;
  padding: 0.55rem 0.7rem;
  background: var(--bg-overlay, #1a1a2e);
  border: 1px solid var(--border-default);
  border-radius: 7px;
  font-size: 0.72rem;
  color: var(--text-secondary);
  white-space: nowrap;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.suggestions__why:hover .suggestions__why-tooltip,
.suggestions__why:focus-visible .suggestions__why-tooltip {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.suggestions__why-tooltip strong {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  margin-bottom: 0.2rem;
}

.suggestions__why-row {
  display: flex;
  justify-content: space-between;
  gap: 1.5rem;
}

.suggestions__why-row--total {
  font-weight: 600;
  color: var(--text-primary);
}

.suggestions__why-method {
  color: var(--text-secondary);
}

.suggestions__why-val {
  font-variant-numeric: tabular-nums;
}

.suggestions__why-divider {
  border-top: 1px solid var(--border-subtle);
  margin: 0.15rem 0;
}

</style>
