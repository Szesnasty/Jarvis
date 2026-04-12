import { describe, it, expect } from 'vitest'
import { mountSuspended } from '@nuxt/test-utils/runtime'
import ChatPanel from '~/components/ChatPanel.vue'

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

  it('has text input and send button', async () => {
    const wrapper = await mountSuspended(ChatPanel, { props: baseProps })
    expect(wrapper.find('.chat-panel__input').exists()).toBe(true)
    expect(wrapper.find('.chat-panel__send').exists()).toBe(true)
  })

  it('send button disabled while loading', async () => {
    const wrapper = await mountSuspended(ChatPanel, {
      props: { ...baseProps, isLoading: true },
    })
    const btn = wrapper.find('.chat-panel__send')
    expect(btn.attributes('disabled')).toBeDefined()
  })
})
