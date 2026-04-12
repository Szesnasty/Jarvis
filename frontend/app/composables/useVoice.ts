import type { OrbState } from '~/types'
import type { STTProvider } from '~/composables/stt/types'
import type { TTSProvider } from '~/composables/tts/types'

export function useVoice(stt: STTProvider, tts: TTSProvider) {
  const state = ref<OrbState>('idle')
  const transcript = ref('')
  const error = ref('')
  const autoSpeak = ref(true)

  const isVoiceAvailable = computed(() => stt.isSupported && tts.isSupported)

  let _sendMessage: ((content: string) => void) | null = null

  function bindChat(sendMessage: (content: string) => void): void {
    _sendMessage = sendMessage
  }

  stt.onResult((text, isFinal) => {
    transcript.value = text
    if (!isFinal) return

    state.value = 'thinking'
    if (_sendMessage) _sendMessage(text)
  })

  stt.onError((err) => {
    error.value = err
    state.value = 'idle'
    transcript.value = ''
  })

  stt.onEnd(() => {
    if (state.value === 'listening') {
      state.value = 'idle'
    }
  })

  tts.onEnd(() => {
    if (state.value === 'speaking') {
      state.value = 'idle'
    }
  })

  function startListening(): void {
    if (!stt.isSupported) return
    if (state.value === 'listening') return

    cancel()
    error.value = ''
    transcript.value = ''
    state.value = 'listening'
    stt.start()
  }

  function stopListening(): void {
    stt.stop()
    state.value = 'idle'
    transcript.value = ''
  }

  async function speakResponse(text: string): Promise<void> {
    if (!autoSpeak.value || !tts.isSupported) return

    state.value = 'speaking'
    await tts.speak(text)
  }

  function cancel(): void {
    stt.stop()
    tts.stop()
    state.value = 'idle'
    transcript.value = ''
  }

  return {
    state,
    transcript,
    error,
    autoSpeak,
    isVoiceAvailable,
    bindChat,
    startListening,
    stopListening,
    speakResponse,
    cancel,
  }
}
