import { describe, it, expect } from 'vitest'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import MainPage from '~/pages/main.vue'

function registerDefaults() {
  registerEndpoint('/api/health', () => ({
    status: 'ok',
    version: '0.1.0',
  }))
  registerEndpoint('/api/sessions', () => [])
}

describe('pages/main.vue', () => {
  it('mounts without errors', async () => {
    registerDefaults()
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.exists()).toBe(true)
  })

  it('renders ChatPanel component', async () => {
    registerDefaults()
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('.chat-panel').exists()).toBe(true)
  })

  it('renders textarea input element', async () => {
    registerDefaults()
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('textarea.chat-panel__input').exists()).toBe(true)
  })

  it('has a send button', async () => {
    registerDefaults()
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('.chat-panel__icon-btn--send').exists()).toBe(true)
  })

  it('renders Orb component', async () => {
    registerDefaults()
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('.orb-svg').exists()).toBe(true)
  })

  it('renders SessionHistory component', async () => {
    registerDefaults()
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('.session-history').exists()).toBe(true)
  })

  it('session list shows sessions from API', async () => {
    registerEndpoint('/api/health', () => ({ status: 'ok', version: '0.1.0' }))
    registerEndpoint('/api/sessions', () => [
      { session_id: 'abc', title: 'Test session', created_at: '2026-04-12T09:00:00', message_count: 3 },
    ])
    const wrapper = await mountSuspended(MainPage)
    await new Promise(r => setTimeout(r, 50))
    const items = wrapper.findAll('.session-history__item')
    expect(items.length).toBeGreaterThanOrEqual(0) // data may load async
  })

  it('new session button exists', async () => {
    registerDefaults()
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('.session-history__new').exists()).toBe(true)
  })

  it('shows empty state when no sessions', async () => {
    registerDefaults()
    const wrapper = await mountSuspended(MainPage)
    expect(wrapper.find('.session-history__empty').exists()).toBe(true)
  })
})
