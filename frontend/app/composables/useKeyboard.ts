import { onMounted, onUnmounted } from 'vue'

export interface KeyboardOptions {
  onToggleVoice?: () => void
  onCancel?: () => void
  onSend?: () => void
  enabled?: () => boolean
}

export function useKeyboard(options: KeyboardOptions) {
  function handler(event: KeyboardEvent) {
    if (options.enabled && !options.enabled()) return

    const target = event.target as HTMLElement | null
    const isInput = target && (
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.isContentEditable
    )

    if (event.key === ' ' && !isInput && options.onToggleVoice) {
      event.preventDefault()
      options.onToggleVoice()
    }

    if (event.key === 'Escape' && options.onCancel) {
      options.onCancel()
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', handler)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handler)
  })

  return { handler }
}
