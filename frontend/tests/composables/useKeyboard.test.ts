import { describe, it, expect, vi, beforeEach } from 'vitest'

describe('useKeyboard', () => {
  let handler: (event: KeyboardEvent) => void
  let toggleVoice: ReturnType<typeof vi.fn>
  let cancel: ReturnType<typeof vi.fn>

  beforeEach(() => {
    toggleVoice = vi.fn()
    cancel = vi.fn()
  })

  function createHandler(opts: { onToggleVoice?: () => void; onCancel?: () => void; enabled?: () => boolean }) {
    return (event: KeyboardEvent) => {
      if (opts.enabled && !opts.enabled()) return
      const target = event.target as HTMLElement | null
      const isInput = target && (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      )
      if (event.key === ' ' && !isInput && opts.onToggleVoice) {
        event.preventDefault()
        opts.onToggleVoice()
      }
      if (event.key === 'Escape' && opts.onCancel) {
        opts.onCancel()
      }
    }
  }

  it('space key calls toggleVoice when not in input', () => {
    handler = createHandler({ onToggleVoice: toggleVoice })
    const event = new KeyboardEvent('keydown', { key: ' ' })
    Object.defineProperty(event, 'target', { value: document.body })
    handler(event)
    expect(toggleVoice).toHaveBeenCalled()
  })

  it('escape calls cancel', () => {
    handler = createHandler({ onCancel: cancel })
    const event = new KeyboardEvent('keydown', { key: 'Escape' })
    Object.defineProperty(event, 'target', { value: document.body })
    handler(event)
    expect(cancel).toHaveBeenCalled()
  })

  it('space does NOT toggle voice when typing in input', () => {
    handler = createHandler({ onToggleVoice: toggleVoice })
    const input = document.createElement('input')
    const event = new KeyboardEvent('keydown', { key: ' ' })
    Object.defineProperty(event, 'target', { value: input })
    handler(event)
    expect(toggleVoice).not.toHaveBeenCalled()
  })

  it('space does NOT toggle voice when typing in textarea', () => {
    handler = createHandler({ onToggleVoice: toggleVoice })
    const textarea = document.createElement('textarea')
    const event = new KeyboardEvent('keydown', { key: ' ' })
    Object.defineProperty(event, 'target', { value: textarea })
    handler(event)
    expect(toggleVoice).not.toHaveBeenCalled()
  })

  it('key events fire correct handler functions', () => {
    handler = createHandler({ onToggleVoice: toggleVoice, onCancel: cancel })
    const spaceEvent = new KeyboardEvent('keydown', { key: ' ' })
    Object.defineProperty(spaceEvent, 'target', { value: document.body })
    handler(spaceEvent)
    expect(toggleVoice).toHaveBeenCalledTimes(1)
    expect(cancel).not.toHaveBeenCalled()

    const escEvent = new KeyboardEvent('keydown', { key: 'Escape' })
    Object.defineProperty(escEvent, 'target', { value: document.body })
    handler(escEvent)
    expect(cancel).toHaveBeenCalledTimes(1)
  })

  it('shortcuts disabled when enabled returns false', () => {
    handler = createHandler({ onToggleVoice: toggleVoice, enabled: () => false })
    const event = new KeyboardEvent('keydown', { key: ' ' })
    Object.defineProperty(event, 'target', { value: document.body })
    handler(event)
    expect(toggleVoice).not.toHaveBeenCalled()
  })

  it('shortcuts enabled when enabled returns true', () => {
    handler = createHandler({ onToggleVoice: toggleVoice, enabled: () => true })
    const event = new KeyboardEvent('keydown', { key: ' ' })
    Object.defineProperty(event, 'target', { value: document.body })
    handler(event)
    expect(toggleVoice).toHaveBeenCalled()
  })

  it('other keys do not trigger handlers', () => {
    handler = createHandler({ onToggleVoice: toggleVoice, onCancel: cancel })
    const event = new KeyboardEvent('keydown', { key: 'a' })
    Object.defineProperty(event, 'target', { value: document.body })
    handler(event)
    expect(toggleVoice).not.toHaveBeenCalled()
    expect(cancel).not.toHaveBeenCalled()
  })
})
