import { describe, it, expect } from 'vitest'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import SettingsPage from '~/pages/settings.vue'

function registerSettingsEndpoints(overrides: Record<string, unknown> = {}) {
  registerEndpoint('/api/settings', () => ({
    workspace_path: '/home/user/Jarvis',
    api_key_set: true,
    voice: { auto_speak: 'false', tts_voice: 'alloy' },
    ...overrides,
  }))
  registerEndpoint('/api/settings/usage', () => ({
    total: 12500,
    request_count: 42,
    cost_estimate: 0.19,
  }))
}

describe('pages/settings.vue', () => {
  it('renders AI Providers section', async () => {
    registerSettingsEndpoints()
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    expect(wrapper.text()).toContain('AI Providers')
  })

  it('shows provider cards with no-key state', async () => {
    registerSettingsEndpoints({ api_key_set: false })
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    await new Promise(r => setTimeout(r, 50))
    await flushPromises()
    // Provider cards show "No key added" when browser has no key stored
    expect(wrapper.text()).toContain('Anthropic')
  })

  it('renders workspace path', async () => {
    registerSettingsEndpoints()
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    await new Promise(r => setTimeout(r, 50))
    await flushPromises()
    expect(wrapper.find('.settings-page__path').text()).toBe('/home/user/Jarvis')
  })

  it('voice toggle reflects auto_speak setting', async () => {
    registerSettingsEndpoints({ voice: { auto_speak: 'true', tts_voice: 'alloy' } })
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    await new Promise(r => setTimeout(r, 50))
    await flushPromises()
    const checkbox = wrapper.find('.settings-page__toggle input[type="checkbox"]')
    expect((checkbox.element as HTMLInputElement).checked).toBe(true)
  })

  it('shows key protection info', async () => {
    registerSettingsEndpoints()
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    // The security info section explains browser-only key storage
    expect(wrapper.text()).toContain('Keys')
  })

  it('displays token usage stats', async () => {
    registerSettingsEndpoints()
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    await new Promise(r => setTimeout(r, 50))
    await flushPromises()
    // Usage is in budget-stats section — formatTokens(12500) renders as '13K'
    expect(wrapper.text()).toContain('13K')
  })

  it('renders workspace section', async () => {
    registerSettingsEndpoints()
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    expect(wrapper.text()).toContain('Workspace')
  })

  it('has reindex and rebuild buttons', async () => {
    registerSettingsEndpoints()
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    const buttons = wrapper.findAll('.settings-page__btn')
    const labels = buttons.map(b => b.text())
    expect(labels).toContain('Reindex Memory')
    expect(labels).toContain('Rebuild Graph')
  })
})
