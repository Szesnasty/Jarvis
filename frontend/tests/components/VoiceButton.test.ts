import { describe, it, expect } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import VoiceButton from '~/components/VoiceButton.vue'

describe('VoiceButton', () => {
  it('renders mic icon when idle', async () => {
    const wrapper = await mountSuspended(VoiceButton, {
      props: { state: 'idle', supported: true },
    })
    expect(wrapper.find('.voice-button__icon--mic').exists()).toBe(true)
  })

  it('renders stop icon when listening', async () => {
    const wrapper = await mountSuspended(VoiceButton, {
      props: { state: 'listening', supported: true },
    })
    expect(wrapper.find('.voice-button__icon--stop').exists()).toBe(true)
  })

  it('applies listening CSS class when listening', async () => {
    const wrapper = await mountSuspended(VoiceButton, {
      props: { state: 'listening', supported: true },
    })
    expect(wrapper.find('.voice-button.listening').exists()).toBe(true)
  })

  it('click emits toggle when idle', async () => {
    const wrapper = await mountSuspended(VoiceButton, {
      props: { state: 'idle', supported: true },
    })
    await wrapper.find('.voice-button').trigger('click')
    expect(wrapper.emitted('toggle')).toHaveLength(1)
  })

  it('click emits toggle when listening', async () => {
    const wrapper = await mountSuspended(VoiceButton, {
      props: { state: 'listening', supported: true },
    })
    await wrapper.find('.voice-button').trigger('click')
    expect(wrapper.emitted('toggle')).toHaveLength(1)
  })

  it('disabled when voice not supported', async () => {
    const wrapper = await mountSuspended(VoiceButton, {
      props: { state: 'idle', supported: false },
    })
    expect(wrapper.find('.voice-button').attributes('disabled')).toBeDefined()
  })

  it('has aria-label for accessibility', async () => {
    const wrapper = await mountSuspended(VoiceButton, {
      props: { state: 'idle', supported: true },
    })
    expect(wrapper.find('.voice-button').attributes('aria-label')).toBeTruthy()
  })
})
