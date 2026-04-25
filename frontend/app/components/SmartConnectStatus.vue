<template>
  <span class="sc-status" :class="stateClass">
    <button
      type="button"
      class="sc-status__btn"
      :aria-label="ariaLabel"
      @click.stop="onClick"
      @mouseenter="open = true"
      @mouseleave="open = false"
      @focus="open = true"
      @blur="open = false"
    >
      <span class="sc-status__dot" :class="stateClass" />
      <span v-if="!compact && summaryShort" class="sc-status__label">{{ summaryShort }}</span>
    </button>
    <span v-if="open && coverage" class="sc-status__tip" role="tooltip">
      <strong class="sc-status__title">Smart Connect</strong>
      <span class="sc-status__line">{{ summaryFull }}</span>
      <span v-if="activeJob" class="sc-status__line sc-status__line--muted">
        {{ activeJob.name }} — {{ activeJob.stage || 'running' }}
      </span>
      <span v-if="needsBackfill" class="sc-status__action">
        <NuxtLink to="/settings#smart-connect" class="sc-status__link">
          Open Settings → Smart Connect
        </NuxtLink>
      </span>
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'

interface ActiveJob {
  id: string
  name: string
  kind: string
  stage?: string
}

interface Coverage {
  notes_total: number
  notes_with_suggestions: number
  notes_pending: number
  sections_total: number
  sections_with_suggestions: number
  sections_pending: number
  documents_pending: number
  active_section_jobs: ActiveJob[]
}

withDefaults(defineProps<{
  compact?: boolean
  ariaLabel?: string
}>(), {
  compact: false,
  ariaLabel: 'Smart Connect status',
})

const open = ref(false)
const coverage = ref<Coverage | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

async function fetchCoverage() {
  try {
    const res = await fetch('/api/connections/coverage')
    if (!res.ok) return
    coverage.value = (await res.json()) as Coverage
  } catch {
    // Silent — endpoint is optional UX, never block the user.
  }
}

onMounted(() => {
  fetchCoverage()
  // Light polling so the badge reflects fresh ingest activity. 10s is
  // enough to catch a section_connect job finishing without thrashing.
  timer = setInterval(fetchCoverage, 10_000)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})

const activeJob = computed<ActiveJob | null>(() => {
  const jobs = coverage.value?.active_section_jobs ?? []
  return jobs.length > 0 ? jobs[0]! : null
})
const needsBackfill = computed(() => {
  const c = coverage.value
  if (!c) return false
  return c.sections_pending > 0 || c.notes_pending > 0
})
const stateClass = computed(() => {
  if (activeJob.value) return 'sc-status--active'
  if (needsBackfill.value) return 'sc-status--warn'
  return 'sc-status--ok'
})

const summaryShort = computed(() => {
  const c = coverage.value
  if (!c) return ''
  if (activeJob.value) return 'Connecting…'
  if (c.sections_pending > 0) return `${c.sections_pending} pending`
  return ''
})

const summaryFull = computed(() => {
  const c = coverage.value
  if (!c) return 'Loading coverage…'
  if (activeJob.value) {
    return 'Sections from a freshly imported document are being connected in the background.'
  }
  if (c.sections_pending > 0) {
    const docs = c.documents_pending
    const docWord = docs === 1 ? 'document' : 'documents'
    return `${c.sections_pending} sections in ${docs} ${docWord} are not yet connected. Cross-document retrieval will improve once Smart Connect processes them.`
  }
  if (c.notes_pending > 0) {
    return `${c.notes_pending} notes have no suggestions yet. Run Backfill once to connect them.`
  }
  return `All ${c.notes_total} notes are connected — Smart Connect is up to date.`
})

function onClick() {
  open.value = !open.value
}
</script>

<style scoped>
.sc-status {
  position: relative;
  display: inline-flex;
  align-items: center;
}
.sc-status__btn {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.5rem;
  border-radius: 999px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-secondary, #a8aab2);
  font-size: 0.75rem;
  cursor: help;
  transition: all 0.15s ease;
}
.sc-status__btn:hover,
.sc-status__btn:focus-visible {
  outline: none;
  border-color: var(--neon-cyan-30, rgba(120, 220, 255, 0.3));
  background: var(--neon-cyan-08, rgba(120, 220, 255, 0.08));
}
.sc-status__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-secondary, #a8aab2);
  flex-shrink: 0;
}
.sc-status__dot.sc-status--ok {
  background: var(--color-success, #4ade80);
  box-shadow: 0 0 6px rgba(74, 222, 128, 0.5);
}
.sc-status__dot.sc-status--warn {
  background: var(--color-warning, #e6a817);
  box-shadow: 0 0 6px rgba(230, 168, 23, 0.5);
}
.sc-status__dot.sc-status--active {
  background: var(--neon-cyan, #78dcff);
  animation: sc-pulse 1.4s ease-in-out infinite;
}
@keyframes sc-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; box-shadow: 0 0 8px rgba(120, 220, 255, 0.7); }
}
.sc-status__label {
  font-weight: 500;
}
.sc-status__tip {
  position: absolute;
  z-index: 100;
  top: calc(100% + 6px);
  right: 0;
  min-width: 240px;
  max-width: 340px;
  padding: 0.6rem 0.75rem;
  border-radius: 6px;
  background: var(--surface-elevated, #1a1d24);
  border: 1px solid var(--neon-cyan-15, rgba(120, 220, 255, 0.18));
  color: var(--text-primary, #e6e6e6);
  font-size: 0.78rem;
  line-height: 1.45;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.sc-status__title {
  color: var(--neon-cyan, #78dcff);
  font-size: 0.78rem;
}
.sc-status__line {
  display: block;
}
.sc-status__line--muted {
  color: var(--text-secondary, #a8aab2);
  font-size: 0.72rem;
}
.sc-status__action {
  display: block;
  margin-top: 0.3rem;
  padding-top: 0.4rem;
  border-top: 1px solid var(--neon-cyan-15, rgba(120, 220, 255, 0.18));
}
.sc-status__link {
  color: var(--neon-cyan, #78dcff);
  text-decoration: none;
  font-weight: 500;
}
.sc-status__link:hover {
  text-decoration: underline;
}
</style>
