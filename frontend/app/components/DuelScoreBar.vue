<script setup lang="ts">
const props = defineProps<{
  scores: Record<string, Record<string, number>>
  specialists: { id: string; name: string; icon: string }[]
  winner: string
  reasoning: string
}>()

const CRITERIA = ['relevance', 'evidence', 'argument_strength', 'counter_argument', 'actionability']
const CRITERIA_LABELS: Record<string, string> = {
  relevance: 'Relevance',
  evidence: 'Evidence',
  argument_strength: 'Argument',
  counter_argument: 'Counter-arg',
  actionability: 'Actionability',
}

const specA = computed(() => props.specialists[0])
const specB = computed(() => props.specialists[1])

function totalFor(specId: string): number {
  const specScores = props.scores[specId]
  if (!specScores) return 0
  return Object.values(specScores).reduce((s, v) => s + v, 0)
}

const totalA = computed(() => totalFor(specA.value?.id ?? ''))
const totalB = computed(() => totalFor(specB.value?.id ?? ''))
const maxTotal = computed(() => CRITERIA.length * 5) // 5 criteria × 5 max
const percentA = computed(() => {
  const sum = totalA.value + totalB.value
  return sum > 0 ? Math.round((totalA.value / sum) * 100) : 50
})
const percentB = computed(() => 100 - percentA.value)

function scoreFor(specId: string, criterion: string): number {
  return props.scores[specId]?.[criterion] ?? 0
}

const winnerSpec = computed(() =>
  props.specialists.find(s => s.id === props.winner),
)
</script>

<template>
  <div class="score-bar">
    <div class="score-bar__header">⚔️ Verdict</div>

    <!-- Main percentage bar -->
    <div class="score-bar__main">
      <div class="score-bar__main-bar">
        <div
          class="score-bar__main-fill score-bar__main-fill--a"
          :style="{ width: percentA + '%' }"
        >
          <span v-if="percentA > 15" class="score-bar__main-label">
            {{ specA?.icon }} {{ percentA }}%
          </span>
        </div>
        <div
          class="score-bar__main-fill score-bar__main-fill--b"
          :style="{ width: percentB + '%' }"
        >
          <span v-if="percentB > 15" class="score-bar__main-label">
            {{ percentB }}% {{ specB?.icon }}
          </span>
        </div>
      </div>
      <div class="score-bar__names">
        <span>{{ specA?.icon }} {{ specA?.name }} · {{ totalA }}/{{ maxTotal }}</span>
        <span>{{ totalB }}/{{ maxTotal }} · {{ specB?.name }} {{ specB?.icon }}</span>
      </div>
    </div>

    <!-- Per-criterion breakdown -->
    <div class="score-bar__criteria">
      <div class="score-bar__criteria-header">Criteria Breakdown</div>
      <div
        v-for="c in CRITERIA"
        :key="c"
        class="score-bar__criterion"
      >
        <span class="score-bar__criterion-label">{{ CRITERIA_LABELS[c] }}</span>
        <div class="score-bar__criterion-bars">
          <div class="score-bar__criterion-side score-bar__criterion-side--a">
            <div
              class="score-bar__criterion-fill score-bar__criterion-fill--a"
              :style="{ width: (scoreFor(specA?.id ?? '', c) / 5) * 100 + '%' }"
            />
          </div>
          <div class="score-bar__criterion-side score-bar__criterion-side--b">
            <div
              class="score-bar__criterion-fill score-bar__criterion-fill--b"
              :style="{ width: (scoreFor(specB?.id ?? '', c) / 5) * 100 + '%' }"
            />
          </div>
        </div>
        <div class="score-bar__criterion-scores">
          <span>{{ scoreFor(specA?.id ?? '', c) }}</span>
          <span>{{ scoreFor(specB?.id ?? '', c) }}</span>
        </div>
      </div>
    </div>

    <!-- Winner -->
    <div v-if="winnerSpec" class="score-bar__winner">
      <div class="score-bar__winner-badge">
        🏆 Winner: {{ winnerSpec.icon }} {{ winnerSpec.name }}
      </div>
      <p class="score-bar__winner-reasoning">{{ reasoning }}</p>
    </div>

    <div class="score-bar__footer">
      📝 Saved to memory · 🔗 Graph updated
    </div>
  </div>
</template>

<style scoped>
.score-bar {
  padding: 1.25rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.score-bar__header {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* Main bar */
.score-bar__main-bar {
  display: flex;
  height: 36px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
}

.score-bar__main-fill {
  display: flex;
  align-items: center;
  justify-content: center;
  transition: width 1s cubic-bezier(0.22, 1, 0.36, 1);
  min-width: 0;
}

.score-bar__main-fill--a {
  background: linear-gradient(90deg, var(--neon-cyan-30), var(--neon-cyan-15));
}

.score-bar__main-fill--b {
  background: linear-gradient(90deg, rgba(168, 85, 247, 0.15), rgba(168, 85, 247, 0.3));
}

.score-bar__main-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
}

.score-bar__names {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-top: 0.35rem;
}

/* Criteria */
.score-bar__criteria {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.85rem;
  background: var(--bg-deep);
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
}

.score-bar__criteria-header {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.25rem;
}

.score-bar__criterion {
  display: grid;
  grid-template-columns: 90px 1fr 40px;
  align-items: center;
  gap: 0.5rem;
}

.score-bar__criterion-label {
  font-size: 0.78rem;
  color: var(--text-secondary);
}

.score-bar__criterion-bars {
  display: flex;
  gap: 2px;
  height: 14px;
}

.score-bar__criterion-side {
  flex: 1;
  background: var(--bg-base);
  border-radius: 3px;
  overflow: hidden;
}

.score-bar__criterion-side--a {
  direction: rtl;
}

.score-bar__criterion-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.8s cubic-bezier(0.22, 1, 0.36, 1);
}

.score-bar__criterion-fill--a {
  background: var(--neon-cyan-60);
}

.score-bar__criterion-fill--b {
  background: var(--neon-purple);
  opacity: 0.7;
}

.score-bar__criterion-scores {
  display: flex;
  justify-content: space-between;
  font-size: 0.72rem;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

/* Winner */
.score-bar__winner {
  padding: 0.85rem;
  background: rgba(234, 179, 8, 0.06);
  border: 1px solid rgba(234, 179, 8, 0.2);
  border-radius: 8px;
}

.score-bar__winner-badge {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--neon-yellow);
  margin-bottom: 0.35rem;
}

.score-bar__winner-reasoning {
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* Footer */
.score-bar__footer {
  font-size: 0.78rem;
  color: var(--text-muted);
  text-align: center;
}
</style>
