import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

/**
 * Server-reported ingest job (running PDF extract / index / link).
 */
export interface IngestJob {
  id: string
  name: string
  kind: 'file' | 'url' | 'youtube'
  size_bytes: number | null
  status: 'running' | 'done' | 'failed'
  stage?: string
  started_at: number
  finished_at: number | null
  error: string | null
}

/**
 * Client-side upload entry (real bytes-uploaded progress, before the server
 * starts processing). Created by `uploadFile()`.
 */
export interface ClientUpload {
  id: string
  name: string
  size: number
  uploaded: number
  state: 'uploading' | 'processing' | 'done' | 'failed'
  stage?: string
  error?: string
  startedAt: number
}

interface IngestStatusResponse {
  active_count: number
  active: IngestJob[]
  recent: IngestJob[]
}

const POLL_INTERVAL_MS = 5000

// Module-level singletons -> shared across all components that call the composable.
const serverActive = ref<IngestJob[]>([])
const serverRecent = ref<IngestJob[]>([])
const uploads = ref<ClientUpload[]>([])
let timer: ReturnType<typeof setInterval> | null = null
let refCount = 0

function makeId(): string {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36)
}

function patchUpload(id: string, patch: Partial<ClientUpload>): void {
  const idx = uploads.value.findIndex((u) => u.id === id)
  if (idx === -1) return
  uploads.value.splice(idx, 1, { ...uploads.value[idx]!, ...patch })
}

function dropUploadLater(id: string, ms: number): void {
  setTimeout(() => {
    uploads.value = uploads.value.filter((u) => u.id !== id)
  }, ms)
}

async function poll(): Promise<void> {
  try {
    const data = await $fetch<IngestStatusResponse>('/api/memory/ingest/status')
    serverActive.value = data.active || []
    serverRecent.value = data.recent || []

    // Mirror server-reported stage onto local processing entries (matched by name).
    if (uploads.value.some((u) => u.state === 'processing')) {
      for (const u of uploads.value) {
        if (u.state !== 'processing') continue
        const match = serverActive.value.find((j) => j.name === u.name)
        if (match?.stage && match.stage !== u.stage) {
          patchUpload(u.id, { stage: match.stage })
        }
      }
    }
  } catch {
    // backend offline -- keep last known state
  }
}

function formatBytes(n: number): string {
  if (!n) return '0 B'
  if (n < 1024) return n + ' B'
  if (n < 1024 * 1024) return (n / 1024).toFixed(0) + ' KB'
  if (n < 1024 * 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + ' MB'
  return (n / 1024 / 1024 / 1024).toFixed(2) + ' GB'
}

function capitalize(s: string): string {
  return s ? s[0]!.toUpperCase() + s.slice(1) : s
}

export function useIngestStatus() {
  const activeUploads = computed(() =>
    uploads.value.filter((u) => u.state === 'uploading' || u.state === 'processing'),
  )

  // Combined active count: client uploads in flight + server jobs not started here
  // (e.g. ingest started in another tab, URL import).
  const activeCount = computed(() => {
    const localNames = new Set(activeUploads.value.map((u) => u.name))
    const extraServer = serverActive.value.filter((j) => !localNames.has(j.name)).length
    return activeUploads.value.length + extraServer
  })

  const recent = computed<IngestJob[]>(() => {
    const localFailed: IngestJob[] = uploads.value
      .filter((u) => u.state === 'failed')
      .map((u) => ({
        id: u.id,
        name: u.name,
        kind: 'file' as const,
        size_bytes: u.size,
        status: 'failed' as const,
        stage: u.stage,
        started_at: u.startedAt / 1000,
        finished_at: Date.now() / 1000,
        error: u.error || 'failed',
      }))
    return [...localFailed, ...serverRecent.value]
  })

  const hasActivity = computed(() => activeCount.value > 0 || recent.value.length > 0)

  // Bytes-based progress (client uploads only -- the server doesn't expose
  // byte-level progress for the extract/index/link phase).
  const totalBytes = computed(() =>
    activeUploads.value.reduce((a, u) => a + (u.size || 0), 0),
  )
  const uploadedBytes = computed(() =>
    activeUploads.value.reduce(
      (a, u) => a + (u.state === 'uploading' ? u.uploaded || 0 : u.size || 0),
      0,
    ),
  )
  const overallPercent = computed(() => {
    if (totalBytes.value === 0) return 0
    return Math.min(100, Math.floor((uploadedBytes.value / totalBytes.value) * 100))
  })

  const label = computed(() => {
    const n = activeCount.value
    if (n === 0) return ''
    if (n === 1 && activeUploads.value.length === 1) {
      const one = activeUploads.value[0]!
      const short = one.name.length > 24 ? one.name.slice(0, 21) + '...' : one.name
      if (one.state === 'uploading') {
        return short + ' - ' + overallPercent.value + '%'
      }
      return capitalize(one.stage || 'processing') + ' - ' + short
    }
    if (n === 1) {
      const one = serverActive.value[0]
      const name = one?.name || 'file'
      const short = name.length > 24 ? name.slice(0, 21) + '...' : name
      return capitalize(one?.stage || 'processing') + ' - ' + short
    }
    if (totalBytes.value > 0) {
      return (
        n +
        ' files - ' +
        formatBytes(uploadedBytes.value) +
        ' / ' +
        formatBytes(totalBytes.value) +
        ' - ' +
        overallPercent.value +
        '%'
      )
    }
    return n + ' files'
  })

  /**
   * Upload a file via XMLHttpRequest so we get real upload progress.
   * Resolves with the parsed JSON response, or rejects with Error.
   */
  function uploadFile(
    url: string,
    file: File,
    extraFields: Record<string, string> = {},
  ): Promise<unknown> {
    const id = makeId()
    uploads.value.push({
      id,
      name: file.name,
      size: file.size,
      uploaded: 0,
      state: 'uploading',
      startedAt: Date.now(),
    })

    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', url)
      xhr.responseType = 'json'

      xhr.upload.onprogress = (e: ProgressEvent) => {
        if (e.lengthComputable) patchUpload(id, { uploaded: e.loaded })
      }
      xhr.upload.onload = () => {
        // All bytes are on the server; backend now extracts/indexes/links.
        patchUpload(id, {
          uploaded: file.size,
          state: 'processing',
          stage: 'processing',
        })
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          patchUpload(id, { state: 'done', stage: 'done' })
          dropUploadLater(id, 6000)
          resolve(xhr.response)
        } else {
          const body = xhr.response as { detail?: string; message?: string } | null
          const detail = body?.detail || body?.message || 'HTTP ' + xhr.status
          patchUpload(id, { state: 'failed', error: String(detail) })
          dropUploadLater(id, 8000)
          reject(new Error(String(detail)))
        }
      }
      xhr.onerror = () => {
        patchUpload(id, { state: 'failed', error: 'Network error' })
        dropUploadLater(id, 8000)
        reject(new Error('Network error'))
      }
      xhr.onabort = () => {
        patchUpload(id, { state: 'failed', error: 'Aborted' })
        dropUploadLater(id, 4000)
        reject(new Error('Aborted'))
      }

      const fd = new FormData()
      fd.append('file', file)
      for (const [k, v] of Object.entries(extraFields)) fd.append(k, v)
      xhr.send(fd)
    })
  }

  onMounted(() => {
    refCount++
    if (timer === null) {
      poll()
      timer = setInterval(poll, POLL_INTERVAL_MS)
    }
  })

  onBeforeUnmount(() => {
    refCount--
    if (refCount <= 0 && timer !== null) {
      clearInterval(timer)
      timer = null
      refCount = 0
    }
  })

  return {
    // server-side
    active: serverActive,
    recent,
    // combined
    activeCount,
    hasActivity,
    label,
    // bytes
    totalBytes,
    uploadedBytes,
    overallPercent,
    // client uploads
    uploads,
    activeUploads,
    uploadFile,
  }
}
