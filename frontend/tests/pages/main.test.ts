import { describe, it, expect } from 'vitest'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import MainPage from '~/pages/main.vue'

describe('pages/main.vue', () => {
  it('mounts without errors', async () => {
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('renders StatusBar component', async () => {
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('.status-bar').exists()).toBe(true)
  })

  it('renders ChatPanel component', async () => {
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('.chat-panel').exists()).toBe(true)
  })

  it('renders text input element', async () => {
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
  })

  it('has a send button', async () => {
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('.chat-panel__send').exists()).toBe(true)
  })

  it('renders Orb component', async () => {
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('.orb').exists()).toBe(true)
  })
})
