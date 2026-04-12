import { describe, it, expect } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import SpecialistWizard from '~/components/SpecialistWizard.vue'

describe('SpecialistWizard', () => {
  it('renders step 1 with name input', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    expect(wrapper.find('.specialist-wizard__input').exists()).toBe(true)
    expect(wrapper.find('.specialist-wizard__step--active').text()).toContain('1')
  })

  it('step 2: role textarea', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    // Fill name and go to step 2
    const input = wrapper.find('.specialist-wizard__input')
    await input.setValue('Test Specialist')
    await wrapper.find('.specialist-wizard__next-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.specialist-wizard__textarea').exists()).toBe(true)
    expect(wrapper.find('.specialist-wizard__step--active').text()).toContain('2')
  })

  it('step 3: source folder picker', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await wrapper.find('.specialist-wizard__input').setValue('Test')
    await wrapper.find('.specialist-wizard__next-btn').trigger('click')
    await flushPromises()
    await wrapper.find('.specialist-wizard__next-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.specialist-wizard__step--active').text()).toContain('3')
    expect(wrapper.find('.specialist-wizard__textarea').exists()).toBe(true)
  })

  it('step 4: style inputs', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await wrapper.find('.specialist-wizard__input').setValue('Test')
    for (let i = 0; i < 3; i++) {
      await wrapper.find('.specialist-wizard__next-btn').trigger('click')
      await flushPromises()
    }
    expect(wrapper.find('.specialist-wizard__step--active').text()).toContain('4')
    const inputs = wrapper.findAll('.specialist-wizard__input')
    expect(inputs.length).toBeGreaterThanOrEqual(3)
  })

  it('step 5: rules textarea', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await wrapper.find('.specialist-wizard__input').setValue('Test')
    for (let i = 0; i < 4; i++) {
      await wrapper.find('.specialist-wizard__next-btn').trigger('click')
      await flushPromises()
    }
    expect(wrapper.find('.specialist-wizard__step--active').text()).toContain('5')
    expect(wrapper.find('.specialist-wizard__textarea').exists()).toBe(true)
  })

  it('step 6: tool checkboxes', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await wrapper.find('.specialist-wizard__input').setValue('Test')
    for (let i = 0; i < 5; i++) {
      await wrapper.find('.specialist-wizard__next-btn').trigger('click')
      await flushPromises()
    }
    expect(wrapper.find('.specialist-wizard__step--active').text()).toContain('6')
    const checkboxes = wrapper.findAll('.specialist-wizard__checkbox')
    expect(checkboxes.length).toBeGreaterThan(0)
  })

  it('step 7: review summary', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await wrapper.find('.specialist-wizard__input').setValue('My Specialist')
    for (let i = 0; i < 6; i++) {
      await wrapper.find('.specialist-wizard__next-btn').trigger('click')
      await flushPromises()
    }
    expect(wrapper.find('.specialist-wizard__step--active').text()).toContain('7')
    expect(wrapper.find('.specialist-wizard__review').text()).toContain('My Specialist')
  })

  it('back button returns to previous step', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await wrapper.find('.specialist-wizard__input').setValue('Test')
    await wrapper.find('.specialist-wizard__next-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.specialist-wizard__step--active').text()).toContain('2')
    await wrapper.find('.specialist-wizard__back-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.specialist-wizard__step--active').text()).toContain('1')
  })

  it('validation prevents skip with empty name', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    const btn = wrapper.find('.specialist-wizard__next-btn')
    expect((btn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('submit emits save event', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await wrapper.find('.specialist-wizard__input').setValue('Test Spec')
    for (let i = 0; i < 6; i++) {
      await wrapper.find('.specialist-wizard__next-btn').trigger('click')
      await flushPromises()
    }
    await wrapper.find('.specialist-wizard__submit-btn').trigger('click')
    expect(wrapper.emitted('save')).toBeTruthy()
    expect(wrapper.emitted('save')![0][0]).toHaveProperty('name', 'Test Spec')
  })
})
