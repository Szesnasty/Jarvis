import { describe, it, expect } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import SpecialistBadge from '~/components/SpecialistBadge.vue'

const MOCK_SPECIALIST = {
  id: 'health-guide',
  name: 'Health Guide',
  icon: '🏥',
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
    expect(wrapper.find('.specialist-badge').exists()).toBe(false)
  })

  it('shows specialist name when active', async () => {
    const wrapper = await mountSuspended(SpecialistBadge, {
      props: { specialist: MOCK_SPECIALIST },
    })
    expect(wrapper.find('.specialist-badge__name').text()).toBe('Health Guide')
    expect(wrapper.find('.specialist-badge__icon').text()).toBe('🏥')
  })

  it('click emits click event', async () => {
    const wrapper = await mountSuspended(SpecialistBadge, {
      props: { specialist: MOCK_SPECIALIST },
    })
    await wrapper.find('.specialist-badge').trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })
})
