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
  it('renders masked API key when key is set', async () => {
    registerSettingsEndpoints()
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    await new Promise(r => setTimeout(r, 50))
    await flushPromises()
    expect(wrapper.find('.settings-page__masked-key').text()).toContain('••••••••')
  })

  it('shows "Not set" when API key is missing', async () => {
    registerSettingsEndpoints({ api_key_set: false })
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    await new Promise(r => setTimeout(r, 50))
    await flushPromises()
    expect(wrapper.find('.settings-page__masked-key').text()).toContain('Not set')
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

  it('update key button clears input on success', async () => {
    registerSettingsEndpoints()
    registerEndpoint('/api/settings/api-key', {
      method: 'PATCH',
      handler: () => ({ status: 'ok' }),
    })
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    const input = wrapper.find('.settings-page__input')
    await input.setValue('sk-new-key')
    await wrapper.find('.settings-page__btn').trigger('click')
    await flushPromises()
    await new Promise(r => setTimeout(r, 100))
    await flushPromises()
    expect((input.element as HTMLInputElement).value).toBe('')
  })

  it('displays token usage stats', async () => {
    registerSettingsEndpoints()
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    await new Promise(r => setTimeout(r, 50))
    await flushPromises()
    const usageSection = wrapper.find('.settings-page__usage')
    expect(usageSection.exists()).toBe(true)
    expect(usageSection.text()).toContain('12500')
    expect(usageSection.text()).toContain('42')
  })

  it('renders Obsidian helper', async () => {
    registerSettingsEndpoints()
    const wrapper = await mountSuspended(SettingsPage)
    await flushPromises()
    expect(wrapper.text()).toContain('Obsidian')
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
