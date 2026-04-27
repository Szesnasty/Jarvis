import { computed, onBeforeUnmount, ref } from 'vue'

export type SharpenQueue = {
  pending: number
  processing: number
  failed_last_hour: number
  completed_total: number
  model_id: string
}

export type SharpenResult = {
  queued_notes: number
  queued_jira: number
  queued: number
  skipped: number
  model_id: string
}

interface SharpenState {
  total: number
  completedAtStart: number
  active: boolean
  lastResult: SharpenResult | null
}

const SHARPEN_KEY = 'jarvis_sharpen_progress'

function toFiniteNumber(value: unknown, fallback = 0): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) return parsed
  }
  return fallback
}

export function useSharpen() {
  const queue = ref<SharpenQueue | null>(null)
  const running = ref(false)
  const lastResult = ref<SharpenResult | null>(null)
  const total = ref(0)
  const completedAtStart = ref(0)
  const active = ref(false)
  const cancelling = ref(false)
  const allowOnBattery = ref(false)
  const onBattery = ref<boolean | null>(null)
  const enrichmentModelId = ref('')
  const enabled = ref(false)
  let pollTimer: ReturnType<typeof setInterval> | null = null

  const done = computed((): number => {
    if (!total.value) return 0
    const pending = toFiniteNumber(queue.value?.pending, 0)
    const processing = toFiniteNumber(queue.value?.processing, 0)
    return Math.min(total.value, Math.max(0, total.value - pending - processing))
  })

  const progress = computed((): number => {
    const t = toFiniteNumber(total.value, 0)
    if (t <= 0) return 0
    return Math.min(100, Math.round((done.value / t) * 100))
  })

  function loadState(): SharpenState {
    if (typeof localStorage === 'undefined') {
      return { total: 0, completedAtStart: 0, active: false, lastResult: null }
    }
    try {
      const raw = localStorage.getItem(SHARPEN_KEY)
      if (raw) {
        const parsed = JSON.parse(raw) as Partial<SharpenState> & { startActive?: number }
        const completed = toFiniteNumber(parsed.completedAtStart, Number.NaN)
        const migratedCompleted = Number.isFinite(completed)
          ? completed
          : toFiniteNumber(parsed.startActive, 0)
        return {
          total: Math.max(0, toFiniteNumber(parsed.total, 0)),
          completedAtStart: Math.max(0, migratedCompleted),
          active: Boolean(parsed.active),
          lastResult: parsed.lastResult ?? null,
        }
      }
    } catch { /* ignore */ }
    return { total: 0, completedAtStart: 0, active: false, lastResult: null }
  }

  function saveState() {
    if (typeof localStorage === 'undefined') return
    try {
      localStorage.setItem(SHARPEN_KEY, JSON.stringify({
        total: total.value,
        completedAtStart: completedAtStart.value,
        active: active.value,
        lastResult: lastResult.value,
      }))
    } catch { /* ignore */ }
  }

  function clearState() {
    if (typeof localStorage === 'undefined') return
    try { localStorage.removeItem(SHARPEN_KEY) } catch { /* ignore */ }
  }

  async function refreshQueue() {
    try {
      queue.value = await $fetch<SharpenQueue>('/api/enrichment/queue')
    } catch { /* non-critical */ }
  }

  function startPolling() {
    if (pollTimer) return
    pollTimer = setInterval(async () => {
      await refreshQueue()
      saveState()
      if (queue.value && queue.value.pending === 0 && queue.value.processing === 0) {
        active.value = false
        saveState()
        stopPolling()
      }
    }, 3000)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function run(includeJira: boolean): Promise<SharpenResult | null> {
    if (running.value) return null
    running.value = true
    total.value = 0
    completedAtStart.value = 0
    active.value = false
    clearState()
    stopPolling()
    try {
      const result = await $fetch<SharpenResult>('/api/enrichment/sharpen-all', {
        method: 'POST',
        body: { reason: 'manual_sharpen_all', include_notes: true, include_jira: includeJira },
      })
      lastResult.value = result
      total.value = result.queued
      await refreshQueue()
      completedAtStart.value = queue.value?.completed_total ?? 0
      if (result.queued > 0) {
        active.value = true
        saveState()
        startPolling()
      }
      return result
    } catch {
      return null
    } finally {
      running.value = false
    }
  }

  async function cancel(): Promise<number | null> {
    if (cancelling.value) return null
    cancelling.value = true
    try {
      const resp = await $fetch<{ removed: number }>('/api/enrichment/queue', { method: 'DELETE' })
      await refreshQueue()
      active.value = false
      total.value = 0
      completedAtStart.value = 0
      lastResult.value = null
      clearState()
      stopPolling()
      return resp.removed
    } catch {
      return null
    } finally {
      cancelling.value = false
    }
  }

  async function loadEnrichmentSettings() {
    try {
      const resp = await $fetch<{
        enabled?: boolean
        allow_on_battery: boolean
        on_battery: boolean
        model_id: string
      }>('/api/settings/enrichment')
      enabled.value = Boolean(resp.enabled)
      allowOnBattery.value = resp.allow_on_battery
      onBattery.value = resp.on_battery
      enrichmentModelId.value = resp.model_id
    } catch {
      onBattery.value = null
    }
  }

  async function changeEnrichmentModel(litellmModel: string): Promise<boolean> {
    enrichmentModelId.value = litellmModel
    try {
      await $fetch('/api/settings/enrichment', {
        method: 'PATCH',
        body: { model_id: litellmModel },
      })
      await refreshQueue()
      return true
    } catch {
      return false
    }
  }

  async function updateBatterySetting(): Promise<void> {
    try {
      await $fetch('/api/settings/enrichment', {
        method: 'PATCH',
        body: { allow_on_battery: allowOnBattery.value },
      })
    } catch { /* ignore */ }
  }

  async function init() {
    const saved = loadState()
    if (saved.total > 0) {
      total.value = saved.total
      completedAtStart.value = saved.completedAtStart
      active.value = saved.active
      lastResult.value = saved.lastResult
    }
    await refreshQueue()
    await loadEnrichmentSettings()
    // Reconcile stale localStorage with backend truth. The Sharpen worker is
    // gated on `enrichment_enabled` server-side; if it's off, no processing
    // is happening regardless of what localStorage from a previous session
    // claims. Clear stale progress so the UI doesn't lie about being active.
    if (!enabled.value) {
      total.value = 0
      completedAtStart.value = 0
      active.value = false
      lastResult.value = null
      clearState()
      return
    }
    if (total.value > 0 && queue.value && (queue.value.pending > 0 || queue.value.processing > 0)) {
      active.value = true
      startPolling()
    } else if (total.value > 0) {
      active.value = false
      saveState()
    }
  }

  onBeforeUnmount(() => { stopPolling() })

  return {
    queue, running, lastResult, total, active, cancelling,
    allowOnBattery, onBattery, enrichmentModelId, enabled,
    done, progress,
    init, run, cancel,
    refreshQueue, changeEnrichmentModel, updateBatterySetting,
  }
}

// ── Quality dots (preset-based) ─────────────────────────────────────────
type LocalModelPreset =
  | 'fast' | 'everyday' | 'balanced' | 'long-docs'
  | 'reasoning' | 'code' | 'best-local'

const PRESET_QUALITY: Record<LocalModelPreset, number> = {
  'fast': 1, 'everyday': 2, 'balanced': 3, 'long-docs': 3,
  'reasoning': 4, 'code': 4, 'best-local': 5,
}
const PRESET_LABEL: Record<LocalModelPreset, string> = {
  'fast': 'Fast · light', 'everyday': 'Good · everyday', 'balanced': 'Solid · balanced',
  'long-docs': 'Solid · long docs', 'reasoning': 'Strong · reasoning',
  'code': 'Strong · coding', 'best-local': 'Best local',
}

export function qualityDots(preset: string): { filled: number; empty: number; label: string } {
  const q = PRESET_QUALITY[preset as LocalModelPreset] ?? 3
  const label = PRESET_LABEL[preset as LocalModelPreset] ?? preset
  return { filled: q, empty: 5 - q, label }
}

export function qualityDotsText(preset: string): string {
  const q = PRESET_QUALITY[preset as LocalModelPreset] ?? 3
  return '●'.repeat(q) + '○'.repeat(5 - q)
}
