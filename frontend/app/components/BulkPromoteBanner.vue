<template>
  <div v-if="visible" class="bulk-promote">
    <div class="bulk-promote__main">
      <span class="bulk-promote__icon" aria-hidden="true">✨</span>
      <span class="bulk-promote__text">
        <strong>{{ pendingStrong }}</strong>
        high-confidence link{{ pendingStrong === 1 ? '' : 's' }} found
        <span class="bulk-promote__muted">in {{ pendingNotes }} note{{ pendingNotes === 1 ? '' : 's' }}</span>
        <span class="bulk-promote__hint"> — accept all in one click, no review needed</span>
      </span>
      <button
        v-if="!confirming"
        class="bulk-promote__btn bulk-promote__btn--primary"
        :disabled="busy"
        @click="confirming = true"
      >
        Link all
      </button>
      <button
        v-if="!confirming"
        class="bulk-promote__btn bulk-promote__btn--ghost"
        :disabled="busy"
        @click="$emit('review')"
      >
        Review
      </button>
    </div>

    <div v-if="confirming" class="bulk-promote__confirm">
      <label class="bulk-promote__threshold">
        Confidence threshold:
        <select v-model.number="threshold" :disabled="busy">
          <option :value="0.7">≥ 70%</option>
          <option :value="0.8">≥ 80% (recommended)</option>
          <option :value="0.9">≥ 90%</option>
        </select>
      </label>
      <span class="bulk-promote__confirm-text">
        Every suggestion at or above the threshold will be added to
        <code>related</code> in one step. Dismissed pairs are skipped.
        Notes with weaker suggestions will keep the ✦ badge for manual review.
      </span>
      <div class="bulk-promote__actions">
        <button class="bulk-promote__btn bulk-promote__btn--ghost" :disabled="busy" @click="confirming = false">
          Cancel
        </button>
        <button class="bulk-promote__btn bulk-promote__btn--primary" :disabled="busy" @click="onConfirm">
          {{ busy ? 'Linking…' : `Link all ≥ ${Math.round(threshold * 100)}%` }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  pendingStrong: number
  pendingNotes: number
}>()

const emit = defineEmits<{
  (e: 'review'): void
  (e: 'promoted', payload: { promoted: number; notes_changed: number }): void
}>()

const { promoteBulk } = useApi()
const { show: showSnackbar } = useSnackbar()

const confirming = ref(false)
const busy = ref(false)
const threshold = ref(0.8)
// Optimistically hide the banner as soon as the user confirms, so it
// doesn't re-appear from coverage polling while the promote is in flight.
const dismissed = ref(false)

const visible = computed(() => !dismissed.value && props.pendingStrong > 0)

// When the parent reports zero pending (coverage refreshed after promote),
// re-arm so the banner can appear again if new suggestions arrive later.
watch(() => props.pendingStrong, (n) => {
  if (n === 0) dismissed.value = false
})

async function onConfirm() {
  busy.value = true
  dismissed.value = true  // hide immediately — don't wait for poll
  try {
    const res = await promoteBulk(threshold.value, 'all', false)
    if (res.promoted === 0) {
      showSnackbar('No suggestions matched the threshold.', { type: 'info' })
    } else {
      showSnackbar(
        `Linked ${res.promoted} suggestion${res.promoted === 1 ? '' : 's'} across ${res.notes_changed} note${res.notes_changed === 1 ? '' : 's'}.`,
        { type: 'success' },
      )
    }
    emit('promoted', { promoted: res.promoted, notes_changed: res.notes_changed })
    confirming.value = false
    // dismissed stays true until parent refreshes coverage and passes 0
  } catch (e: unknown) {
    showSnackbar(`Could not promote: ${(e as Error).message}`, { type: 'error' })
    dismissed.value = false  // restore banner so user can retry
  } finally {
    busy.value = false
  }
}
</script>

<style scoped>
.bulk-promote {
  margin: 0.5rem 0.75rem;
  padding: 0.6rem 0.75rem;
  border-radius: 8px;
  background: var(--neon-cyan-08, rgba(120, 220, 255, 0.08));
  border: 1px solid var(--neon-cyan-30, rgba(120, 220, 255, 0.3));
  color: var(--text-primary, #e6e6e6);
  font-size: 0.8rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.bulk-promote__main {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}
.bulk-promote__icon {
  font-size: 0.95rem;
}
.bulk-promote__text {
  flex: 1;
  min-width: 0;
}
.bulk-promote__muted {
  color: var(--text-secondary, #a8aab2);
  font-size: 0.74rem;
  margin-left: 0.25rem;
}
.bulk-promote__hint {
  color: var(--text-muted, #6b7280);
  font-size: 0.72rem;
  font-style: italic;
  margin-left: 0.15rem;
}
.bulk-promote__btn {
  padding: 0.3rem 0.65rem;
  border-radius: 4px;
  font-size: 0.75rem;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s ease;
  white-space: nowrap;
}
.bulk-promote__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.bulk-promote__btn--primary {
  background: var(--neon-cyan, #78dcff);
  color: #0a0d12;
  font-weight: 600;
}
.bulk-promote__btn--primary:hover:not(:disabled) {
  background: var(--neon-cyan-bright, #9ee5ff);
}
.bulk-promote__btn--ghost {
  background: transparent;
  border-color: var(--neon-cyan-30, rgba(120, 220, 255, 0.3));
  color: var(--text-primary, #e6e6e6);
}
.bulk-promote__btn--ghost:hover:not(:disabled) {
  background: var(--neon-cyan-08, rgba(120, 220, 255, 0.08));
}
.bulk-promote__confirm {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  padding-top: 0.4rem;
  border-top: 1px solid var(--neon-cyan-15, rgba(120, 220, 255, 0.18));
}
.bulk-promote__threshold {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--text-secondary, #a8aab2);
  font-size: 0.75rem;
}
.bulk-promote__threshold select {
  background: var(--surface-elevated, #1a1d24);
  color: var(--text-primary, #e6e6e6);
  border: 1px solid var(--neon-cyan-15, rgba(120, 220, 255, 0.18));
  border-radius: 4px;
  padding: 0.15rem 0.35rem;
  font-size: 0.75rem;
}
.bulk-promote__confirm-text {
  font-size: 0.74rem;
  color: var(--text-secondary, #a8aab2);
  line-height: 1.4;
}
.bulk-promote__confirm-text code {
  background: var(--surface-elevated, #1a1d24);
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
  font-size: 0.7rem;
}
.bulk-promote__actions {
  display: flex;
  gap: 0.4rem;
  justify-content: flex-end;
}
</style>
