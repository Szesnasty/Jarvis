import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import SuggestionsPanel from '~/components/SuggestionsPanel.vue'
import type { NoteDetail } from '~/types'

const dismissMock = vi.fn()
const promoteMock = vi.fn()
const rerunMock = vi.fn()
const showSnackbar = vi.fn()

vi.mock('~/composables/useApi', () => ({
  useApi: () => ({
    dismissSuggestion: dismissMock,
    promoteSuggestion: promoteMock,
    rerunConnect: rerunMock,
  }),
}))

vi.mock('~/composables/useSnackbar', () => ({
  useSnackbar: () => ({ show: showSnackbar }),
}))

function makeNote(extra: Record<string, unknown> = {}): NoteDetail {
  return {
    path: 'projects/alpha.md',
    title: 'Alpha',
    content: '---\ntitle: Alpha\n---\n\nbody',
    updated_at: '2026-04-27T00:00:00Z',
    frontmatter: extra,
  }
}

beforeEach(() => {
  dismissMock.mockReset()
  promoteMock.mockReset()
  rerunMock.mockReset()
  showSnackbar.mockReset()
})

describe('components/SuggestionsPanel.vue', () => {
  it('renders nothing when there are no suggestions or aliases', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: { note: makeNote() },
    })
    expect(wrapper.find('.suggestions').exists()).toBe(false)
  })

  it('renders nothing for null note', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: { note: null },
    })
    expect(wrapper.find('.suggestions').exists()).toBe(false)
  })

  it('renders one item per suggestion with confidence and methods', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: [
            { path: 'projects/beta.md', confidence: 0.85, methods: ['bm25', 'note_emb'] },
            { path: 'people/eve.md', confidence: 0.62, methods: ['alias'] },
          ],
        }),
      },
    })
    const items = wrapper.findAll('.suggestions__item')
    expect(items).toHaveLength(2)
    expect(items[0]!.classes()).toContain('suggestions__item--strong')
    expect(items[1]!.classes()).toContain('suggestions__item--normal')
    expect(items[0]!.text()).toContain('85%')
    expect(items[0]!.text()).toContain('bm25')
  })

  it('shows aliases_matched separately', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: { note: makeNote({ aliases_matched: ['Łódź', 'Project Alpha'] }) },
    })
    expect(wrapper.find('.suggestions__aliases').text()).toContain('Łódź')
    expect(wrapper.find('.suggestions__aliases').text()).toContain('Project Alpha')
  })

  it('promote button calls API and emits changed', async () => {
    promoteMock.mockResolvedValueOnce({
      note_path: 'projects/alpha.md',
      target_path: 'projects/beta.md',
      related: ['projects/beta.md'],
    })
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: [
            { path: 'projects/beta.md', confidence: 0.85, methods: ['bm25'] },
          ],
        }),
      },
    })
    await wrapper.find('.suggestions__btn--promote').trigger('click')
    expect(promoteMock).toHaveBeenCalledWith('projects/alpha.md', 'projects/beta.md')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('dismiss button calls API and emits changed', async () => {
    dismissMock.mockResolvedValueOnce({
      note_path: 'projects/alpha.md',
      target_path: 'projects/beta.md',
      dismissed: true,
    })
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: [
            { path: 'projects/beta.md', confidence: 0.85, methods: ['bm25'] },
          ],
        }),
      },
    })
    await wrapper.find('.suggestions__btn--dismiss').trigger('click')
    expect(dismissMock).toHaveBeenCalledWith('projects/alpha.md', 'projects/beta.md')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('clicking a suggestion path emits open(path)', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: [
            { path: 'projects/beta.md', confidence: 0.85, methods: ['bm25'] },
          ],
        }),
      },
    })
    await wrapper.find('.suggestions__path').trigger('click')
    expect(wrapper.emitted('open')).toEqual([['projects/beta.md']])
  })

  it('re-run button calls rerunConnect with fast mode', async () => {
    rerunMock.mockResolvedValueOnce({
      note_path: 'projects/alpha.md',
      suggested: [],
      strong_count: 0,
      aliases_matched: [],
      graph_edges_added: 0,
    })
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: [
            { path: 'x.md', confidence: 0.7, methods: ['bm25'] },
          ],
        }),
      },
    })
    await wrapper.find('.suggestions__rerun').trigger('click')
    expect(rerunMock).toHaveBeenCalledWith('projects/alpha.md', 'fast')
    expect(wrapper.emitted('changed')).toBeTruthy()
  })

  it('ignores malformed suggested_related entries', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: [
            null,
            'just-a-string',
            { confidence: 0.9 },
            { path: 'ok.md', confidence: 0.7, methods: ['bm25'] },
          ],
        }),
      },
    })
    expect(wrapper.findAll('.suggestions__item')).toHaveLength(1)
  })

  // -------------------------------------------------------------------------
  // Step 26c: Keep all (N) button
  // -------------------------------------------------------------------------

  it('Keep-all button is hidden when fewer than 2 strong suggestions', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: [
            { path: 'a.md', confidence: 0.85, methods: ['bm25'] },
          ],
        }),
      },
    })
    expect(wrapper.find('.suggestions__btn--keep-all').exists()).toBe(false)
  })

  it('Keep-all button is hidden when more than 5 strong suggestions', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: Array.from({ length: 6 }, (_, i) => ({
            path: `n${i}.md`,
            confidence: 0.90,
            methods: ['bm25'],
          })),
        }),
      },
    })
    expect(wrapper.find('.suggestions__btn--keep-all').exists()).toBe(false)
  })

  it('Keep-all button visible and shows count when 2–5 strong suggestions', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: [
            { path: 'a.md', confidence: 0.82, methods: ['bm25'] },
            { path: 'b.md', confidence: 0.91, methods: ['alias'] },
            { path: 'c.md', confidence: 0.55, methods: ['bm25'] },  // not strong
          ],
        }),
      },
    })
    const btn = wrapper.find('.suggestions__btn--keep-all')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toContain('2')
  })

  it('Keep-all with N ≤ 3 promotes immediately and emits changed once', async () => {
    promoteMock.mockResolvedValue({ note_path: 'p/a.md', target_path: 'x.md', related: [] })
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: [
            { path: 'x.md', confidence: 0.85, methods: ['bm25'] },
            { path: 'y.md', confidence: 0.88, methods: ['alias'] },
          ],
        }),
      },
    })
    // Should not show confirmation panel first
    await wrapper.find('.suggestions__btn--keep-all').trigger('click')
    expect(wrapper.find('.suggestions__confirm-text').exists()).toBe(false)
    // Wait for async promotions
    await new Promise(r => setTimeout(r, 10))
    expect(promoteMock).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('changed')).toHaveLength(1)
    expect(showSnackbar).toHaveBeenCalledWith(expect.stringContaining('2'), expect.any(Object))
  })

  it('Keep-all with N = 4 shows inline confirmation before promoting', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: Array.from({ length: 4 }, (_, i) => ({
            path: `n${i}.md`,
            confidence: 0.85,
            methods: ['bm25'],
          })),
        }),
      },
    })
    await wrapper.find('.suggestions__btn--keep-all').trigger('click')
    // Confirmation should appear
    expect(wrapper.find('.suggestions__confirm-text').exists()).toBe(true)
    expect(promoteMock).not.toHaveBeenCalled()
  })

  it('Cancel hides the confirmation panel', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: Array.from({ length: 4 }, (_, i) => ({
            path: `n${i}.md`,
            confidence: 0.85,
            methods: ['bm25'],
          })),
        }),
      },
    })
    await wrapper.find('.suggestions__btn--keep-all').trigger('click')
    expect(wrapper.find('.suggestions__confirm-text').exists()).toBe(true)
    await wrapper.find('.suggestions__btn-text').trigger('click')
    expect(wrapper.find('.suggestions__confirm-text').exists()).toBe(false)
    expect(promoteMock).not.toHaveBeenCalled()
  })

  // -------------------------------------------------------------------------
  // Step 26c: Why? tooltip
  // -------------------------------------------------------------------------

  it('Why info icon shown when score_breakdown is present', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: [
            {
              path: 'x.md',
              confidence: 0.82,
              methods: ['bm25', 'alias'],
              score_breakdown: { bm25: 0.50, alias: 0.32 },
            },
          ],
        }),
      },
    })
    expect(wrapper.find('.suggestions__why').exists()).toBe(true)
  })

  it('Why info icon absent when score_breakdown is missing', async () => {
    const wrapper = await mountSuspended(SuggestionsPanel, {
      props: {
        note: makeNote({
          suggested_related: [
            { path: 'x.md', confidence: 0.82, methods: ['bm25'] },
          ],
        }),
      },
    })
    expect(wrapper.find('.suggestions__why').exists()).toBe(false)
  })
})
