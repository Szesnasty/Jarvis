import { describe, it, expect } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import StatusBar from '~/components/StatusBar.vue'

describe('StatusBar', () => {
  it('renders Jarvis label text', async () => {
    const wrapper = await mountSuspended(StatusBar)
    expect(wrapper.text()).toContain('Jarvis')
  })

  it('shows status text from appState', async () => {
    const wrapper = await mountSuspended(StatusBar)
    // Default status is 'unknown' → shows 'Checking...'
    expect(wrapper.text()).toContain('Checking...')
  })

  it('applies .online CSS class when status is online', async () => {
    useState('backendStatus').value = 'online'
    const wrapper = await mountSuspended(StatusBar)
    expect(wrapper.find('.online').exists()).toBe(true)
  })

  it('applies .offline CSS class when status is offline', async () => {
    useState('backendStatus').value = 'offline'
    const wrapper = await mountSuspended(StatusBar)
    expect(wrapper.find('.offline').exists()).toBe(true)
  })

  it('applies .unknown CSS class when status is unknown', async () => {
    useState('backendStatus').value = 'unknown'
    const wrapper = await mountSuspended(StatusBar)
    expect(wrapper.find('.unknown').exists()).toBe(true)
  })
})
