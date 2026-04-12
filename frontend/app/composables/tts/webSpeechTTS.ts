import type { TTSProvider } from './types'

const MAX_CHUNK_LENGTH = 200

function splitIntoChunks(text: string): string[] {
  if (text.length <= MAX_CHUNK_LENGTH) return [text]

  const chunks: string[] = []
  let remaining = text

  while (remaining.length > MAX_CHUNK_LENGTH) {
    let splitAt = remaining.lastIndexOf('. ', MAX_CHUNK_LENGTH)
    if (splitAt === -1) splitAt = remaining.lastIndexOf(' ', MAX_CHUNK_LENGTH)
    if (splitAt === -1) splitAt = MAX_CHUNK_LENGTH

    chunks.push(remaining.slice(0, splitAt + 1).trim())
    remaining = remaining.slice(splitAt + 1).trim()
  }

  if (remaining) chunks.push(remaining)
  return chunks
}

export function createWebSpeechTTS(): TTSProvider {
  const synth = typeof window !== 'undefined' ? window.speechSynthesis : null
  const isSupported = !!synth

  let startCallback: (() => void) | null = null
  let endCallback: (() => void) | null = null
  let isSpeaking = false

  async function speak(text: string): Promise<void> {
    if (!synth || !isSupported) return

    // Chrome bug: cancel before speaking to avoid queue issues
    synth.cancel()

    const chunks = splitIntoChunks(text)
    isSpeaking = true
    if (startCallback) startCallback()

    for (let i = 0; i < chunks.length; i++) {
      await _speakChunk(chunks[i]!)
      if (!isSpeaking) break
    }

    isSpeaking = false
    if (endCallback) endCallback()
  }

  function _speakChunk(text: string): Promise<void> {
    return new Promise((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = navigator.language || 'en-US'
      utterance.onend = () => resolve()
      utterance.onerror = () => resolve()
      synth!.speak(utterance)
    })
  }

  function stop(): void {
    if (!synth) return
    isSpeaking = false
    synth.cancel()
    if (endCallback) endCallback()
  }

  function onStart(callback: () => void): void {
    startCallback = callback
  }

  function onEnd(callback: () => void): void {
    endCallback = callback
  }

  return { isSupported, speak, stop, onStart, onEnd }
}
