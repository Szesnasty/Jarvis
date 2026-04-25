import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import SmartConnectSection from '~/components/settings/SmartConnectSection.vue'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeProgressLines(lines: object[]): string {
  return lines.map(l => JSON.stringify(l)).join('\n') + '\n'
}

function mockFetch(lines: object[], status = 200) {
  const body = makeProgressLines(lines)
  const encoder = new TextEncoder()
  const encoded = encoder.encode(body)
  let offset = 0

  const readable = new ReadableStream({
    pull(controller) {
      if (offset < encoded.length) {
        controller.enqueue(encoded.slice(offset, encoded.length))
        offset = encoded.length
      } else {
        controller.close()
      }
    },
  })

  global.fetch = vi.fn().mockResolvedValue({
    ok: status === 200,
    status,
    body: readable,
  } as unknown as Response)
}

beforeEach(() => {
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe('components/settings/SmartConnectSection.vue', () => {
  it('renders the warning message above run-all button', async () => {
    const wrapper = await mountSuspended(SmartConnectSection)
    expect(wrapper.find('.smart-connect-section__warning').exists()).toBe(true)
    expect(wrapper.text()).toContain('Warning')
    expect(wrapper.text()).toContain('Dry-run preview')
  })

  it('renders three action buttons', async () => {
    const wrapper = await mountSuspended(SmartConnectSection)
    const btns = wrapper.findAll('.settings-page__btn')
    expect(btns.length).toBeGreaterThanOrEqual(3)
    const text = wrapper.text()
    expect(text).toContain('Run on all notes')
    expect(text).toContain('Run only on semantic orphans')
    expect(text).toContain('Dry-run preview')
  })

  it('does not render progress panel initially', async () => {
    const wrapper = await mountSuspended(SmartConnectSection)
    expect(wrapper.find('.smart-connect-section__progress').exists()).toBe(false)
  })

  // ---------------------------------------------------------------------------
  // Dry-run button calls endpoint with dry_run: true
  // ---------------------------------------------------------------------------

  it('dry-run button calls POST /api/connections/backfill with dry_run: true', async () => {
    mockFetch([{ done: 0, total: 0, suggestions_added: 0, notes_changed: 0, skipped: 0, orphans_found: 0, dry_run: true }])
    const wrapper = await mountSuspended(SmartConnectSection)

    const btns = wrapper.findAll('.settings-page__btn')
    const dryBtn = btns.find(b => b.text().includes('Dry-run'))!
    await dryBtn.trigger('click')
    await flushPromises()

    const [url, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toBe('/api/connections/backfill')
    const body = JSON.parse(opts.body as string)
    expect(body.dry_run).toBe(true)
  })

  // ---------------------------------------------------------------------------
  // Run on all notes calls without dry_run flag
  // ---------------------------------------------------------------------------

  it('run-all button calls endpoint without dry_run', async () => {
    mockFetch([{ done: 5, total: 5, suggestions_added: 2, notes_changed: 1, skipped: 0, orphans_found: 0, dry_run: false }])
    const wrapper = await mountSuspended(SmartConnectSection)

    const btns = wrapper.findAll('.settings-page__btn')
    const allBtn = btns.find(b => b.text().includes('Run on all'))!
    await allBtn.trigger('click')
    await flushPromises()

    const [, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    const body = JSON.parse(opts.body as string)
    expect(body.dry_run).toBeUndefined()
  })

  // ---------------------------------------------------------------------------
  // Only-orphans button sends only_orphans: true
  // ---------------------------------------------------------------------------

  it('orphans button sends only_orphans: true', async () => {
    mockFetch([{ done: 2, total: 2, suggestions_added: 1, notes_changed: 1, skipped: 0, orphans_found: 2, dry_run: false }])
    const wrapper = await mountSuspended(SmartConnectSection)

    const btns = wrapper.findAll('.settings-page__btn')
    const orphBtn = btns.find(b => b.text().includes('orphan'))!
    await orphBtn.trigger('click')
    await flushPromises()

    const [, opts] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    const body = JSON.parse(opts.body as string)
    expect(body.only_orphans).toBe(true)
  })

  // ---------------------------------------------------------------------------
  // Progress counters update from streamed JSON lines
  // ---------------------------------------------------------------------------

  it('progress counters update from streamed JSON', async () => {
    const lines = [
      { done: 10, total: 25, suggestions_added: 4, notes_changed: 3, skipped: 0, orphans_found: 0, dry_run: false },
      { done: 25, total: 25, suggestions_added: 9, notes_changed: 7, skipped: 1, orphans_found: 0, dry_run: false },
    ]
    mockFetch(lines)

    const wrapper = await mountSuspended(SmartConnectSection)
    const btns = wrapper.findAll('.settings-page__btn')
    await btns[0].trigger('click')
    await flushPromises()

    const statsText = wrapper.find('.smart-connect-section__progress-stats').text()
    expect(statsText).toContain('25')
    expect(statsText).toContain('9 suggestions')
  })

  // ---------------------------------------------------------------------------
  // Done message shown after stream closes
  // ---------------------------------------------------------------------------

  it('shows done message after stream closes (non-dry-run)', async () => {
    mockFetch([{ done: 5, total: 5, suggestions_added: 2, notes_changed: 2, skipped: 0, orphans_found: 0, dry_run: false }])
    const wrapper = await mountSuspended(SmartConnectSection)
    await wrapper.findAll('.settings-page__btn')[0].trigger('click')
    await flushPromises()

    expect(wrapper.find('.smart-connect-section__done').exists()).toBe(true)
    expect(wrapper.find('.smart-connect-section__done--dry').exists()).toBe(false)
  })

  it('shows dry-run done message when dry_run was true', async () => {
    mockFetch([{ done: 3, total: 3, suggestions_added: 1, notes_changed: 1, skipped: 0, orphans_found: 0, dry_run: true }])
    const wrapper = await mountSuspended(SmartConnectSection)

    const btns = wrapper.findAll('.settings-page__btn')
    const dryBtn = btns.find(b => b.text().includes('Dry-run'))!
    await dryBtn.trigger('click')
    await flushPromises()

    expect(wrapper.find('.smart-connect-section__done--dry').exists()).toBe(true)
  })

  // ---------------------------------------------------------------------------
  // Error state
  // ---------------------------------------------------------------------------

  it('shows error message when fetch fails', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('network error'))
    const wrapper = await mountSuspended(SmartConnectSection)
    await wrapper.findAll('.settings-page__btn')[0].trigger('click')
    await flushPromises()

    expect(wrapper.find('.smart-connect-section__error').text()).toContain('network error')
  })

  it('disables buttons while running', async () => {
    let resolve!: () => void
    const neverEnds = new Promise<void>(r => { resolve = r })
    global.fetch = vi.fn().mockReturnValue(neverEnds)

    const wrapper = await mountSuspended(SmartConnectSection)
    await wrapper.findAll('.settings-page__btn')[0].trigger('click')
    await flushPromises()

    const btns = wrapper.findAll('.settings-page__btn')
    btns.forEach(btn => {
      expect((btn.element as HTMLButtonElement).disabled).toBe(true)
    })

    resolve()
  })
})
