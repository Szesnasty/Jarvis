import { describe, it, expect } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import TranscriptBar from '~/components/TranscriptBar.vue'

describe('TranscriptBar', () => {
  it('hidden when no transcript', async () => {
    const wrapper = await mountSuspended(TranscriptBar, {
      props: { transcript: '', visible: false },
    })
    expect(wrapper.find('.transcript-bar').exists()).toBe(false)
  })

  it('shows transcript while visible', async () => {
    const wrapper = await mountSuspended(TranscriptBar, {
      props: { transcript: 'hello jarvis', visible: true },
    })
    expect(wrapper.find('.transcript-bar').text()).toBe('hello jarvis')
  })

  it('hidden when visible but empty transcript', async () => {
    const wrapper = await mountSuspended(TranscriptBar, {
      props: { transcript: '', visible: true },
    })
    expect(wrapper.find('.transcript-bar').exists()).toBe(false)
  })

  it('updates when transcript changes', async () => {
    const wrapper = await mountSuspended(TranscriptBar, {
      props: { transcript: 'first', visible: true },
    })
    expect(wrapper.find('.transcript-bar').text()).toBe('first')

    await wrapper.setProps({ transcript: 'first second' })
    expect(wrapper.find('.transcript-bar').text()).toBe('first second')
  })
})
