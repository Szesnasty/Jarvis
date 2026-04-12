export interface STTProvider {
  readonly isSupported: boolean
  start(): void
  stop(): void
  onResult: (callback: (transcript: string, isFinal: boolean) => void) => void
  onError: (callback: (error: string) => void) => void
  onEnd: (callback: () => void) => void
}
