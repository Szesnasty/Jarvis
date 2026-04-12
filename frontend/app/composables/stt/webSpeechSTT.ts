import type { STTProvider } from './types'

export function createWebSpeechSTT(): STTProvider {
  const SpeechRecognition =
    typeof window !== 'undefined'
      ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
      : null

  const isSupported = !!SpeechRecognition
  let recognition: any = null
  let isListening = false

  let resultCallback: ((transcript: string, isFinal: boolean) => void) | null = null
  let errorCallback: ((error: string) => void) | null = null
  let endCallback: (() => void) | null = null

  function _create(): any {
    const rec = new SpeechRecognition()
    rec.continuous = false
    rec.interimResults = true
    rec.lang = navigator.language || 'en-US'

    rec.onresult = (event: any) => {
      if (!resultCallback) return
      const last = event.results[event.results.length - 1]
      const transcript = last[0].transcript
      resultCallback(transcript, last.isFinal)
    }

    rec.onerror = (event: any) => {
      isListening = false
      if (errorCallback) errorCallback(event.error)
    }

    rec.onend = () => {
      isListening = false
      if (endCallback) endCallback()
    }

    return rec
  }

  function start(): void {
    if (!isSupported || isListening) return
    recognition = _create()
    isListening = true
    recognition.start()
  }

  function stop(): void {
    if (!recognition || !isListening) return
    recognition.stop()
    isListening = false
  }

  function onResult(callback: (transcript: string, isFinal: boolean) => void): void {
    resultCallback = callback
  }

  function onError(callback: (error: string) => void): void {
    errorCallback = callback
  }

  function onEnd(callback: () => void): void {
    endCallback = callback
  }

  return { isSupported, start, stop, onResult, onError, onEnd }
}
