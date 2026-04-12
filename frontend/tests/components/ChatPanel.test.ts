import { describe, it, expect, vi } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import ChatPanel from '~/components/ChatPanel.vue'

vi.mock('~/composables/useApi', () => ({
  useApi: () => ({
    ingestUrl: vi.fn().mockResolvedValue({
      path: 'knowledge/article.md',
      title: 'Example',
      type: 'article',
      source: 'https://example.com',
      word_count: 42,
    }),
  }),
}))

const baseProps = {
  messages: [],
  currentResponse: '',
  isLoading: false,
  toolActivity: '',
}

describe('ChatPanel', () => {
  it('renders message list from chat state', async () => {
    const wrapper = await mountSuspended(ChatPanel, {
      props: {
        ...baseProps,
        messages: [
          { role: 'user' as const, content: 'Hello' },
          { role: 'assistant' as const, content: 'Hi there' },
        ],
      },
    })
    const msgs = wrapper.findAll('.chat-panel__message')
    expect(msgs).toHaveLength(2)
  })

  it('user messages have user class', async () => {
    const wrapper = await mountSuspended(ChatPanel, {
      props: {
        ...baseProps,
        messages: [{ role: 'user' as const, content: 'Hello' }],
      },
    })
    expect(wrapper.find('.chat-panel__message.user').exists()).toBe(true)
  })

  it('assistant messages have assistant class', async () => {
    const wrapper = await mountSuspended(ChatPanel, {
      props: {
        ...baseProps,
        messages: [{ role: 'assistant' as const, content: 'Hi' }],
      },
    })
    expect(wrapper.find('.chat-panel__message.assistant').exists()).toBe(true)
  })

  it('streaming response shows cursor', async () => {
    const wrapper = await mountSuspended(ChatPanel, {
      props: {
        ...baseProps,
        currentResponse: 'Typing...',
      },
    })
    expect(wrapper.find('.chat-panel__cursor').exists()).toBe(true)
  })

  it('tool activity shows indicator text', async () => {
    const wrapper = await mountSuspended(ChatPanel, {
      props: {
        ...baseProps,
        toolActivity: 'Searching notes...',
      },
    })
    expect(wrapper.find('.chat-panel__activity').text()).toBe('Searching notes...')
  })

  it('has textarea input and send button', async () => {
    const wrapper = await mountSuspended(ChatPanel, { props: baseProps })
    expect(wrapper.find('.chat-panel__input').exists()).toBe(true)
    expect(wrapper.find('.chat-panel__icon-btn--send').exists()).toBe(true)
  })

  it('send button disabled while loading', async () => {
    const wrapper = await mountSuspended(ChatPanel, {
      props: { ...baseProps, isLoading: true },
    })
    const btn = wrapper.find('.chat-panel__icon-btn--send')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('shows URL action bar when input contains URL', async () => {
    const wrapper = await mountSuspended(ChatPanel, { props: baseProps })
    await wrapper.find('textarea.chat-panel__input').setValue('check this https://example.com')
    expect(wrapper.find('.chat-panel__url-bar').exists()).toBe(true)
    expect(wrapper.find('.chat-panel__url-action').text()).toContain('Save to memory')
  })

  it('does not show URL action bar for regular text', async () => {
    const wrapper = await mountSuspended(ChatPanel, { props: baseProps })
    await wrapper.find('textarea.chat-panel__input').setValue('hello world only')
    expect(wrapper.find('.chat-panel__url-bar').exists()).toBe(false)
  })
})
