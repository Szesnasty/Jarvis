<template>
  <SettingsSection
    id="smart-connect"
    title="Smart Connect"
    section-class="smart-connect-section"
    :default-open="false"
  >
    <p class="smart-connect-section__lead">
      Smart Connect runs automatically when you add new notes — including
      every section of split documents (PDFs, large Markdown/JSON), which
      are connected in the background right after ingest.
      Use <strong>Backfill</strong> to process notes that existed before
      Smart Connect was enabled, or after a version bump.
      All analysis is <strong>100% local</strong> — BM25, semantic similarity, and alias matching.
      No API key or AI model required.
    </p>

    <div class="smart-connect-section__warning" role="alert">
      <strong>Warning:</strong> "Run on all notes" only rewrites frontmatter
      where suggestions actually changed (idempotent). Use <em>Dry-run
      preview</em> first to see what would change, or <em>Force</em> to
      rewrite every note regardless.
    </div>

    <div class="settings-page__actions">
      <button
        class="settings-page__btn settings-page__btn--primary"
        :disabled="running"
        @click="onRunAll"
      >
        {{ running ? 'Running…' : 'Run on all notes' }}
      </button>
      <button
        class="settings-page__btn"
        :disabled="running"
        @click="onRunOrphans"
      >
        Run only on semantic orphans
      </button>
      <button
        class="settings-page__btn"
        :disabled="running"
        @click="onDryRun"
      >
        Dry-run preview
      </button>
    </div>

    <div v-if="progress" class="smart-connect-section__progress">
      <div class="smart-connect-section__progress-bar-track">
        <div
          class="smart-connect-section__progress-bar-fill"
          :style="{ width: progressPct + '%' }"
        />
      </div>
      <div class="smart-connect-section__progress-stats">
        <span>{{ progress.done }}&thinsp;/&thinsp;{{ progress.total }} notes</span>
        <span v-if="progress.dry_run" class="smart-connect-section__chip smart-connect-section__chip--info">
          dry-run
        </span>
        <span>{{ progress.suggestions_added }} suggestions added</span>
        <span>{{ progress.notes_changed }} notes changed</span>
        <span v-if="progress.skipped > 0">{{ progress.skipped }} skipped</span>
      </div>
      <p v-if="done && !progress.dry_run" class="smart-connect-section__done">
        Done. Run "Reindex Memory" to update the stats panel.
      </p>
      <p v-if="done && progress.dry_run" class="smart-connect-section__done smart-connect-section__done--dry">
        Dry-run complete — no changes were written.
      </p>
    </div>

    <p v-if="errorMsg" class="smart-connect-section__error">{{ errorMsg }}</p>
  </SettingsSection>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import SettingsSection from '~/components/settings/SettingsSection.vue'

interface BackfillProgress {
  done: number
  total: number
  suggestions_added: number
  notes_changed: number
  skipped: number
  orphans_found: number
  dry_run: boolean
  error?: string
}

const running = ref(false)
const done = ref(false)
const progress = ref<BackfillProgress | null>(null)
const errorMsg = ref('')

const progressPct = computed(() => {
  if (!progress.value || progress.value.total === 0) return 0
  return Math.round((progress.value.done / progress.value.total) * 100)
})

async function runBackfill(payload: Record<string, unknown>) {
  running.value = true
  done.value = false
  progress.value = null
  errorMsg.value = ''

  try {
    // NOTE: Native EventSource only supports GET, so we MUST use fetch() +
    // ReadableStream to consume the SSE stream from this POST endpoint.
    const resp = await fetch('/api/connections/backfill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!resp.ok || !resp.body) {
      errorMsg.value = `Request failed: ${resp.status}`
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''

    while (true) {
      const { value, done: streamDone } = await reader.read()
      if (streamDone) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() ?? ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue
        try {
          const parsed = JSON.parse(trimmed) as BackfillProgress
          progress.value = parsed
          if (parsed.error) {
            errorMsg.value = parsed.error
          }
        } catch { /* ignore malformed lines */ }
      }
    }

    // Flush any trailing buffer
    if (buf.trim()) {
      try {
        progress.value = JSON.parse(buf.trim()) as BackfillProgress
      } catch { /* ignore */ }
    }

    done.value = true
  } catch (err: unknown) {
    errorMsg.value = err instanceof Error ? err.message : String(err)
  } finally {
    running.value = false
  }
}

function onRunAll() {
  runBackfill({ batch_size: 50 })
}

function onRunOrphans() {
  runBackfill({ only_orphans: true, batch_size: 50 })
}

function onDryRun() {
  runBackfill({ dry_run: true, batch_size: 50 })
}
</script>

<style scoped>
.smart-connect-section__lead {
  margin-bottom: 0.75rem;
  color: var(--text-secondary, #aaa);
  font-size: 0.9rem;
}

.smart-connect-section__warning {
  margin-bottom: 1rem;
  padding: 0.6rem 0.9rem;
  border-left: 3px solid var(--color-warning, #e6a817);
  background: var(--color-warning-bg, rgba(230, 168, 23, 0.08));
  font-size: 0.85rem;
  border-radius: 0 4px 4px 0;
}

.smart-connect-section__progress {
  margin-top: 1.25rem;
}

.smart-connect-section__progress-bar-track {
  height: 6px;
  border-radius: 3px;
  background: var(--color-surface-2, #2a2a2a);
  overflow: hidden;
  margin-bottom: 0.6rem;
}

.smart-connect-section__progress-bar-fill {
  height: 100%;
  background: var(--color-accent, #7c6af7);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.smart-connect-section__progress-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.85rem;
  color: var(--text-secondary, #aaa);
}

.smart-connect-section__chip {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 600;
}

.smart-connect-section__chip--info {
  background: var(--color-info-bg, rgba(100, 160, 255, 0.12));
  color: var(--color-info, #64a0ff);
}

.smart-connect-section__done {
  margin-top: 0.6rem;
  font-size: 0.85rem;
  color: var(--color-success, #5cb85c);
}

.smart-connect-section__done--dry {
  color: var(--color-info, #64a0ff);
}

.smart-connect-section__error {
  margin-top: 0.6rem;
  font-size: 0.85rem;
  color: var(--color-danger, #e05b5b);
}
</style>
