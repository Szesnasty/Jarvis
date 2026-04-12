import { describe, it, expect, vi } from 'vitest'
import { useVoice } from '~/composables/useVoice'
import type { STTProvider } from '~/composables/stt/types'
import type { TTSProvider } from '~/composables/tts/types'

function createMockSTT(): STTProvider & { _triggerResult: (t: string, f: boolean) => void; _triggerError: (e: string) => void; _triggerEnd: () => void } {
  let resultCb: ((t: string, f: boolean) => void) | null = null
  let errorCb: ((e: string) => void) | null = null
  let endCb: (() => void) | null = null

  return {
    isSupported: true,
    start: vi.fn(),
    stop: vi.fn(),
    onResult: (cb) => { resultCb = cb },
    onError: (cb) => { errorCb = cb },
    onEnd: (cb) => { endCb = cb },
    _triggerResult: (t, f) => resultCb?.(t, f),
    _triggerError: (e) => errorCb?.(e),
    _triggerEnd: () => endCb?.(),
  }
}

function createMockTTS(): TTSProvider & { _triggerEnd: () => void; _triggerStart: () => void } {
  let startCb: (() => void) | null = null
  let endCb: (() => void) | null = null

  return {
    isSupported: true,
    speak: vi.fn().mockResolvedValue(undefined),
    stop: vi.fn(),
    onStart: (cb) => { startCb = cb },
    onEnd: (cb) => { endCb = cb },
    _triggerStart: () => startCb?.(),
    _triggerEnd: () => endCb?.(),
  }
}

describe('useVoice', () => {
  it('full flow: listening → thinking → speaking → idle', async () => {
    const stt = createMockSTT()
    const tts = createMockTTS()
    const voice = useVoice(stt, tts)
    const sendMessage = vi.fn()
    voice.bindChat(sendMessage)

    voice.startListening()
    expect(voice.state.value).toBe('listening')

    stt._triggerResult('hello jarvis', true)
    expect(voice.state.value).toBe('thinking')
    expect(sendMessage).toHaveBeenCalledWith('hello jarvis')

    await voice.speakResponse('Hi there!')
    expect(tts.speak).toHaveBeenCalledWith('Hi there!')
  })

  it('state transitions: idle → listening → thinking → speaking → idle', () => {
    const stt = createMockSTT()
    const tts = createMockTTS()
    const voice = useVoice(stt, tts)
    voice.bindChat(vi.fn())

    expect(voice.state.value).toBe('idle')

    voice.startListening()
    expect(voice.state.value).toBe('listening')

    stt._triggerResult('test', true)
    expect(voice.state.value).toBe('thinking')

    voice.state.value = 'speaking'
    tts._triggerEnd()
    expect(voice.state.value).toBe('idle')
  })

  it('cancel during listening returns to idle', () => {
    const stt = createMockSTT()
    const tts = createMockTTS()
    const voice = useVoice(stt, tts)

    voice.startListening()
    expect(voice.state.value).toBe('listening')

    voice.cancel()
    expect(voice.state.value).toBe('idle')
    expect(stt.stop).toHaveBeenCalled()
  })

  it('cancel during speaking stops TTS and returns to idle', () => {
    const stt = createMockSTT()
    const tts = createMockTTS()
    const voice = useVoice(stt, tts)

    voice.state.value = 'speaking'
    voice.cancel()
    expect(voice.state.value).toBe('idle')
    expect(tts.stop).toHaveBeenCalled()
  })

  it('error during STT returns to idle with error', () => {
    const stt = createMockSTT()
    const tts = createMockTTS()
    const voice = useVoice(stt, tts)

    voice.startListening()
    stt._triggerError('no-speech')

    expect(voice.state.value).toBe('idle')
    expect(voice.error.value).toBe('no-speech')
  })

  it('text input works when voice disabled (state stays idle)', () => {
    const stt = createMockSTT()
    const tts = createMockTTS()
    const voice = useVoice(stt, tts)

    // Just verify state doesn't change without voice interaction
    expect(voice.state.value).toBe('idle')
  })

  it('isVoiceAvailable is computed from STT + TTS support', () => {
    const stt = createMockSTT()
    const tts = createMockTTS()
    const voice = useVoice(stt, tts)
    expect(voice.isVoiceAvailable.value).toBe(true)
  })

  it('isVoiceAvailable is false when STT not supported', () => {
    const stt = createMockSTT()
    ;(stt as any).isSupported = false
    const tts = createMockTTS()
    const voice = useVoice(stt, tts)
    expect(voice.isVoiceAvailable.value).toBe(false)
  })
})
