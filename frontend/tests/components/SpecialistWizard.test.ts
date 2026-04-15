import { describe, it, expect } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import SpecialistWizard from '~/components/SpecialistWizard.vue'

async function goToStep(wrapper: ReturnType<Awaited<typeof mountSuspended>>, targetStep: number) {
  // Fill name first (required for step 1)
  if (targetStep > 1) {
    await wrapper.find('.wiz__input').setValue('Test Specialist')
  }
  for (let i = 1; i < targetStep; i++) {
    await wrapper.find('.wiz__next-btn').trigger('click')
    await flushPromises()
  }
}

describe('SpecialistWizard', () => {
  it('renders step 1 with name input', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    expect(wrapper.find('.wiz__input').exists()).toBe(true)
    expect(wrapper.find('.wiz__step--active').text()).toContain('1')
  })

  it('validation prevents proceeding with empty name', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    const btn = wrapper.find('.wiz__next-btn')
    expect((btn.element as HTMLButtonElement).disabled).toBe(true)
  })

  it('step 2: role textarea', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await goToStep(wrapper, 2)
    expect(wrapper.find('.wiz__textarea').exists()).toBe(true)
    expect(wrapper.find('.wiz__step--active').text()).toContain('2')
  })

  it('step 3: knowledge sources with dropzone', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await goToStep(wrapper, 3)
    expect(wrapper.find('.wiz__step--active').text()).toContain('3')
    expect(wrapper.find('.wiz__dropzone').exists()).toBe(true)
  })

  it('step 3: shows auto-created folder path based on name', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await wrapper.find('.wiz__input').setValue('Health Guide')
    await wrapper.find('.wiz__next-btn').trigger('click')
    await flushPromises()
    await wrapper.find('.wiz__next-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.wiz__code').text()).toContain('health-guide')
  })

  it('step 3: dropzone exists for file staging', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await goToStep(wrapper, 3)
    const dropzone = wrapper.find('.wiz__dropzone')
    expect(dropzone.exists()).toBe(true)
  })

  it('step 4: style inputs', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await goToStep(wrapper, 4)
    expect(wrapper.find('.wiz__step--active').text()).toContain('4')
    const inputs = wrapper.findAll('.wiz__input')
    expect(inputs.length).toBeGreaterThanOrEqual(2)
  })

  it('step 5: rules textarea', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await goToStep(wrapper, 5)
    expect(wrapper.find('.wiz__step--active').text()).toContain('5')
    expect(wrapper.find('.wiz__textarea').exists()).toBe(true)
  })

  it('step 6: tool checkboxes as grid', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await goToStep(wrapper, 6)
    expect(wrapper.find('.wiz__step--active').text()).toContain('6')
    const tools = wrapper.findAll('.wiz__tool')
    expect(tools.length).toBeGreaterThan(0)
  })

  it('step 7: review summary', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await goToStep(wrapper, 7)
    expect(wrapper.find('.wiz__step--active').text()).toContain('7')
    // Name was set to 'Test Specialist' by goToStep helper
    expect(wrapper.find('.wiz__review').text()).toContain('Test Specialist')
  })

  it('step 7: review shows stat grid', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await wrapper.find('.wiz__input').setValue('Test')
    await goToStep(wrapper, 7)
    const stats = wrapper.findAll('.wiz__review-stat')
    expect(stats.length).toBeGreaterThanOrEqual(4) // staged files, source folders, rules, tools (+ model)
  })

  it('back button returns to previous step', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await goToStep(wrapper, 2)
    expect(wrapper.find('.wiz__step--active').text()).toContain('2')
    await wrapper.find('.wiz__back-btn').trigger('click')
    await flushPromises()
    expect(wrapper.find('.wiz__step--active').text()).toContain('1')
  })

  it('cancel button emits cancel event', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await wrapper.find('.wiz__cancel-btn').trigger('click')
    expect(wrapper.emitted('cancel')).toBeTruthy()
  })

  it('submit emits save event with form data and staged files', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    // goToStep sets name to 'Test Specialist'
    await goToStep(wrapper, 7)
    await wrapper.find('.wiz__submit-btn').trigger('click')
    expect(wrapper.emitted('save')).toBeTruthy()
    const payload = wrapper.emitted('save')![0]
    expect(payload[0]).toHaveProperty('name', 'Test Specialist')
    expect(Array.isArray(payload[1])).toBe(true) // staged files array
  })

  it('step indicators are clickable for completed steps', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    await goToStep(wrapper, 3)
    // Click back to step 1
    const steps = wrapper.findAll('.wiz__step')
    await steps[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('.wiz__step--active').text()).toContain('1')
  })

  it('exposes resetSubmitting method', async () => {
    const wrapper = await mountSuspended(SpecialistWizard)
    expect(typeof (wrapper.vm as any).resetSubmitting).toBe('function')
  })
})
