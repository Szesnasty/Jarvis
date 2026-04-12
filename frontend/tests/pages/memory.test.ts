import { describe, it, expect } from 'vitest'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import MemoryPage from '~/pages/memory.vue'

const MOCK_NOTES = [
  {
    path: 'inbox/hello.md',
    title: 'Hello World',
    folder: 'inbox',
    tags: ['test'],
    updated_at: '2026-01-01T00:00:00',
    word_count: 42,
  },
  {
    path: 'projects/jarvis.md',
    title: 'Jarvis Project',
    folder: 'projects',
    tags: ['project', 'ai'],
    updated_at: '2026-01-02T00:00:00',
    word_count: 120,
  },
]

const MOCK_DETAIL = {
  path: 'inbox/hello.md',
  title: 'Hello World',
  content: '---\ntitle: Hello World\ntags: [test]\n---\n\nHello content.',
  frontmatter: { title: 'Hello World', tags: ['test'] },
  updated_at: '2026-01-01T00:00:00',
}

function registerNotesEndpoints(notes = MOCK_NOTES) {
  registerEndpoint('/api/memory/notes', () => notes)
  registerEndpoint('/api/memory/notes/inbox/hello.md', () => MOCK_DETAIL)
}

describe('pages/memory.vue', () => {
  it('renders folder buttons from API data', async () => {
    registerNotesEndpoints()
    const wrapper = await mountSuspended(MemoryPage)
    await flushPromises()
    const buttons = wrapper.findAll('.note-list__folder-btn')
    expect(buttons.length).toBeGreaterThanOrEqual(2)
    const text = buttons.map((b) => b.text())
    expect(text).toContain('inbox')
    expect(text).toContain('projects')
  })

  it('shows empty state message when no notes', async () => {
    registerNotesEndpoints([])
    const wrapper = await mountSuspended(MemoryPage)
    await flushPromises()
    expect(wrapper.find('.note-list__empty').text()).toBe('No notes yet')
  })

  it('clicking folder toggles active state', async () => {
    registerNotesEndpoints()
    const wrapper = await mountSuspended(MemoryPage)
    await flushPromises()
    const btn = wrapper.findAll('.note-list__folder-btn').find((b) => b.text() === 'inbox')
    expect(btn).toBeDefined()
    await btn!.trigger('click')
    await flushPromises()
    expect(btn!.classes()).toContain('note-list__folder-btn--active')
  })

  it('clicking note shows content in preview', async () => {
    registerNotesEndpoints()
    const wrapper = await mountSuspended(MemoryPage)
    await flushPromises()
    const item = wrapper.find('.note-list__item')
    expect(item.exists()).toBe(true)
    await item.trigger('click')
    await flushPromises()
    expect(wrapper.find('.note-viewer__title').text()).toBe('Hello World')
  })

  it('search input triggers API search on Enter', async () => {
    registerNotesEndpoints()
    const wrapper = await mountSuspended(MemoryPage)
    await flushPromises()
    const input = wrapper.find('.note-list__search-input')
    await input.setValue('python')
    await input.trigger('keydown.enter')
    expect(input.element.value).toBe('python')
  })

  it('search results replace folder view', async () => {
    registerNotesEndpoints()
    const wrapper = await mountSuspended(MemoryPage)
    await flushPromises()
    const input = wrapper.find('.note-list__search-input')
    await input.setValue('jarvis')
    await input.trigger('keydown.enter')
    await flushPromises()
    const active = wrapper.findAll('.note-list__folder-btn--active')
    expect(active.length).toBe(0)
  })

  it('clear search restores folder view', async () => {
    registerNotesEndpoints()
    const wrapper = await mountSuspended(MemoryPage)
    await flushPromises()
    const input = wrapper.find('.note-list__search-input')
    await input.setValue('test')
    await input.trigger('keydown.enter')
    await flushPromises()
    const clearBtn = wrapper.find('.note-list__clear')
    expect(clearBtn.exists()).toBe(true)
    await clearBtn.trigger('click')
    expect(input.element.value).toBe('')
  })

  it('select note empty state shows placeholder', async () => {
    registerNotesEndpoints()
    const wrapper = await mountSuspended(MemoryPage)
    await flushPromises()
    expect(wrapper.find('.note-viewer__empty').text()).toBe('Select a note to view')
  })
})
