<script setup lang="ts">
import type { DuelEvent, DuelPhase, DuelVerdict } from '~/types'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ breaks: true, gfm: true })

function renderMd(text: string): string {
  return DOMPurify.sanitize(marked.parse(text) as string, { USE_PROFILES: { html: true } })
}

const props = defineProps<{
  topic: string
  events: DuelEvent[]
  phase: DuelPhase
  verdict: DuelVerdict | null
  currentTexts: Record<string, string>
  errorMsg?: string
}>()

const emit = defineEmits<{
  cancel: []
}>()

const r1Collapsed = ref(false)

// Toggle Round 1 collapse
function toggleR1(): void {
  r1Collapsed.value = !r1Collapsed.value
}

const debateEl = ref<HTMLElement | null>(null)
const verdictEl = ref<HTMLElement | null>(null)

// Auto-collapse Round 1 when Round 2 starts
watch(() => props.phase, (p) => {
  if (p === 'round2') r1Collapsed.value = true
  // Auto-scroll to verdict/judging when it appears
  if (p === 'judging' || p === 'verdict' || p === 'done') {
    nextTick(() => {
      if (verdictEl.value) {
        verdictEl.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
      } else if (debateEl.value) {
        debateEl.value.scrollTo({ top: debateEl.value.scrollHeight, behavior: 'smooth' })
      }
    })
  }
})

// Extract specialists from setup event
const specialists = computed(() => {
  const setup = props.events.find(e => e.type === 'duel_setup')
  return setup?.specialists ?? []
})

const specA = computed(() => specialists.value[0])
const specB = computed(() => specialists.value[1])

// Collect completed round texts from events
function roundTexts(roundNum: number): Record<string, string> {
  const texts: Record<string, string> = {}
  for (const ev of props.events) {
    if (ev.type === 'duel_specialist_delta' && ev.round === roundNum && ev.specialist) {
      texts[ev.specialist] = (texts[ev.specialist] ?? '') + (ev.content ?? '')
    }
  }
  return texts
}

const r1Texts = computed(() => roundTexts(1))
const r2Texts = computed(() => roundTexts(2))

// Current round number for display
const currentRound = computed(() => {
  if (props.phase === 'round1') return 1
  if (props.phase === 'round2') return 2
  return 0
})

// Determine if a specialist is currently streaming
function isStreaming(specName: string): boolean {
  if (props.phase !== 'round1' && props.phase !== 'round2') return false
  // If we have current text accumulating for this specialist, it's streaming
  return (props.currentTexts[specName]?.length ?? 0) > 0 && !isRoundDone(specName)
}

function isRoundDone(specName: string): boolean {
  const round = currentRound.value
  return props.events.some(
    e => e.type === 'duel_specialist_done' && e.specialist === specName && e.round === round,
  )
}

// Get display text for a specialist in the current streaming round
function liveText(specName: string): string {
  return props.currentTexts[specName] ?? ''
}

// Build score bar spec list
const scoreSpecialists = computed(() =>
  specialists.value.map(s => ({ id: s.id, name: s.name, icon: s.icon })),
)

const roundLabel = computed(() => {
  switch (props.phase) {
    case 'round1': return 'Round 1 of 2 · Opening Positions'
    case 'round2': return 'Round 2 of 2 · Counter-Arguments'
    case 'judging': return 'Judging...'
    case 'verdict': return 'Verdict'
    case 'done': return 'Complete'
    case 'error': return 'Error'
    default: return ''
  }
})
</script>

<template>
  <div ref="debateEl" class="debate">
    <div class="debate__header">
      <div class="debate__title">⚔️ Duel — "{{ topic }}"</div>
      <div class="debate__round-label">{{ roundLabel }}</div>
    </div>

    <!-- Round 1 -->
    <div
      v-if="Object.keys(r1Texts).length > 0 || phase === 'round1'"
      class="debate__round"
      :class="{ 'debate__round--collapsed': r1Collapsed }"
    >
      <button
        v-if="phase !== 'round1'"
        class="debate__round-toggle"
        @click="toggleR1"
      >
        Round 1 {{ r1Collapsed ? '▸' : '▾' }}
        <span v-if="r1Collapsed" class="debate__round-summary">
          <span v-if="specA">{{ specA.icon }} {{ specA.name }} ✓</span>
          <span v-if="specB">{{ specB.icon }} {{ specB.name }} ✓</span>
        </span>
      </button>

      <template v-if="!r1Collapsed">
        <!-- Spec A — Round 1 -->
        <div v-if="specA" class="debate__card">
          <div class="debate__card-header">
            <span class="debate__card-icon">{{ specA.icon || '🤖' }}</span>
            <span class="debate__card-name">{{ specA.name }}</span>
            <span
              v-if="phase === 'round1' && isStreaming(specA.name)"
              class="debate__pulse"
            />
            <span
              v-if="phase !== 'round1' || isRoundDone(specA.name)"
              class="debate__check"
            >✓</span>
          </div>
          <div
            v-if="phase === 'round1' && liveText(specA.name)"
            class="debate__card-body debate__card-body--md"
            v-html="renderMd(liveText(specA.name))"
          />
          <div
            v-else-if="r1Texts[specA.name]"
            class="debate__card-body debate__card-body--md"
            v-html="renderMd(r1Texts[specA.name] ?? '')"
          />
          <div v-else class="debate__card-body debate__card-waiting">
            ◌ Waiting for Round 1...
          </div>
        </div>

        <!-- Spec B — Round 1 -->
        <div v-if="specB" class="debate__card">
          <div class="debate__card-header">
            <span class="debate__card-icon">{{ specB.icon || '🤖' }}</span>
            <span class="debate__card-name">{{ specB.name }}</span>
            <span
              v-if="phase === 'round1' && isStreaming(specB.name)"
              class="debate__pulse"
            />
            <span
              v-if="phase !== 'round1' || isRoundDone(specB.name)"
              class="debate__check"
            >✓</span>
          </div>
          <div
            v-if="phase === 'round1' && liveText(specB.name)"
            class="debate__card-body debate__card-body--md"
            v-html="renderMd(liveText(specB.name))"
          />
          <div
            v-else-if="r1Texts[specB.name]"
            class="debate__card-body debate__card-body--md"
            v-html="renderMd(r1Texts[specB.name] ?? '')"
          />
          <div v-else class="debate__card-body debate__card-waiting">
            ◌ Waiting for Round 1...
          </div>
        </div>
      </template>
    </div>

    <!-- Round 2 -->
    <div
      v-if="phase === 'round2' || Object.keys(r2Texts).length > 0 || phase === 'judging' || phase === 'verdict' || phase === 'done'"
      class="debate__round"
    >
      <!-- Spec A — Round 2 -->
      <div v-if="specA" class="debate__card">
        <div class="debate__card-header">
          <span class="debate__card-icon">{{ specA.icon || '🤖' }}</span>
          <span class="debate__card-name">{{ specA.name }} — Rebuttal</span>
          <span
            v-if="phase === 'round2' && isStreaming(specA.name)"
            class="debate__pulse"
          />
          <span
            v-if="phase !== 'round2' || isRoundDone(specA.name)"
            class="debate__check"
          >✓</span>
        </div>
        <div
          v-if="phase === 'round2' && liveText(specA.name)"
          class="debate__card-body debate__card-body--md"
          v-html="renderMd(liveText(specA.name))"
        />
        <div
          v-else-if="r2Texts[specA.name]"
          class="debate__card-body debate__card-body--md"
          v-html="renderMd(r2Texts[specA.name] ?? '')"
        />
        <div v-else class="debate__card-body debate__card-waiting">
          ◌ Waiting for Round 2...
        </div>
      </div>

      <!-- Spec B — Round 2 -->
      <div v-if="specB" class="debate__card">
        <div class="debate__card-header">
          <span class="debate__card-icon">{{ specB.icon || '🤖' }}</span>
          <span class="debate__card-name">{{ specB.name }} — Rebuttal</span>
          <span
            v-if="phase === 'round2' && isStreaming(specB.name)"
            class="debate__pulse"
          />
          <span
            v-if="phase !== 'round2' || isRoundDone(specB.name)"
            class="debate__check"
          >✓</span>
        </div>
        <div
          v-if="phase === 'round2' && liveText(specB.name)"
          class="debate__card-body debate__card-body--md"
          v-html="renderMd(liveText(specB.name))"
        />
        <div
          v-else-if="r2Texts[specB.name]"
          class="debate__card-body debate__card-body--md"
          v-html="renderMd(r2Texts[specB.name] ?? '')"
        />
        <div v-else class="debate__card-body debate__card-waiting">
          ◌ Waiting for Round 2...
        </div>
      </div>
    </div>

    <!-- Judging indicator — Jarvis Orb deliberating -->
    <div v-if="phase === 'judging'" class="debate__jarvis-judging">
      <div class="debate__jarvis-orb-wrap">
        <Orb state="thinking" />
      </div>
      <div class="debate__jarvis-label">Evaluating arguments...</div>
    </div>

    <!-- Verdict — Jarvis delivers judgment -->
    <div v-if="(phase === 'verdict' || phase === 'done') && verdict" ref="verdictEl" class="debate__jarvis-verdict">
      <div class="debate__jarvis-verdict-header">
        <div class="debate__jarvis-orb-mini">
          <Orb state="speaking" />
        </div>
        <div class="debate__jarvis-says">Jarvis Verdict</div>
      </div>

      <!-- Score Bar -->
      <DuelScoreBar
        v-if="specialists.length === 2"
        :scores="verdict.scores"
        :specialists="scoreSpecialists"
        :winner="verdict.winner"
        :reasoning="verdict.reasoning"
      />

      <div v-if="verdict.recommendation" class="debate__recommendation">
        <div class="debate__recommendation-label">Recommendation</div>
        <div class="debate__recommendation-text" v-html="renderMd(verdict.recommendation)" />
      </div>

      <div v-if="verdict.action_items?.length" class="debate__actions">
        <div class="debate__actions-label">Action Items</div>
        <ul class="debate__actions-list">
          <li v-for="(item, i) in verdict.action_items" :key="i">{{ item }}</li>
        </ul>
      </div>
    </div>

    <!-- Error display -->
    <div v-if="phase === 'error' && errorMsg" class="debate__error">
      <span class="debate__error-icon">⚠️</span>
      <span class="debate__error-text">{{ errorMsg }}</span>
    </div>

    <!-- Cancel button -->
    <div v-if="phase !== 'verdict' && phase !== 'done'" class="debate__footer">
      <button class="debate__cancel" @click="emit('cancel')">
        {{ phase === 'error' ? 'Close Duel' : 'Cancel Duel' }}
      </button>
    </div>

    <!-- Back to chat after verdict -->
    <div v-if="phase === 'verdict' || phase === 'done'" class="debate__footer">
      <button class="debate__back" @click="emit('cancel')">
        ← Back to Chat
      </button>
    </div>
  </div>
</template>

<style scoped>
.debate {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1.25rem 1.5rem;
  flex: 1;
  width: 100%;
  max-width: 900px;
  min-height: 0;
  overflow-y: auto;
  min-height: 0;
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.debate__header {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-subtle);
}

.debate__title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.debate__round-label {
  font-size: 0.82rem;
  color: var(--neon-cyan-60);
  font-weight: 500;
}

/* Rounds */
.debate__round {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.debate__round-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  padding: 0.25rem 0;
}

.debate__round-toggle:hover {
  color: var(--text-primary);
}

.debate__round-summary {
  display: flex;
  gap: 0.75rem;
  font-weight: 400;
  color: var(--text-muted);
}

/* Cards */
.debate__card {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  overflow: hidden;
}

.debate__card-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 0.85rem;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-deep);
}

.debate__card-icon {
  font-size: 1.1rem;
}

.debate__card-name {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.debate__pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--neon-cyan);
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.85); }
}

.debate__check {
  color: var(--neon-green);
  font-size: 0.82rem;
  font-weight: 700;
}

.debate__card-body {
  padding: 0.75rem 0.85rem;
  font-size: 0.9rem;
  line-height: 1.6;
  color: var(--text-primary);
}

.debate__card-body--md :deep(p) {
  margin: 0 0 0.5em;
}
.debate__card-body--md :deep(p:last-child) {
  margin-bottom: 0;
}
.debate__card-body--md :deep(strong) {
  color: var(--neon-cyan);
  font-weight: 600;
}
.debate__card-body--md :deep(ul),
.debate__card-body--md :deep(ol) {
  margin: 0.4em 0;
  padding-left: 1.4em;
}
.debate__card-body--md :deep(li) {
  margin: 0.2em 0;
}

.debate__card-waiting {
  color: var(--text-muted);
  font-style: italic;
  font-size: 0.85rem;
}

/* Jarvis Judging */
.debate__jarvis-judging {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 2rem 1rem;
  background:
    radial-gradient(ellipse at center, var(--neon-cyan-08) 0%, transparent 70%),
    var(--bg-surface, #0d1117);
  border: 1px solid var(--neon-cyan-15);
  border-radius: 14px;
  box-shadow:
    0 0 40px var(--neon-cyan-08),
    inset 0 1px 0 var(--neon-cyan-08);
  animation: fadeIn 0.3s ease-out;
}

.debate__jarvis-orb-wrap {
  width: 120px;
  height: 120px;
}

.debate__jarvis-orb-wrap :deep(.orb-svg) {
  width: 120px !important;
  height: 120px !important;
}

.debate__jarvis-label {
  font-size: 0.9rem;
  color: var(--neon-cyan, #02feff);
  letter-spacing: 0.05em;
  text-shadow: 0 0 10px var(--neon-cyan-30);
  animation: pulse-text 1.5s ease-in-out infinite;
}

@keyframes pulse-text {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

/* Jarvis Verdict */
.debate__jarvis-verdict {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1.25rem;
  position: relative;
  background:
    linear-gradient(135deg, var(--neon-cyan-08) 0%, transparent 50%),
    linear-gradient(315deg, rgba(2, 254, 255, 0.03) 0%, transparent 50%),
    var(--bg-surface, #0d1117);
  border: 1px solid var(--neon-cyan-30);
  border-radius: 14px;
  box-shadow:
    0 0 30px var(--neon-cyan-08),
    0 0 60px rgba(2, 254, 255, 0.04),
    inset 0 1px 0 var(--neon-cyan-15),
    inset 0 -1px 0 rgba(2, 254, 255, 0.05);
  animation: verdict-appear 0.5s ease-out;
  overflow: hidden;
}

/* Soft edge glow shimmer */
.debate__jarvis-verdict::before {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: 14px;
  background: linear-gradient(
    135deg,
    var(--neon-cyan-15) 0%,
    transparent 30%,
    transparent 70%,
    var(--neon-cyan-08) 100%
  );
  z-index: -1;
  animation: glow-rotate 6s linear infinite;
}

@keyframes glow-rotate {
  0% { filter: hue-rotate(0deg) brightness(1); }
  50% { filter: hue-rotate(5deg) brightness(1.15); }
  100% { filter: hue-rotate(0deg) brightness(1); }
}

@keyframes verdict-appear {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.debate__jarvis-verdict-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--neon-cyan-08);
}

.debate__jarvis-orb-mini {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  filter: drop-shadow(0 0 10px var(--neon-cyan-30));
}

.debate__jarvis-orb-mini :deep(.orb-svg) {
  width: 44px !important;
  height: 44px !important;
}

.debate__jarvis-says {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--neon-cyan, #02feff);
  letter-spacing: 0.04em;
  text-shadow: 0 0 12px var(--neon-cyan-30), 0 0 30px rgba(2, 254, 255, 0.15);
}

.debate__recommendation {
  padding-top: 0.25rem;
}

.debate__recommendation-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--neon-cyan, #02feff);
  text-shadow: 0 0 8px var(--neon-cyan-30);
  margin-bottom: 0.35rem;
}

.debate__recommendation-text {
  font-size: 0.88rem;
  line-height: 1.6;
  color: var(--text-primary);
}

.debate__recommendation-text :deep(p) {
  margin: 0;
}

.debate__actions {
  padding-top: 0.25rem;
}

.debate__actions-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--neon-cyan, #02feff);
  text-shadow: 0 0 8px var(--neon-cyan-30);
  margin-bottom: 0.35rem;
}

.debate__actions-list {
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.85rem;
  line-height: 1.7;
  color: var(--text-primary);
}

.debate__actions-list li::marker {
  color: var(--neon-cyan, #02feff);
}

/* Error */
.debate__error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background: rgba(220, 60, 60, 0.08);
  border: 1px solid rgba(220, 60, 60, 0.25);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 0.85rem;
  line-height: 1.5;
}

.debate__error-icon {
  font-size: 1.1rem;
  flex-shrink: 0;
}

/* Footer */
.debate__footer {
  display: flex;
  justify-content: center;
  padding-top: 0.5rem;
}

.debate__cancel {
  padding: 0.4rem 1rem;
  font-size: 0.82rem;
  color: var(--text-secondary);
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}

.debate__cancel:hover {
  color: var(--neon-red);
  border-color: rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.04);
}

.debate__back {
  padding: 0.5rem 1.25rem;
  font-size: 0.85rem;
  color: var(--neon-cyan, #02feff);
  background: rgba(2, 254, 255, 0.06);
  border: 1px solid rgba(2, 254, 255, 0.2);
  border-radius: 8px;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.2s;
}

.debate__back:hover {
  background: rgba(2, 254, 255, 0.12);
  border-color: rgba(2, 254, 255, 0.35);
}
</style>
