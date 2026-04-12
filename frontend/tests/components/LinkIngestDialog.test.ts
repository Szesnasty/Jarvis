import { describe, it, expect, vi } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import LinkIngestDialog from '~/components/LinkIngestDialog.vue'

const ingestUrlMock = vi.fn()

vi.mock('~/composables/useApi', () => ({
  useApi: () => ({
    ingestUrl: ingestUrlMock,
  }),
}))

describe('components/LinkIngestDialog.vue', () => {
  it('renders when modelValue=true', async () => {
    const wrapper = await mountSuspended(LinkIngestDialog, {
      props: { modelValue: true },
    })
    expect(wrapper.find('.link-dialog').exists()).toBe(true)
    expect(wrapper.find('.link-dialog__title').text()).toBe('Import from URL')
  })

  it('detects YouTube URL type', async () => {
    const wrapper = await mountSuspended(LinkIngestDialog, {
      props: { modelValue: true },
    })
    await wrapper.find('.link-dialog__input').setValue('https://youtu.be/dQw4w9WgXcQ')
    expect(wrapper.find('.link-dialog__badge--yt').exists()).toBe(true)
  })

  it('detects webpage URL type', async () => {
    const wrapper = await mountSuspended(LinkIngestDialog, {
      props: { modelValue: true },
    })
    await wrapper.find('.link-dialog__input').setValue('https://example.com/article')
    expect(wrapper.find('.link-dialog__badge--web').exists()).toBe(true)
  })

  it('invalid URL disables import button', async () => {
    const wrapper = await mountSuspended(LinkIngestDialog, {
      props: { modelValue: true },
    })
    await wrapper.find('.link-dialog__input').setValue('notaurl')
    const btn = wrapper.find('.link-dialog__import-btn')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('successful import emits imported', async () => {
    ingestUrlMock.mockResolvedValueOnce({
      path: 'knowledge/article.md',
      title: 'Article',
      type: 'article',
      source: 'https://example.com/article',
      word_count: 100,
    })

    const wrapper = await mountSuspended(LinkIngestDialog, {
      props: { modelValue: true },
    })

    await wrapper.find('.link-dialog__input').setValue('https://example.com/article')
    await wrapper.find('.link-dialog__import-btn').trigger('click')

    expect(wrapper.emitted('imported')).toBeTruthy()
    expect(wrapper.find('.link-dialog__success').exists()).toBe(true)
  })

  it('error state shows error message', async () => {
    ingestUrlMock.mockRejectedValueOnce(new Error('Import failed'))

    const wrapper = await mountSuspended(LinkIngestDialog, {
      props: { modelValue: true },
    })

    await wrapper.find('.link-dialog__input').setValue('https://example.com/article')
    await wrapper.find('.link-dialog__import-btn').trigger('click')

    expect(wrapper.find('.link-dialog__error').exists()).toBe(true)
  })
})
