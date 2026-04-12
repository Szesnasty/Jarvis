import { describe, it, expect } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import Orb from '~/components/Orb.vue'

describe('Orb', () => {
  it('renders without errors', async () => {
    const wrapper = await mountSuspended(Orb)
    expect(wrapper.exists()).toBe(true)
  })

  it('defaults to idle state', async () => {
    const wrapper = await mountSuspended(Orb)
    expect(wrapper.find('.orb.idle').exists()).toBe(true)
  })

  it('applies listening class when state is listening', async () => {
    const wrapper = await mountSuspended(Orb, { props: { state: 'listening' } })
    expect(wrapper.find('.orb.listening').exists()).toBe(true)
  })

  it('applies thinking class when state is thinking', async () => {
    const wrapper = await mountSuspended(Orb, { props: { state: 'thinking' } })
    expect(wrapper.find('.orb.thinking').exists()).toBe(true)
  })

  it('applies speaking class when state is speaking', async () => {
    const wrapper = await mountSuspended(Orb, { props: { state: 'speaking' } })
    expect(wrapper.find('.orb.speaking').exists()).toBe(true)
  })
})
