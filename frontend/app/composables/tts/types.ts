export interface TTSProvider {
  readonly isSupported: boolean
  speak(text: string): Promise<void>
  stop(): void
  onStart: (callback: () => void) => void
  onEnd: (callback: () => void) => void
}
