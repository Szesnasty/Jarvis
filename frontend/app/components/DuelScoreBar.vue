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
    <div class="score-bar__header">
      <span class="score-bar__header-icon">⚔️</span>
      <span class="score-bar__header-text">Verdict</span>
    </div>

    <!-- Main percentage bar -->
    <div class="score-bar__main">
      <div class="score-bar__main-bar">
        <div
          class="score-bar__main-fill score-bar__main-fill--a"
          :style="{ width: percentA + '%' }"
        >
          <div class="score-bar__main-fill-glow score-bar__main-fill-glow--a" />
          <span v-if="percentA > 15" class="score-bar__main-label">
            {{ specA?.icon }} {{ percentA }}%
          </span>
        </div>
        <div
          class="score-bar__main-fill score-bar__main-fill--b"
          :style="{ width: percentB + '%' }"
        >
          <div class="score-bar__main-fill-glow score-bar__main-fill-glow--b" />
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
        v-for="(c, idx) in CRITERIA"
        :key="c"
        class="score-bar__criterion"
        :style="{ animationDelay: idx * 0.08 + 's' }"
      >
        <span class="score-bar__criterion-label">{{ CRITERIA_LABELS[c] }}</span>
        <div class="score-bar__criterion-bars">
          <div class="score-bar__criterion-side score-bar__criterion-side--a">
            <div
              class="score-bar__criterion-fill score-bar__criterion-fill--a"
              :style="{ width: (scoreFor(specA?.id ?? '', c) / 5) * 100 + '%' }"
            >
              <div class="score-bar__criterion-shine" />
            </div>
          </div>
          <div class="score-bar__criterion-side score-bar__criterion-side--b">
            <div
              class="score-bar__criterion-fill score-bar__criterion-fill--b"
              :style="{ width: (scoreFor(specB?.id ?? '', c) / 5) * 100 + '%' }"
            >
              <div class="score-bar__criterion-shine" />
            </div>
          </div>
        </div>
        <div class="score-bar__criterion-scores">
          <span class="score-bar__score score-bar__score--a">{{ scoreFor(specA?.id ?? '', c) }}</span>
          <span class="score-bar__score score-bar__score--b">{{ scoreFor(specB?.id ?? '', c) }}</span>
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
/* ---------- Root card — frosted glass ---------- */
.score-bar {
  --cyan-glow: rgba(2, 254, 255, 0.45);
  --purple-glow: rgba(168, 85, 247, 0.45);
  --cyan-fill: rgba(2, 254, 255, 0.7);
  --purple-fill: rgba(168, 85, 247, 0.65);

  padding: 1.5rem;
  background:
    linear-gradient(135deg, rgba(2, 254, 255, 0.04) 0%, transparent 50%, rgba(168, 85, 247, 0.04) 100%),
    rgba(15, 23, 36, 0.75);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(2, 254, 255, 0.12);
  border-radius: 16px;
  display: flex;
  flex-direction: column;
  gap: 1.1rem;
  box-shadow:
    0 0 30px rgba(2, 254, 255, 0.06),
    0 0 60px rgba(168, 85, 247, 0.04),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  animation: scoreBarAppear 0.6s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes scoreBarAppear {
  from {
    opacity: 0;
    transform: translateY(12px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

/* ---------- Header ---------- */
.score-bar__header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.score-bar__header-icon {
  font-size: 1.1rem;
}

.score-bar__header-text {
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.02em;
}

/* ---------- Main summary bar ---------- */
.score-bar__main-bar {
  display: flex;
  height: 42px;
  border-radius: 10px;
  overflow: hidden;
  position: relative;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.4);
}

.score-bar__main-fill {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  transition: width 1.2s cubic-bezier(0.22, 1, 0.36, 1);
  min-width: 0;
}

.score-bar__main-fill--a {
  background: linear-gradient(90deg,
    rgba(2, 254, 255, 0.25) 0%,
    rgba(2, 254, 255, 0.4) 100%
  );
  border-right: 1px solid rgba(255, 255, 255, 0.1);
}

.score-bar__main-fill--b {
  background: linear-gradient(90deg,
    rgba(168, 85, 247, 0.25) 0%,
    rgba(168, 85, 247, 0.4) 100%
  );
}

/* Animated glow layer inside the main fills */
.score-bar__main-fill-glow {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.score-bar__main-fill-glow--a {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(2, 254, 255, 0.2) 40%,
    rgba(2, 254, 255, 0.5) 50%,
    rgba(2, 254, 255, 0.2) 60%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmerCyan 3s ease-in-out infinite;
}

.score-bar__main-fill-glow--b {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(168, 85, 247, 0.2) 40%,
    rgba(168, 85, 247, 0.5) 50%,
    rgba(168, 85, 247, 0.2) 60%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmerPurple 3.5s ease-in-out infinite;
}

@keyframes shimmerCyan {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@keyframes shimmerPurple {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}

.score-bar__main-label {
  font-size: 0.82rem;
  font-weight: 700;
  color: #fff;
  white-space: nowrap;
  text-shadow: 0 0 10px rgba(0, 0, 0, 0.6);
  position: relative;
  z-index: 1;
}

.score-bar__names {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
  color: var(--text-secondary);
  margin-top: 0.4rem;
}

/* ---------- Criteria breakdown — glass panel ---------- */
.score-bar__criteria {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.score-bar__criteria-header {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 0.15rem;
}

.score-bar__criterion {
  display: grid;
  grid-template-columns: 95px 1fr 46px;
  align-items: center;
  gap: 0.6rem;
  animation: criterionSlideIn 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes criterionSlideIn {
  from {
    opacity: 0;
    transform: translateX(-8px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.score-bar__criterion-label {
  font-size: 0.78rem;
  color: var(--text-secondary);
  font-weight: 500;
}

.score-bar__criterion-bars {
  display: flex;
  gap: 3px;
  height: 20px;
}

.score-bar__criterion-side {
  flex: 1;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 5px;
  overflow: hidden;
  position: relative;
  border: 1px solid rgba(255, 255, 255, 0.04);
}

.score-bar__criterion-side--a {
  direction: rtl;
}

.score-bar__criterion-fill {
  height: 100%;
  border-radius: 5px;
  position: relative;
  overflow: hidden;
  transition: width 1s cubic-bezier(0.22, 1, 0.36, 1);
}

.score-bar__criterion-fill--a {
  background: linear-gradient(90deg,
    rgba(2, 254, 255, 0.5),
    rgba(2, 254, 255, 0.8)
  );
  box-shadow:
    0 0 8px rgba(2, 254, 255, 0.3),
    0 0 20px rgba(2, 254, 255, 0.15),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

.score-bar__criterion-fill--b {
  background: linear-gradient(90deg,
    rgba(168, 85, 247, 0.5),
    rgba(168, 85, 247, 0.8)
  );
  box-shadow:
    0 0 8px rgba(168, 85, 247, 0.3),
    0 0 20px rgba(168, 85, 247, 0.15),
    inset 0 1px 0 rgba(255, 255, 255, 0.25);
}

/* Glass shine on bars */
.score-bar__criterion-shine {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    rgba(255, 255, 255, 0.2) 0%,
    transparent 50%,
    rgba(0, 0, 0, 0.1) 100%
  );
  pointer-events: none;
}

.score-bar__criterion-scores {
  display: flex;
  justify-content: space-between;
  font-variant-numeric: tabular-nums;
}

.score-bar__score {
  font-size: 0.78rem;
  font-weight: 700;
  display: inline-flex;
  justify-content: center;
  width: 20px;
}

.score-bar__score--a {
  color: var(--neon-cyan);
  text-shadow: 0 0 6px rgba(2, 254, 255, 0.4);
}

.score-bar__score--b {
  color: var(--neon-purple);
  text-shadow: 0 0 6px rgba(168, 85, 247, 0.4);
}

/* ---------- Winner section — glowing border ---------- */
.score-bar__winner {
  position: relative;
  padding: 1rem 1.1rem;
  background: rgba(234, 179, 8, 0.04);
  border: 1px solid rgba(234, 179, 8, 0.25);
  border-radius: 12px;
  overflow: hidden;
  box-shadow:
    0 0 15px rgba(234, 179, 8, 0.08),
    inset 0 1px 0 rgba(234, 179, 8, 0.1);
  animation: winnerGlow 2.5s ease-in-out infinite alternate;
}

@keyframes winnerGlow {
  0% {
    box-shadow:
      0 0 15px rgba(234, 179, 8, 0.08),
      inset 0 1px 0 rgba(234, 179, 8, 0.1);
  }
  100% {
    box-shadow:
      0 0 25px rgba(234, 179, 8, 0.15),
      0 0 50px rgba(234, 179, 8, 0.06),
      inset 0 1px 0 rgba(234, 179, 8, 0.15);
  }
}

.score-bar__winner-badge {
  font-size: 0.95rem;
  font-weight: 800;
  color: var(--neon-yellow);
  margin-bottom: 0.4rem;
  text-shadow: 0 0 12px rgba(234, 179, 8, 0.4);
}

.score-bar__winner-reasoning {
  font-size: 0.85rem;
  color: var(--text-secondary);
  line-height: 1.55;
}

/* ---------- Footer ---------- */
.score-bar__footer {
  font-size: 0.75rem;
  color: var(--text-muted);
  text-align: center;
  opacity: 0.7;
}
</style>
