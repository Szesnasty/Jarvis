import { describe, it, expect, vi } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import SpecialistKnowledgePanel from '~/components/SpecialistKnowledgePanel.vue'

// Mock useSpecialists composable
const mockUploadFile = vi.fn()
const mockIngestUrl = vi.fn()
const mockRemoveFile = vi.fn()

vi.mock('~/composables/useSpecialists', () => ({
  useSpecialists: () => ({
    files: useState('specialistFiles', () => ({
      'test-spec': [
        { filename: 'notes.md', path: 'specialists/test-spec/notes.md', title: 'Notes', size: 1024, created_at: '2026-01-01T00:00:00Z' },
        { filename: 'data.csv', path: 'specialists/test-spec/data.csv', title: 'Data', size: 51200, created_at: '2026-01-02T00:00:00Z' },
      ],
    })),
    filesLoading: useState('specialistFilesLoading', () => ({})),
    uploadFile: mockUploadFile,
    ingestUrl: mockIngestUrl,
    removeFile: mockRemoveFile,
  }),
}))

describe('SpecialistKnowledgePanel', () => {
  it('renders header with file count', async () => {
    const wrapper = await mountSuspended(SpecialistKnowledgePanel, {
      props: { specialistId: 'test-spec' },
    })
    expect(wrapper.find('.know-panel__header-label').text()).toContain('Knowledge Base')
    expect(wrapper.find('.know-panel__count').text()).toBe('2')
  })

  it('renders file list with names and sizes', async () => {
    const wrapper = await mountSuspended(SpecialistKnowledgePanel, {
      props: { specialistId: 'test-spec' },
    })
    const files = wrapper.findAll('.know-panel__file')
    expect(files.length).toBe(2)
    expect(files[0].find('.know-panel__file-title').text()).toBe('Notes')
    expect(files[0].find('.know-panel__file-meta').text()).toBe('1.0 KB')
    expect(files[1].find('.know-panel__file-title').text()).toBe('Data')
    expect(files[1].find('.know-panel__file-meta').text()).toBe('50.0 KB')
  })

  it('shows empty state when no files', async () => {
    useState('specialistFiles').value = { 'empty-spec': [] }
    const wrapper = await mountSuspended(SpecialistKnowledgePanel, {
      props: { specialistId: 'empty-spec' },
    })
    expect(wrapper.find('.know-panel__empty').exists()).toBe(true)
    expect(wrapper.find('.know-panel__empty').text()).toContain('No files yet')
  })

  it('has drag-and-drop zone', async () => {
    const wrapper = await mountSuspended(SpecialistKnowledgePanel, {
      props: { specialistId: 'test-spec' },
    })
    expect(wrapper.find('.know-panel__dropzone').exists()).toBe(true)
    expect(wrapper.find('.know-panel__drop-text').text()).toContain('Drop files here')
  })

  it('has URL ingest bar', async () => {
    const wrapper = await mountSuspended(SpecialistKnowledgePanel, {
      props: { specialistId: 'test-spec' },
    })
    expect(wrapper.find('.know-panel__url-bar').exists()).toBe(true)
    expect(wrapper.find('.know-panel__url-input').exists()).toBe(true)
  })

  it('URL go button is disabled when input is empty', async () => {
    const wrapper = await mountSuspended(SpecialistKnowledgePanel, {
      props: { specialistId: 'test-spec' },
    })
    const goBtn = wrapper.find('.know-panel__url-go')
    expect((goBtn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('URL go button enables when input has text', async () => {
    const wrapper = await mountSuspended(SpecialistKnowledgePanel, {
      props: { specialistId: 'test-spec' },
    })
    await wrapper.find('.know-panel__url-input').setValue('https://example.com')
    const goBtn = wrapper.find('.know-panel__url-go')
    expect((goBtn.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('rejects invalid URLs with error message', async () => {
    const wrapper = await mountSuspended(SpecialistKnowledgePanel, {
      props: { specialistId: 'test-spec' },
    })
    await wrapper.find('.know-panel__url-input').setValue('not-a-url')
    await wrapper.find('.know-panel__url-go').trigger('click')
    await flushPromises()
    expect(wrapper.find('.know-panel__error').exists()).toBe(true)
    expect(wrapper.find('.know-panel__error').text()).toContain('valid URL')
    expect(mockIngestUrl).not.toHaveBeenCalled()
  })

  it('calls ingestUrl for valid URL', async () => {
    mockIngestUrl.mockResolvedValue({
      filename: 'article.md',
      path: 'specialists/test-spec/article.md',
      title: 'Article',
      size: 2048,
      created_at: '2026-01-03T00:00:00Z',
    })
    const wrapper = await mountSuspended(SpecialistKnowledgePanel, {
      props: { specialistId: 'test-spec' },
    })
    await wrapper.find('.know-panel__url-input').setValue('https://example.com/article')
    await wrapper.find('.know-panel__url-go').trigger('click')
    await flushPromises()
    expect(mockIngestUrl).toHaveBeenCalledWith('test-spec', 'https://example.com/article')
  })

  it('delete button calls removeFile', async () => {
    useState('specialistFiles').value = {
      'test-spec': [
        { filename: 'notes.md', path: 'specialists/test-spec/notes.md', title: 'Notes', size: 1024, created_at: '2026-01-01T00:00:00Z' },
      ],
    }
    const wrapper = await mountSuspended(SpecialistKnowledgePanel, {
      props: { specialistId: 'test-spec' },
    })
    await wrapper.find('.know-panel__file-delete').trigger('click')
    expect(mockRemoveFile).toHaveBeenCalledWith('test-spec', 'notes.md')
  })

  it('file input accepts correct types', async () => {
    const wrapper = await mountSuspended(SpecialistKnowledgePanel, {
      props: { specialistId: 'test-spec' },
    })
    const input = wrapper.find('.know-panel__file-input')
    expect(input.attributes('accept')).toBe('.md,.txt,.pdf,.csv,.json')
    expect(input.attributes('multiple')).toBeDefined()
  })

  it('browse button triggers file input click', async () => {
    const wrapper = await mountSuspended(SpecialistKnowledgePanel, {
      props: { specialistId: 'test-spec' },
    })
    expect(wrapper.find('.know-panel__browse-btn').exists()).toBe(true)
  })
})
