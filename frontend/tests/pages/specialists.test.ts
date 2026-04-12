import { describe, it, expect } from 'vitest'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import SpecialistsPage from '~/pages/specialists.vue'

const MOCK_SPECIALISTS = [
  { id: 'health-guide', name: 'Health Guide', icon: '🏥', source_count: 2, rule_count: 4 },
  { id: 'writer', name: 'Writer', icon: '✍️', source_count: 1, rule_count: 2 },
]

function registerSpecialistEndpoints(specialists = MOCK_SPECIALISTS) {
  registerEndpoint('/api/specialists', () => specialists)
  registerEndpoint('/api/specialists/active', () => ({ active: null }))
}

describe('pages/specialists.vue', () => {
  it('renders list of specialists from API', async () => {
    registerSpecialistEndpoints()
    const wrapper = await mountSuspended(SpecialistsPage)
    await flushPromises()
    const cards = wrapper.findAll('.specialist-card')
    expect(cards.length).toBe(2)
  })

  it('each card shows name and meta', async () => {
    registerSpecialistEndpoints()
    const wrapper = await mountSuspended(SpecialistsPage)
    await flushPromises()
    const names = wrapper.findAll('.specialist-card__name').map(n => n.text())
    expect(names).toContain('Health Guide')
    expect(names).toContain('Writer')
  })

  it('active specialist highlighted', async () => {
    registerEndpoint('/api/specialists', () => MOCK_SPECIALISTS)
    registerEndpoint('/api/specialists/active', () => ({
      id: 'health-guide',
      name: 'Health Guide',
      icon: '🏥',
      role: '',
      sources: [],
      style: {},
      rules: [],
      tools: [],
      examples: [],
      created_at: '',
      updated_at: '',
    }))
    const wrapper = await mountSuspended(SpecialistsPage)
    await flushPromises()
    await new Promise(r => setTimeout(r, 50))
    await flushPromises()
    const activeCards = wrapper.findAll('.specialist-card--active')
    expect(activeCards.length).toBe(1)
    expect(activeCards[0].find('.specialist-card__name').text()).toBe('Health Guide')
  })

  it('delete button calls API and removes card', async () => {
    registerSpecialistEndpoints()
    registerEndpoint('/api/specialists/health-guide', { handler: () => ({ status: 'deleted' }) })
    const wrapper = await mountSuspended(SpecialistsPage)
    await flushPromises()
    const deleteBtn = wrapper.find('.specialist-card__delete-btn')
    expect(deleteBtn.exists()).toBe(true)
    await deleteBtn.trigger('click')
    await flushPromises()
    const remaining = wrapper.findAll('.specialist-card')
    expect(remaining.length).toBe(1)
  })

  it('empty state shows create message', async () => {
    registerSpecialistEndpoints([])
    useState('activeSpecialist').value = null
    const wrapper = await mountSuspended(SpecialistsPage)
    await flushPromises()
    expect(wrapper.find('.specialists-page__empty').text()).toBe('Create your first specialist')
  })

  it('create button opens wizard', async () => {
    registerSpecialistEndpoints([])
    const wrapper = await mountSuspended(SpecialistsPage)
    await flushPromises()
    await wrapper.find('.specialists-page__create-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.specialist-wizard').exists()).toBe(true)
  })
})
