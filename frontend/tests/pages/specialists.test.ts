import { describe, it, expect } from 'vitest'
import { mountSuspended, registerEndpoint } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import SpecialistsPage from '~/pages/specialists.vue'

const MOCK_SPECIALISTS = [
  { id: 'health-guide', name: 'Health Guide', icon: '\u{1F3E5}', source_count: 2, rule_count: 4, file_count: 3 },
  { id: 'writer', name: 'Writer', icon: '\u{270D}\u{FE0F}', source_count: 1, rule_count: 2, file_count: 0 },
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
    const cards = wrapper.findAll('.spec-card')
    expect(cards.length).toBe(2)
  })

  it('each card shows name', async () => {
    registerSpecialistEndpoints()
    const wrapper = await mountSuspended(SpecialistsPage)
    await flushPromises()
    const names = wrapper.findAll('.spec-card__name').map(n => n.text())
    expect(names).toContain('Health Guide')
    expect(names).toContain('Writer')
  })

  it('active specialist highlighted', async () => {
    registerEndpoint('/api/specialists', () => MOCK_SPECIALISTS)
    registerEndpoint('/api/specialists/active', () => ({
      id: 'health-guide',
      name: 'Health Guide',
      icon: '\u{1F3E5}',
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
    const activeCards = wrapper.findAll('.spec-card--active')
    expect(activeCards.length).toBe(1)
    expect(activeCards[0].find('.spec-card__name').text()).toBe('Health Guide')
  })

  it('empty state shows create message', async () => {
    registerSpecialistEndpoints([])
    useState('activeSpecialist').value = null
    const wrapper = await mountSuspended(SpecialistsPage)
    await flushPromises()
    expect(wrapper.find('.spec-page__empty').exists()).toBe(true)
    expect(wrapper.find('.spec-page__empty-text').text()).toContain('No specialists yet')
  })

  it('create button opens wizard', async () => {
    registerSpecialistEndpoints()
    const wrapper = await mountSuspended(SpecialistsPage)
    await flushPromises()
    await wrapper.find('.spec-page__create-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.wiz').exists()).toBe(true)
  })

  it('empty state button opens wizard', async () => {
    registerSpecialistEndpoints([])
    useState('activeSpecialist').value = null
    const wrapper = await mountSuspended(SpecialistsPage)
    await flushPromises()
    await wrapper.find('.spec-page__empty-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.wiz').exists()).toBe(true)
  })

  it('delete button opens confirmation dialog', async () => {
    registerSpecialistEndpoints()
    const wrapper = await mountSuspended(SpecialistsPage)
    await flushPromises()
    await wrapper.find('.spec-card__btn--delete').trigger('click')
    await flushPromises()
    // ConfirmDialog uses Teleport to="body", check in document
    const dialog = document.querySelector('.confirm-dialog')
    expect(dialog).toBeTruthy()
  })

  it('header shows title and subtitle', async () => {
    registerSpecialistEndpoints()
    const wrapper = await mountSuspended(SpecialistsPage)
    await flushPromises()
    expect(wrapper.find('.spec-page__title').text()).toBe('Specialists')
    expect(wrapper.find('.spec-page__subtitle').exists()).toBe(true)
  })
})
