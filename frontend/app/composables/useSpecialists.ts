import type { SpecialistSummary, SpecialistDetail, SpecialistFileInfo } from '~/types'
import { useApi } from '~/composables/useApi'

export function useSpecialists() {
  const specialists = useState<SpecialistSummary[]>('specialists', () => [])
  const activeSpecialist = useState<SpecialistDetail | null>('activeSpecialist', () => null)
  const loading = useState<boolean>('specialistsLoading', () => false)
  const expandedId = useState<string | null>('specialistExpanded', () => null)
  const files = useState<Record<string, SpecialistFileInfo[]>>('specialistFiles', () => ({}))
  const filesLoading = useState<Record<string, boolean>>('specialistFilesLoading', () => ({}))
  const api = useApi()

  async function load() {
    loading.value = true
    try {
      specialists.value = await api.fetchSpecialists()
      activeSpecialist.value = await api.fetchActiveSpecialist()
    } finally {
      loading.value = false
    }
  }

  async function activate(id: string) {
    await api.activateSpecialist(id)
    activeSpecialist.value = await api.fetchSpecialist(id)
  }

  async function deactivate() {
    await api.deactivateSpecialist()
    activeSpecialist.value = null
  }

  async function update(id: string, data: Partial<import('~/types').SpecialistDetail>) {
    await api.updateSpecialist(id, data)
    await load()
  }

  async function remove(id: string) {
    await api.deleteSpecialist(id)
    specialists.value = specialists.value.filter(s => s.id !== id)
    if (activeSpecialist.value?.id === id) {
      activeSpecialist.value = null
    }
    delete files.value[id]
  }

  function toggleExpand(id: string) {
    if (expandedId.value === id) {
      expandedId.value = null
    } else {
      expandedId.value = id
      if (!files.value[id] && !filesLoading.value[id]) {
        loadFiles(id)
      }
    }
  }

  async function loadFiles(id: string) {
    filesLoading.value = { ...filesLoading.value, [id]: true }
    try {
      const result = await api.fetchSpecialistFiles(id)
      files.value = { ...files.value, [id]: result }
    } catch {
      files.value = { ...files.value, [id]: [] }
    } finally {
      filesLoading.value = { ...filesLoading.value, [id]: false }
    }
  }

  async function uploadFile(id: string, file: File) {
    const result = await api.uploadSpecialistFile(id, file)
    const current = files.value[id] || []
    files.value = { ...files.value, [id]: [...current, result] }
    _syncFileCount(id)
    return result
  }

  async function ingestUrl(id: string, url: string, summarize = false) {
    const result = await api.ingestSpecialistUrl(id, url, summarize)
    const current = files.value[id] || []
    files.value = { ...files.value, [id]: [...current, result] }
    _syncFileCount(id)
    return result
  }

  async function removeFile(id: string, filename: string) {
    await api.deleteSpecialistFile(id, filename)
    const current = files.value[id] || []
    files.value = { ...files.value, [id]: current.filter(f => f.filename !== filename) }
    _syncFileCount(id)
  }

  /** Sync file_count from the local files cache — only called after successful API ops */
  function _syncFileCount(id: string) {
    const spec = specialists.value.find(s => s.id === id)
    if (spec) spec.file_count = (files.value[id] || []).length
  }

  return {
    specialists,
    activeSpecialist,
    loading,
    expandedId,
    files,
    filesLoading,
    load,
    activate,
    deactivate,
    update,
    remove,
    toggleExpand,
    loadFiles,
    uploadFile,
    ingestUrl,
    removeFile,
  }
}
