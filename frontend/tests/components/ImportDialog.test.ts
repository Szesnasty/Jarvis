import { describe, it, expect } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import ImportDialog from '~/components/ImportDialog.vue'

describe('components/ImportDialog.vue', () => {
  it('renders when visible=true', async () => {
    const wrapper = await mountSuspended(ImportDialog, {
      props: { visible: true },
    })
    expect(wrapper.find('.import-dialog').exists()).toBe(true)
    expect(wrapper.find('.import-dialog__title').text()).toBe('Import File')
  })

  it('does not render when visible=false', async () => {
    const wrapper = await mountSuspended(ImportDialog, {
      props: { visible: false },
    })
    expect(wrapper.find('.import-dialog').exists()).toBe(false)
  })

  it('file input accepts .md, .txt, .pdf', async () => {
    const wrapper = await mountSuspended(ImportDialog, {
      props: { visible: true },
    })
    const input = wrapper.find('.import-dialog__file-input')
    expect(input.attributes('accept')).toBe('.md,.txt,.pdf')
  })

  it('dropzone is visible', async () => {
    const wrapper = await mountSuspended(ImportDialog, {
      props: { visible: true },
    })
    expect(wrapper.find('.import-dialog__dropzone').exists()).toBe(true)
  })

  it('import button disabled when no file selected', async () => {
    const wrapper = await mountSuspended(ImportDialog, {
      props: { visible: true },
    })
    const btn = wrapper.find('.import-dialog__import-btn')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('has folder selector with default options', async () => {
    const wrapper = await mountSuspended(ImportDialog, {
      props: { visible: true },
    })
    const select = wrapper.find('.import-dialog__select')
    expect(select.exists()).toBe(true)
    const options = select.findAll('option')
    const values = options.map(o => o.attributes('value'))
    expect(values).toContain('knowledge')
    expect(values).toContain('inbox')
  })

  it('cancel button emits close', async () => {
    const wrapper = await mountSuspended(ImportDialog, {
      props: { visible: true },
    })
    await wrapper.find('.import-dialog__cancel-btn').trigger('click')
    expect(wrapper.emitted('close')).toBeTruthy()
  })
})
