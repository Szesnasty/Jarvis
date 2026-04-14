import { describe, it, expect, vi } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import ModelSelector from '~/components/ModelSelector.vue'
import { MODEL_CATALOG } from '~/composables/useApiKeys'

const ANTHROPIC_PROVIDER = {
  id: 'anthropic',
  name: 'Anthropic',
  icon: '<svg></svg>',
  keyPrefix: 'sk-ant-',
  docsUrl: '',
  models: MODEL_CATALOG.anthropic.map(m => m.id),
  color: '#D97706',
}

const OPENAI_PROVIDER = {
  id: 'openai',
  name: 'OpenAI',
  icon: '<svg></svg>',
  keyPrefix: 'sk-',
  docsUrl: '',
  models: MODEL_CATALOG.openai.map(m => m.id),
  color: '#10A37F',
}

const mockActiveProvider = ref('anthropic')
const mockActiveModel = ref('claude-sonnet-4-20250514')
const mockSelectModel = vi.fn((providerId: string, modelId: string) => {
  mockActiveProvider.value = providerId
  mockActiveModel.value = modelId
})
let mockConfigured: typeof ANTHROPIC_PROVIDER[] = []

vi.mock('~/composables/useApiKeys', async (importOriginal) => {
  const orig = await importOriginal<typeof import('~/composables/useApiKeys')>()
  return {
    ...orig,
    useApiKeys: () => ({
      activeProvider: mockActiveProvider,
      activeModel: mockActiveModel,
      selectModel: mockSelectModel,
      configuredProviders: () => mockConfigured,
      providers: [ANTHROPIC_PROVIDER, OPENAI_PROVIDER],
    }),
  }
})

describe('ModelSelector', () => {
  it('renders trigger button with model label', async () => {
    mockConfigured = [ANTHROPIC_PROVIDER]
    mockActiveProvider.value = 'anthropic'
    mockActiveModel.value = 'claude-sonnet-4-20250514'

    const wrapper = await mountSuspended(ModelSelector)
    expect(wrapper.find('.model-selector__trigger').exists()).toBe(true)
    expect(wrapper.find('.model-selector__trigger-label').text()).toBe('Claude Sonnet 4')
  })

  it('dropdown is closed by default', async () => {
    const wrapper = await mountSuspended(ModelSelector)
    expect(wrapper.find('.model-selector__dropdown').exists()).toBe(false)
  })

  it('opens dropdown on trigger click', async () => {
    mockConfigured = [ANTHROPIC_PROVIDER]
    const wrapper = await mountSuspended(ModelSelector)
    await wrapper.find('.model-selector__trigger').trigger('click')
    expect(wrapper.find('.model-selector__dropdown').exists()).toBe(true)
  })

  it('shows only providers with configured keys', async () => {
    mockConfigured = [ANTHROPIC_PROVIDER]
    const wrapper = await mountSuspended(ModelSelector)
    await wrapper.find('.model-selector__trigger').trigger('click')

    const headers = wrapper.findAll('.model-selector__group-header')
    expect(headers).toHaveLength(1)
    expect(headers[0].text()).toContain('Anthropic')
  })

  it('shows multiple configured providers', async () => {
    mockConfigured = [ANTHROPIC_PROVIDER, OPENAI_PROVIDER]
    const wrapper = await mountSuspended(ModelSelector)
    await wrapper.find('.model-selector__trigger').trigger('click')

    const headers = wrapper.findAll('.model-selector__group-header')
    expect(headers).toHaveLength(2)
  })

  it('shows empty state when no keys configured', async () => {
    mockConfigured = []
    const wrapper = await mountSuspended(ModelSelector)
    await wrapper.find('.model-selector__trigger').trigger('click')
    expect(wrapper.find('.model-selector__empty').exists()).toBe(true)
  })

  it('renders 3 Anthropic model options', async () => {
    mockConfigured = [ANTHROPIC_PROVIDER]
    const wrapper = await mountSuspended(ModelSelector)
    await wrapper.find('.model-selector__trigger').trigger('click')

    const options = wrapper.findAll('.model-selector__option')
    expect(options).toHaveLength(3)
  })

  it('shows cost badges ($, $$, $$$) for Anthropic', async () => {
    mockConfigured = [ANTHROPIC_PROVIDER]
    const wrapper = await mountSuspended(ModelSelector)
    await wrapper.find('.model-selector__trigger').trigger('click')

    const costs = wrapper.findAll('.model-selector__cost')
    expect(costs).toHaveLength(3)
    const texts = costs.map(c => c.text())
    expect(texts).toContain('$')
    expect(texts).toContain('$$')
    expect(texts).toContain('$$$')
  })

  it('highlights active model', async () => {
    mockConfigured = [ANTHROPIC_PROVIDER]
    mockActiveProvider.value = 'anthropic'
    mockActiveModel.value = 'claude-sonnet-4-20250514'

    const wrapper = await mountSuspended(ModelSelector)
    await wrapper.find('.model-selector__trigger').trigger('click')

    const active = wrapper.find('.model-selector__option--active')
    expect(active.exists()).toBe(true)
    expect(active.text()).toContain('Claude Sonnet 4')
  })

  it('calls selectModel on option click and closes dropdown', async () => {
    mockConfigured = [ANTHROPIC_PROVIDER]
    mockSelectModel.mockClear()

    const wrapper = await mountSuspended(ModelSelector)
    await wrapper.find('.model-selector__trigger').trigger('click')

    const options = wrapper.findAll('.model-selector__option')
    await options[1].trigger('click') // Haiku
    expect(mockSelectModel).toHaveBeenCalledWith('anthropic', 'claude-haiku-4-20250514')
    // Dropdown should close
    expect(wrapper.find('.model-selector__dropdown').exists()).toBe(false)
  })
})
