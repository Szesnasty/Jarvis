import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createWebSpeechTTS } from '~/composables/tts/webSpeechTTS'

let mockSynth: any

function setupMockSynthesis() {
  mockSynth = {
    speak: vi.fn((utterance: any) => {
      // Auto-resolve onend
      setTimeout(() => utterance.onend?.(), 0)
    }),
    cancel: vi.fn(),
  }
  Object.defineProperty(window, 'speechSynthesis', {
    value: mockSynth,
    writable: true,
    configurable: true,
  })

  // Mock SpeechSynthesisUtterance as a constructor
  ;(globalThis as any).SpeechSynthesisUtterance = function (this: any, text: string) {
    this.text = text
    this.lang = ''
    this.onend = null
    this.onerror = null
  }
}

describe('webSpeechTTS', () => {
  beforeEach(() => {
    setupMockSynthesis()
  })

  it('speak(text) calls speechSynthesis.speak()', async () => {
    const tts = createWebSpeechTTS()
    await tts.speak('Hello')
    expect(mockSynth.speak).toHaveBeenCalled()
  })

  it('speak(text) triggers onStart callback', async () => {
    const tts = createWebSpeechTTS()
    const startCb = vi.fn()
    tts.onStart(startCb)
    await tts.speak('Hello')
    expect(startCb).toHaveBeenCalled()
  })

  it('speak completion triggers onEnd callback', async () => {
    const tts = createWebSpeechTTS()
    const endCb = vi.fn()
    tts.onEnd(endCb)
    await tts.speak('Hello')
    expect(endCb).toHaveBeenCalled()
  })

  it('stop() calls speechSynthesis.cancel()', () => {
    const tts = createWebSpeechTTS()
    tts.stop()
    expect(mockSynth.cancel).toHaveBeenCalled()
  })

  it('stop() triggers onEnd callback', () => {
    const tts = createWebSpeechTTS()
    const endCb = vi.fn()
    tts.onEnd(endCb)
    tts.stop()
    expect(endCb).toHaveBeenCalled()
  })

  it('isSupported is true when speechSynthesis exists', () => {
    const tts = createWebSpeechTTS()
    expect(tts.isSupported).toBe(true)
  })

  it('isSupported is false when speechSynthesis missing', () => {
    Object.defineProperty(window, 'speechSynthesis', {
      value: undefined,
      writable: true,
      configurable: true,
    })
    const tts = createWebSpeechTTS()
    expect(tts.isSupported).toBe(false)
  })

  it('speak() cancels before speaking (Chrome bug workaround)', async () => {
    const tts = createWebSpeechTTS()
    await tts.speak('Hello')
    // cancel called before speak
    expect(mockSynth.cancel).toHaveBeenCalled()
    expect(mockSynth.speak).toHaveBeenCalled()
  })
})
