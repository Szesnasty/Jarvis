import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import { nextTick } from 'vue'
import JarvisSelfCard from '~/components/JarvisSelfCard.vue'

const fetchMock = vi.fn()
const updateMock = vi.fn()

vi.mock('~/composables/useApi', () => ({
  useApi: () => ({
    fetchJarvisConfig: fetchMock,
    updateJarvisConfig: updateMock,
  }),
}))

// Resolves microtasks for both the API mock and Vue's reactivity flush.
async function flush() {
  await Promise.resolve()
  await Promise.resolve()
  await nextTick()
}

describe('components/JarvisSelfCard.vue', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    updateMock.mockReset()
  })

  it('loads config and shows checkbox unchecked when no override is set', async () => {
    fetchMock.mockResolvedValueOnce({ system_prompt: '', behavior_extension: '' })
    const wrapper = await mountSuspended(JarvisSelfCard)
    await flush()

    const checkbox = wrapper.find<HTMLInputElement>('input[type="checkbox"]')
    expect(checkbox.element.checked).toBe(false)
    // override textarea is hidden when checkbox is off
    const textareas = wrapper.findAll('textarea')
    expect(textareas).toHaveLength(1) // only the extension textarea
  })

  it('shows checkbox checked and override textarea pre-filled when override exists', async () => {
    fetchMock.mockResolvedValueOnce({
      system_prompt: 'My custom prompt',
      behavior_extension: 'sign as J',
    })
    const wrapper = await mountSuspended(JarvisSelfCard)
    await flush()

    const checkbox = wrapper.find<HTMLInputElement>('input[type="checkbox"]')
    expect(checkbox.element.checked).toBe(true)
    const textareas = wrapper.findAll<HTMLTextAreaElement>('textarea')
    expect(textareas).toHaveLength(2)
    expect(textareas[0]!.element.value).toBe('My custom prompt')
    expect(textareas[1]!.element.value).toBe('sign as J')
  })

  it('unchecking override + saving sends empty system_prompt (defaults restored)', async () => {
    fetchMock.mockResolvedValueOnce({
      system_prompt: 'Old override text',
      behavior_extension: 'keep me',
    })
    updateMock.mockResolvedValueOnce({
      system_prompt: '',
      behavior_extension: 'keep me',
    })

    const wrapper = await mountSuspended(JarvisSelfCard)
    await flush()

    // Sanity: starts checked
    const checkbox = wrapper.find<HTMLInputElement>('input[type="checkbox"]')
    expect(checkbox.element.checked).toBe(true)

    // Uncheck the override
    checkbox.element.checked = false
    await checkbox.trigger('change')

    // Override textarea disappears immediately
    expect(wrapper.findAll('textarea')).toHaveLength(1)

    // Save button is now enabled (form is dirty)
    const saveBtn = wrapper.find<HTMLButtonElement>('.jarvis-card__save')
    expect(saveBtn.element.disabled).toBe(false)

    await saveBtn.trigger('click')
    await flush()

    expect(updateMock).toHaveBeenCalledTimes(1)
    expect(updateMock).toHaveBeenCalledWith({
      system_prompt: '', // <- this is the key: empty string returns Jarvis to default
      behavior_extension: 'keep me',
    })

    // After save, checkbox stays unchecked (matches the saved state)
    expect(checkbox.element.checked).toBe(false)
  })

  it('save button is disabled when form is not dirty', async () => {
    fetchMock.mockResolvedValueOnce({ system_prompt: '', behavior_extension: '' })
    const wrapper = await mountSuspended(JarvisSelfCard)
    await flush()

    const saveBtn = wrapper.find<HTMLButtonElement>('.jarvis-card__save')
    expect(saveBtn.element.disabled).toBe(true)
  })

  it('typing in extension textarea enables save', async () => {
    fetchMock.mockResolvedValueOnce({ system_prompt: '', behavior_extension: '' })
    const wrapper = await mountSuspended(JarvisSelfCard)
    await flush()

    const ext = wrapper.find<HTMLTextAreaElement>('textarea')
    await ext.setValue('hello')

    const saveBtn = wrapper.find<HTMLButtonElement>('.jarvis-card__save')
    expect(saveBtn.element.disabled).toBe(false)
  })

  it('checking override reveals an EMPTY textarea (default never prefilled)', async () => {
    fetchMock.mockResolvedValueOnce({ system_prompt: '', behavior_extension: '' })
    const wrapper = await mountSuspended(JarvisSelfCard)
    await flush()

    const checkbox = wrapper.find<HTMLInputElement>('input[type="checkbox"]')
    checkbox.element.checked = true
    await checkbox.trigger('change')

    const textareas = wrapper.findAll<HTMLTextAreaElement>('textarea')
    expect(textareas).toHaveLength(2)
    // Override textarea (the first one) must be empty — the user writes from
    // a blank canvas, never sees the built-in default.
    expect(textareas[0]!.element.value).toBe('')
  })

  it('shows error when save fails', async () => {
    fetchMock.mockResolvedValueOnce({ system_prompt: '', behavior_extension: '' })
    updateMock.mockRejectedValueOnce(new Error('boom'))

    const wrapper = await mountSuspended(JarvisSelfCard)
    await flush()

    await wrapper.find('textarea').setValue('hello')
    await wrapper.find('.jarvis-card__save').trigger('click')
    await flush()

    expect(wrapper.find('.jarvis-card__error').exists()).toBe(true)
  })

  it('shows empty defaults gracefully when API returns null fields', async () => {
    fetchMock.mockResolvedValueOnce({ system_prompt: null as unknown as string, behavior_extension: null as unknown as string })
    const wrapper = await mountSuspended(JarvisSelfCard)
    await flush()

    const ext = wrapper.find<HTMLTextAreaElement>('textarea')
    expect(ext.element.value).toBe('')
    const checkbox = wrapper.find<HTMLInputElement>('input[type="checkbox"]')
    expect(checkbox.element.checked).toBe(false)
  })
})
