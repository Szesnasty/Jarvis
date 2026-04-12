import { describe, it, expect, vi } from 'vitest'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import OnboardingPage from '~/pages/onboarding.vue'

describe('pages/onboarding.vue', () => {
  it('renders API key input field', async () => {
    const wrapper = await mountSuspended(OnboardingPage)
    expect(wrapper.find('input[type="password"]').exists()).toBe(true)
  })

  it('renders Create Workspace button', async () => {
    const wrapper = await mountSuspended(OnboardingPage)
    expect(wrapper.find('button[type="submit"]').text()).toContain('Create Jarvis Workspace')
  })

  it('button disabled when input empty', async () => {
    const wrapper = await mountSuspended(OnboardingPage)
    const button = wrapper.find('button[type="submit"]')
    expect(button.attributes('disabled')).toBeDefined()
  })

  it('button enabled when input has text', async () => {
    const wrapper = await mountSuspended(OnboardingPage)
    const input = wrapper.find('input[type="password"]')
    await input.setValue('sk-ant-test-key')
    const button = wrapper.find('button[type="submit"]')
    expect(button.attributes('disabled')).toBeUndefined()
  })

  it('submit sends POST to /api/workspace/init', async () => {
    let receivedBody: any = null
    registerEndpoint('/api/workspace/init', {
      method: 'POST',
      handler: (event) => {
        receivedBody = true
        return { status: 'ok', workspace_path: '/tmp/Jarvis' }
      },
    })

    const wrapper = await mountSuspended(OnboardingPage)
    const input = wrapper.find('input[type="password"]')
    await input.setValue('sk-ant-test-key-123')
    await wrapper.find('form').trigger('submit')

    // Give async submit time to execute
    await new Promise(r => setTimeout(r, 100))
    expect(receivedBody).toBe(true)
  })

  it('API error shows error message', async () => {
    registerEndpoint('/api/workspace/init', {
      method: 'POST',
      handler: () => {
        throw createError({ statusCode: 409, statusMessage: 'Workspace already exists' })
      },
    })

    const wrapper = await mountSuspended(OnboardingPage)
    const input = wrapper.find('input[type="password"]')
    await input.setValue('sk-ant-test-key-123')
    await wrapper.find('form').trigger('submit')

    await new Promise(r => setTimeout(r, 100))
    const errorEl = wrapper.find('.onboarding__error')
    expect(errorEl.exists()).toBe(true)
  })

  it('network error shows connection error message', async () => {
    registerEndpoint('/api/workspace/init', {
      method: 'POST',
      handler: () => {
        throw createError({ statusCode: 500, statusMessage: 'Internal Server Error' })
      },
    })

    const wrapper = await mountSuspended(OnboardingPage)
    const input = wrapper.find('input[type="password"]')
    await input.setValue('sk-ant-test-key-123')
    await wrapper.find('form').trigger('submit')

    await new Promise(r => setTimeout(r, 100))
    const errorEl = wrapper.find('.onboarding__error')
    expect(errorEl.exists()).toBe(true)
  })
})
