<template>
  <span class="sc-status" :class="stateClass">
    <button
      type="button"
      class="sc-status__btn"
      :class="{ 'sc-status__btn--just-finished': justFinished }"
      :aria-label="ariaLabel"
      @click.stop="onClick"
      @mouseenter="hoverOpen = true"
      @mouseleave="hoverOpen = false"
      @focus="hoverOpen = true"
      @blur="hoverOpen = false"
    >
      <span class="sc-status__dot" :class="stateClass" />
      <span v-if="!compact && summaryShort" class="sc-status__label">{{ summaryShort }}</span>
    </button>
    <span v-if="popoverOpen && coverage" class="sc-status__tip" role="tooltip">
      <strong class="sc-status__title">
        <span v-if="justFinished">✓ Smart Connect finished</span>
        <span v-else>Smart Connect</span>
      </strong>
      <span class="sc-status__line">{{ summaryFull }}</span>
      <span v-if="activeJob" class="sc-status__line sc-status__line--muted">
        {{ activeJob.name }} — {{ activeJob.stage || 'running' }}
      </span>
      <span v-if="activeJob && progressPct !== null" class="sc-status__progress">
        <span class="sc-status__progress-fill" :style="{ width: progressPct + '%' }" />
      </span>
      <span v-if="!activeJob && coverage" class="sc-status__breakdown">
        <span class="sc-status__chip sc-status__chip--ok">
          {{ coverage.sections_with_suggestions }} connected
        </span>
        <span v-if="coverage.sections_no_match > 0" class="sc-status__chip sc-status__chip--muted">
          {{ coverage.sections_no_match }} standalone
        </span>
        <span v-if="unprocessedCount > 0" class="sc-status__chip sc-status__chip--warn">
          {{ unprocessedCount }} pending
        </span>
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
  sections_unprocessed: number   // SC never ran → needs backfill
  sections_no_match: number      // SC ran, found nothing → final state
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

const hoverOpen = ref(false)
const autoOpen = ref(false)              // auto-opened popover after completion
const justFinished = ref(false)          // 3s green pulse + checkmark in title
const coverage = ref<Coverage | null>(null)
let timer: ReturnType<typeof setInterval> | null = null
let autoOpenTimer: ReturnType<typeof setTimeout> | null = null
let pulseTimer: ReturnType<typeof setTimeout> | null = null

const popoverOpen = computed(() => hoverOpen.value || autoOpen.value)

// Re-show completion popover only once per "completion event" — keyed by
// the timestamp of when SC last finished. Stored in sessionStorage so a
// page reload right after completion doesn't re-fire the popover.
const COMPLETION_KEY = 'sc-completion-shown-at'

async function fetchCoverage() {
  try {
    const res = await fetch('/api/connections/coverage')
    if (!res.ok) return
    const next = (await res.json()) as Coverage
    const prev = coverage.value
    coverage.value = next

    // Detect active→idle transition (SC just finished its background work).
    const wasActiveJob = (prev?.active_section_jobs?.length ?? 0) > 0
    const isActiveJob = next.active_section_jobs.length > 0
    if (wasActiveJob && !isActiveJob) {
      onSmartConnectFinished()
    }
  } catch {
    // Silent — endpoint is optional UX, never block the user.
  }
}

function onSmartConnectFinished() {
  // Sticky guard: if we already showed completion for this exact moment, skip.
  // We use a coarse 30s window — if user reloads within 30s, we still suppress.
  try {
    const last = Number(sessionStorage.getItem(COMPLETION_KEY) || '0')
    const now = Date.now()
    if (now - last < 30_000) return
    sessionStorage.setItem(COMPLETION_KEY, String(now))
  } catch {
    // sessionStorage unavailable — fall through, just show once per page life
  }

  justFinished.value = true
  autoOpen.value = true

  if (autoOpenTimer) clearTimeout(autoOpenTimer)
  autoOpenTimer = setTimeout(() => { autoOpen.value = false }, 6_000)

  if (pulseTimer) clearTimeout(pulseTimer)
  pulseTimer = setTimeout(() => { justFinished.value = false }, 3_000)
}

onMounted(() => {
  fetchCoverage()
  // Light polling so the badge reflects fresh ingest activity. While SC is
  // active we poll faster (3s) so the N/M progress text stays accurate.
  const POLL_IDLE = 10_000
  const POLL_ACTIVE = 3_000
  let currentInterval = POLL_IDLE
  const reschedule = (next: number) => {
    if (next === currentInterval) return
    currentInterval = next
    if (timer) clearInterval(timer)
    timer = setInterval(tick, currentInterval)
  }
  const tick = async () => {
    await fetchCoverage()
    reschedule((coverage.value?.active_section_jobs?.length ?? 0) > 0 ? POLL_ACTIVE : POLL_IDLE)
  }
  timer = setInterval(tick, currentInterval)
})
onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
  if (autoOpenTimer) clearTimeout(autoOpenTimer)
  if (pulseTimer) clearTimeout(pulseTimer)
})

const activeJob = computed<ActiveJob | null>(() => {
  const jobs = coverage.value?.active_section_jobs ?? []
  return jobs.length > 0 ? jobs[0]! : null
})

// Parse "linking 12/30" or similar "N/M" from the active job's stage string.
const progressPct = computed<number | null>(() => {
  const stage = activeJob.value?.stage
  if (!stage) return null
  const m = stage.match(/(\d+)\s*\/\s*(\d+)/)
  if (!m) return null
  const [, doneStr, totalStr] = m
  const done = Number(doneStr)
  const total = Number(totalStr)
  if (!total) return null
  return Math.min(100, Math.round((done / total) * 100))
})

const progressLabel = computed<string | null>(() => {
  const stage = activeJob.value?.stage
  if (!stage) return null
  const m = stage.match(/(\d+)\s*\/\s*(\d+)/)
  return m ? `${m[1]}/${m[2]}` : null
})

const unprocessedCount = computed(() => {
  const c = coverage.value
  if (!c) return 0
  return c.sections_unprocessed ?? c.sections_pending
})
// Amber warning only when SC hasn't processed some sections yet (needs backfill).
// sections_no_match = SC ran and found nothing → green, that's a final state.
const needsBackfill = computed(() => {
  const c = coverage.value
  if (!c) return false
  return unprocessedCount.value > 0 || c.notes_pending > 0
})
const stateClass = computed(() => {
  if (activeJob.value) return 'sc-status--active'
  if (needsBackfill.value) return 'sc-status--warn'
  return 'sc-status--ok'
})

// Always show a status label so the user has an explicit "done" signal.
// During active work it reads e.g. "Connecting 12/30". When done it reads
// "Up to date" — small, green, but visible (no more silent blank state).
const summaryShort = computed(() => {
  const c = coverage.value
  if (!c) return ''
  if (activeJob.value) {
    return progressLabel.value ? `Processing ${progressLabel.value}` : 'Processing…'
  }
  if (unprocessedCount.value > 0) return `${unprocessedCount.value} pending`
  if (justFinished.value) return '✓ Just finished'
  return '✓ Up to date'
})

const summaryFull = computed(() => {
  const c = coverage.value
  if (!c) return 'Loading coverage…'
  if (activeJob.value) {
    if (progressLabel.value) {
      return `Processing sections in the background — ${progressLabel.value} done. You can keep working; this runs offline.`
    }
    return 'Sections from a freshly imported document are being processed in the background. You can keep working.'
  }
  const unprocessed = unprocessedCount.value
  const noMatch = c.sections_no_match ?? 0
  if (unprocessed > 0) {
    const docs = c.documents_pending
    const docWord = docs === 1 ? 'document' : 'documents'
    return `${unprocessed} sections in ${docs} ${docWord} haven't been processed yet. Run Backfill in Settings → Smart Connect to connect them.`
  }
  if (justFinished.value) {
    const connected = c.sections_with_suggestions
    const standalone = noMatch
    if (standalone > 0) {
      return `Connected ${connected} sections. ${standalone} had no link candidates — normal for niche or standalone content.`
    }
    return `Connected ${connected} sections. Everything is linked — you can keep working.`
  }
  if (noMatch > 0) {
    return `Smart Connect is up to date. ${noMatch} section${noMatch === 1 ? '' : 's'} had no link candidates — this is normal for niche or standalone content.`
  }
  if (c.notes_pending > 0) {
    return `${c.notes_pending} notes have no suggestions yet. Run Backfill once to connect them.`
  }
  return `All ${c.notes_total} notes are connected — Smart Connect is up to date.`
})

function onClick() {
  // Toggle: if either auto or hover-open, close everything. Otherwise open.
  if (popoverOpen.value) {
    hoverOpen.value = false
    autoOpen.value = false
    if (autoOpenTimer) { clearTimeout(autoOpenTimer); autoOpenTimer = null }
  } else {
    hoverOpen.value = true
  }
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
  /* Reset typographic styles inherited from parent headings (e.g. the
     Memory page <h2> which is uppercase + letter-spaced). */
  text-transform: none;
  letter-spacing: normal;
  font-weight: 500;
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
  /* Pin to the left edge of the trigger so the tooltip always opens to the
     right. The Memory sidebar is narrow and near the viewport edge, so
     using right:0 was causing the popup to overflow off-screen to the left. */
  left: 0;
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
  /* Reset inherited heading typography so the tooltip reads as normal
     sentence-case prose, not ALL-CAPS / wide-tracked like the parent <h2>. */
  text-transform: none;
  letter-spacing: normal;
  font-weight: normal;
  text-align: left;
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

/* Progress bar shown in tooltip while a section_connect job is active. */
.sc-status__progress {
  display: block;
  height: 4px;
  border-radius: 2px;
  background: var(--neon-cyan-15, rgba(120, 220, 255, 0.18));
  overflow: hidden;
  margin-top: 0.2rem;
}
.sc-status__progress-fill {
  display: block;
  height: 100%;
  background: var(--neon-cyan, #78dcff);
  transition: width 0.3s ease;
}

/* Idle-state breakdown chips: connected / standalone / pending. */
.sc-status__breakdown {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  margin-top: 0.3rem;
}
.sc-status__chip {
  display: inline-flex;
  align-items: center;
  padding: 0.1rem 0.4rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 500;
  border: 1px solid transparent;
}
.sc-status__chip--ok {
  background: rgba(74, 222, 128, 0.12);
  color: var(--color-success, #4ade80);
  border-color: rgba(74, 222, 128, 0.25);
}
.sc-status__chip--muted {
  background: var(--neon-cyan-08, rgba(120, 220, 255, 0.08));
  color: var(--text-secondary, #a8aab2);
  border-color: var(--neon-cyan-15, rgba(120, 220, 255, 0.18));
}
.sc-status__chip--warn {
  background: rgba(230, 168, 23, 0.14);
  color: var(--color-warning, #e6a817);
  border-color: rgba(230, 168, 23, 0.3);
}

/* Brief celebratory pulse when SC transitions from active to idle. */
.sc-status__btn--just-finished {
  animation: sc-finished-pulse 1.4s ease-out 2;
}
@keyframes sc-finished-pulse {
  0% { box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.55); }
  100% { box-shadow: 0 0 0 10px rgba(74, 222, 128, 0); }
}
</style>
