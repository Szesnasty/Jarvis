import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createWebSpeechSTT } from '~/composables/stt/webSpeechSTT'

let mockRecognition: any

function createMockSpeechRecognition() {
  // Must be a real function (not arrow) so `new` works
  return function SpeechRecognition(this: any) {
    mockRecognition = this
    this.continuous = false
    this.interimResults = false
    this.lang = ''
    this.start = vi.fn()
    this.stop = vi.fn()
    this.abort = vi.fn()
    this.onresult = null
    this.onerror = null
    this.onend = null
  }
}

describe('webSpeechSTT', () => {
  beforeEach(() => {
    mockRecognition = null
    ;(window as any).SpeechRecognition = undefined
    ;(window as any).webkitSpeechRecognition = undefined
  })

  it('start() calls SpeechRecognition.start()', () => {
    ;(window as any).SpeechRecognition = createMockSpeechRecognition()
    const stt = createWebSpeechSTT()
    stt.start()
    expect(mockRecognition.start).toHaveBeenCalled()
  })

  it('stop() calls SpeechRecognition.stop()', () => {
    ;(window as any).SpeechRecognition = createMockSpeechRecognition()
    const stt = createWebSpeechSTT()
    stt.start()
    stt.stop()
    expect(mockRecognition.stop).toHaveBeenCalled()
  })

  it('onresult updates transcript in real-time', () => {
    ;(window as any).SpeechRecognition = createMockSpeechRecognition()
    const stt = createWebSpeechSTT()
    const results: string[] = []

    stt.onResult((text) => results.push(text))
    stt.start()

    mockRecognition.onresult({
      results: [{ 0: { transcript: 'hello' }, isFinal: false, length: 1 }],
    })

    expect(results).toContain('hello')
  })

  it('onresult with isFinal emits final transcript', () => {
    ;(window as any).SpeechRecognition = createMockSpeechRecognition()
    const stt = createWebSpeechSTT()
    const finals: boolean[] = []

    stt.onResult((_text, isFinal) => finals.push(isFinal))
    stt.start()

    mockRecognition.onresult({
      results: [{ 0: { transcript: 'hello world' }, isFinal: true, length: 1 }],
    })

    expect(finals).toContain(true)
  })

  it('onend callback is called', () => {
    ;(window as any).SpeechRecognition = createMockSpeechRecognition()
    const stt = createWebSpeechSTT()
    const endCb = vi.fn()

    stt.onEnd(endCb)
    stt.start()
    mockRecognition.onend()

    expect(endCb).toHaveBeenCalled()
  })

  it('onerror sets error', () => {
    ;(window as any).SpeechRecognition = createMockSpeechRecognition()
    const stt = createWebSpeechSTT()
    const errors: string[] = []

    stt.onError((err) => errors.push(err))
    stt.start()
    mockRecognition.onerror({ error: 'no-speech' })

    expect(errors).toContain('no-speech')
  })

  it('isSupported is false when no SpeechRecognition API', () => {
    const stt = createWebSpeechSTT()
    expect(stt.isSupported).toBe(false)
  })

  it('start() is no-op when not supported', () => {
    const stt = createWebSpeechSTT()
    // Should not throw
    stt.start()
    expect(stt.isSupported).toBe(false)
  })

  it('start() while already listening is no-op', () => {
    ;(window as any).SpeechRecognition = createMockSpeechRecognition()
    const stt = createWebSpeechSTT()
    stt.start()
    const firstRec = mockRecognition
    stt.start()
    // start only called once on the first recognition instance
    expect(firstRec.start).toHaveBeenCalledTimes(1)
  })

  it('works with webkitSpeechRecognition fallback', () => {
    ;(window as any).webkitSpeechRecognition = createMockSpeechRecognition()
    const stt = createWebSpeechSTT()
    expect(stt.isSupported).toBe(true)
  })
})
