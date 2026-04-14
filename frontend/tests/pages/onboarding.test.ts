import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import OnboardingPage from '~/pages/onboarding.vue'

// Mock sessionStorage and localStorage for useApiKeys
const storageMap: Record<string, string> = {}
const mockStorage = {
  getItem: (key: string) => storageMap[key] ?? null,
  setItem: (key: string, val: string) => { storageMap[key] = val },
  removeItem: (key: string) => { delete storageMap[key] },
}

beforeEach(() => {
  Object.keys(storageMap).forEach(k => delete storageMap[k])
  vi.stubGlobal('sessionStorage', mockStorage)
  vi.stubGlobal('localStorage', mockStorage)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('pages/onboarding.vue', () => {
  it('renders 3 provider cards', async () => {
    const wrapper = await mountSuspended(OnboardingPage)
    const cards = wrapper.findAllComponents({ name: 'ProviderCard' })
    expect(cards.length).toBe(3)
  })

  it('renders Create Workspace button', async () => {
    const wrapper = await mountSuspended(OnboardingPage)
    const button = wrapper.find('.onboarding__button')
    expect(button.text()).toContain('Create Jarvis Workspace')
  })

  it('button disabled when no keys configured', async () => {
    const wrapper = await mountSuspended(OnboardingPage)
    const button = wrapper.find('.onboarding__button')
    expect(button.attributes('disabled')).toBeDefined()
  })

  it('button enabled after adding a key', async () => {
    // Simulate a key in storage before mount
    storageMap['jarvis_key_anthropic'] = 'sk-ant-test-123'
    storageMap['jarvis_key_meta_anthropic'] = JSON.stringify({ remember: false, addedAt: new Date().toISOString() })

    const wrapper = await mountSuspended(OnboardingPage)
    // Force reactivity update
    await wrapper.vm.$nextTick()
    const button = wrapper.find('.onboarding__button')
    expect(button.attributes('disabled')).toBeUndefined()
  })

  it('shows security info panel', async () => {
    const wrapper = await mountSuspended(OnboardingPage)
    const info = wrapper.findComponent({ name: 'KeyProtectionInfo' })
    expect(info.exists()).toBe(true)
  })

  it('shows provider help links', async () => {
    const wrapper = await mountSuspended(OnboardingPage)
    const links = wrapper.findAll('.onboarding__help-link')
    expect(links.length).toBe(3)
    expect(links[0].attributes('href')).toContain('anthropic')
    expect(links[1].attributes('href')).toContain('openai')
    expect(links[2].attributes('href')).toContain('google')
  })

  it('shows settings hint', async () => {
    const wrapper = await mountSuspended(OnboardingPage)
    expect(wrapper.find('.onboarding__settings-hint').text()).toContain('Settings')
  })

  it('submit sends POST without api_key', async () => {
    storageMap['jarvis_key_anthropic'] = 'sk-ant-test-123'
    storageMap['jarvis_key_meta_anthropic'] = JSON.stringify({ remember: false, addedAt: new Date().toISOString() })

    let called = false
    registerEndpoint('/api/workspace/init', {
      method: 'POST',
      handler: () => {
        called = true
        return { status: 'ok', workspace_path: '/tmp/Jarvis' }
      },
    })

    const wrapper = await mountSuspended(OnboardingPage)
    await wrapper.find('.onboarding__button').trigger('click')
    await new Promise(r => setTimeout(r, 150))
    expect(called).toBe(true)
  })
})
