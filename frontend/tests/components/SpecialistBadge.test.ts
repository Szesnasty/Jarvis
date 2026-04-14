import { describe, it, expect } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import SpecialistBadge from '~/components/SpecialistBadge.vue'

const MOCK_SPECIALIST = {
  id: 'health-guide',
  name: 'Health Guide',
  icon: '\u{1F3E5}',
  role: 'Health assistant',
  sources: [],
  style: {},
  rules: [],
  tools: [],
  examples: [],
  created_at: '',
  updated_at: '',
}

describe('SpecialistBadge', () => {
  it('hidden when no specialist active', async () => {
    const wrapper = await mountSuspended(SpecialistBadge, {
      props: { specialist: null },
    })
    expect(wrapper.find('.spec-badge').exists()).toBe(false)
  })

  it('shows specialist name and icon when active', async () => {
    const wrapper = await mountSuspended(SpecialistBadge, {
      props: { specialist: MOCK_SPECIALIST },
    })
    expect(wrapper.find('.spec-badge__name').text()).toBe('Health Guide')
    expect(wrapper.find('.spec-badge__icon').text()).toBe('\u{1F3E5}')
  })

  it('shows pulsing active dot', async () => {
    const wrapper = await mountSuspended(SpecialistBadge, {
      props: { specialist: MOCK_SPECIALIST },
    })
    expect(wrapper.find('.spec-badge__dot').exists()).toBe(true)
  })

  it('click emits click event', async () => {
    const wrapper = await mountSuspended(SpecialistBadge, {
      props: { specialist: MOCK_SPECIALIST },
    })
    await wrapper.find('.spec-badge').trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })

  it('close button emits deactivate', async () => {
    const wrapper = await mountSuspended(SpecialistBadge, {
      props: { specialist: MOCK_SPECIALIST },
    })
    await wrapper.find('.spec-badge__close').trigger('click')
    expect(wrapper.emitted('deactivate')).toBeTruthy()
    // Should not also emit click (stopPropagation)
    expect(wrapper.emitted('click')).toBeFalsy()
  })
})
