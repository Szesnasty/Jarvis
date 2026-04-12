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

  it('renders Jarvis heading', async () => {
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('h1').text()).toBe('Jarvis')
  })

  it('renders text input element', async () => {
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('input[type="text"]').exists()).toBe(true)
  })

  it('input is disabled', async () => {
    registerEndpoint('/api/health', () => ({
      status: 'ok',
      version: '0.1.0',
    }))
    const wrapper = await mountSuspended(MainPage)
    const input = wrapper.find('input[type="text"]')
    expect(input.attributes('disabled')).toBeDefined()
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
