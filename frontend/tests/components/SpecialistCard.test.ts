import { describe, it, expect } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import SpecialistCard from '~/components/SpecialistCard.vue'

const MOCK_SPEC = {
  id: 'health-guide',
  name: 'Health Guide',
  icon: '\u{1F3E5}',
  source_count: 2,
  rule_count: 4,
  file_count: 3,
}

describe('SpecialistCard', () => {
  it('renders specialist name and icon', async () => {
    const wrapper = await mountSuspended(SpecialistCard, {
      props: { specialist: MOCK_SPEC },
    })
    expect(wrapper.find('.spec-card__name').text()).toBe('Health Guide')
    expect(wrapper.find('.spec-card__icon').text()).toBe('\u{1F3E5}')
  })

  it('shows stats: file count, source count, rule count', async () => {
    const wrapper = await mountSuspended(SpecialistCard, {
      props: { specialist: MOCK_SPEC },
    })
    const statsText = wrapper.find('.spec-card__stats').text()
    expect(statsText).toContain('3 files')
    expect(statsText).toContain('2 sources')
    expect(statsText).toContain('4 rules')
  })

  it('defaults file_count to 0 when missing', async () => {
    const spec = { ...MOCK_SPEC, file_count: 0 }
    const wrapper = await mountSuspended(SpecialistCard, {
      props: { specialist: spec },
    })
    expect(wrapper.find('.spec-card__stats').text()).toContain('0 files')
  })

  it('applies active class and shows tag when active', async () => {
    const wrapper = await mountSuspended(SpecialistCard, {
      props: { specialist: MOCK_SPEC, active: true },
    })
    expect(wrapper.find('.spec-card--active').exists()).toBe(true)
    expect(wrapper.find('.spec-card__active-tag').text()).toBe('Active')
    expect(wrapper.find('.spec-card__active-dot').exists()).toBe(true)
  })

  it('no active indicators when not active', async () => {
    const wrapper = await mountSuspended(SpecialistCard, {
      props: { specialist: MOCK_SPEC, active: false },
    })
    expect(wrapper.find('.spec-card--active').exists()).toBe(false)
    expect(wrapper.find('.spec-card__active-tag').exists()).toBe(false)
    expect(wrapper.find('.spec-card__active-dot').exists()).toBe(false)
  })

  it('activate button emits activate event', async () => {
    const wrapper = await mountSuspended(SpecialistCard, {
      props: { specialist: MOCK_SPEC },
    })
    await wrapper.find('.spec-card__btn--activate').trigger('click')
    expect(wrapper.emitted('activate')).toBeTruthy()
    expect(wrapper.emitted('activate')![0]).toEqual([MOCK_SPEC.id])
  })

  it('delete button emits delete event', async () => {
    const wrapper = await mountSuspended(SpecialistCard, {
      props: { specialist: MOCK_SPEC },
    })
    await wrapper.find('.spec-card__btn--delete').trigger('click')
    expect(wrapper.emitted('delete')).toBeTruthy()
    expect(wrapper.emitted('delete')![0]).toEqual([MOCK_SPEC.id])
  })

  it('expand button emits toggle-expand event', async () => {
    const wrapper = await mountSuspended(SpecialistCard, {
      props: { specialist: MOCK_SPEC },
    })
    await wrapper.find('.spec-card__btn--expand').trigger('click')
    expect(wrapper.emitted('toggle-expand')).toBeTruthy()
    expect(wrapper.emitted('toggle-expand')![0]).toEqual([MOCK_SPEC.id])
  })

  it('applies expanded class when expanded prop is true', async () => {
    const wrapper = await mountSuspended(SpecialistCard, {
      props: { specialist: MOCK_SPEC, expanded: true },
    })
    expect(wrapper.find('.spec-card--expanded').exists()).toBe(true)
    expect(wrapper.find('.spec-card__btn--expand-open').exists()).toBe(true)
  })

  it('clicking main row emits toggle-expand', async () => {
    const wrapper = await mountSuspended(SpecialistCard, {
      props: { specialist: MOCK_SPEC },
    })
    await wrapper.find('.spec-card__main').trigger('click')
    expect(wrapper.emitted('toggle-expand')).toBeTruthy()
  })
})
