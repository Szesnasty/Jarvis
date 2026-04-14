---
title: Voice System
status: active
type: feature
sources:
  - frontend/app/composables/useVoice.ts
  - frontend/app/composables/stt/types.ts
  - frontend/app/composables/stt/webSpeechSTT.ts
  - frontend/app/composables/tts/types.ts
  - frontend/app/composables/tts/webSpeechTTS.ts
  - frontend/app/components/VoiceButton.vue
  - frontend/app/components/TranscriptBar.vue
depends_on: [chat]
last_reviewed: 2026-04-14
---

## Summary

The voice system provides speech-to-text input and text-to-speech output using browser-native Web Speech APIs, requiring no extra API keys or backend involvement. It is designed around provider interfaces so either layer can be swapped for an alternative implementation (e.g., Whisper, Kokoro.js) without touching the orchestration logic.

## How It Works

The `useVoice` composable is the central coordinator. It receives concrete STT and TTS provider instances at construction time and registers event callbacks on both. This wiring happens once at setup — the composable does not create providers itself, so the caller controls which implementation is injected.

State flows through four values defined by the `OrbState` type: `idle`, `listening`, `thinking`, and `speaking`. Transitions between these states are driven entirely by provider events and explicit calls, not by timers or polling:

1. `startListening()` moves state to `listening` and delegates to `stt.start()`.
2. As speech is recognised, interim results surface through `onResult` with `isFinal: false` — these update the displayed transcript without triggering a send.
3. When the browser finalises a result (`isFinal: true`), state shifts to `thinking` and the transcript is forwarded to the chat layer via a callback registered with `bindChat()`.
4. The chat layer is expected to call `speakResponse(text)` once it has a reply. This shifts state to `speaking` and delegates to `tts.speak(text)`.
5. When TTS finishes, the `onEnd` callback returns state to `idle`.

`cancel()` is a hard reset: it stops both providers simultaneously and clears transcript and state, used defensively before any new `startListening()` call to avoid overlapping sessions.

### STT implementation (Web Speech API)

`createWebSpeechSTT` creates a fresh `SpeechRecognition` instance on every `start()` call rather than reusing one. This avoids a class of browser bugs where a stopped recognition object cannot be cleanly restarted. The instance is configured with `continuous: false` (single utterance) and `interimResults: true` (live transcript updates). Language is taken from `navigator.language` with an `en-US` fallback.

### TTS implementation (Web Speech API)

`createWebSpeechTTS` addresses a well-known Chrome bug where queued utterances silently fail: it calls `synth.cancel()` unconditionally before every `speak()` call. For long responses, text is split into chunks of at most 200 characters, breaking on sentence boundaries (`. `) first, then word boundaries, then hard-cutting if neither is found. Chunks are spoken sequentially using promise chaining, and the loop exits early if `stop()` is called mid-speech. Utterance errors are treated as resolved (not rejected) so a single failed chunk does not abort the whole sequence.

### UI Components

`VoiceButton` is a stateless display component. It receives the current `OrbState` and a `supported` flag, emits a single `toggle` event on click, and is disabled when voice is unavailable. Visual state is communicated through CSS class names matching the state values — the `listening` class triggers a pulsing ring animation.

`TranscriptBar` renders the live interim transcript with a fade transition. It only appears when both `visible` and a non-empty `transcript` are truthy, so callers can suppress it during states where showing partial text would be confusing.

## Key Files

| File | Role |
|---|---|
| `frontend/app/composables/useVoice.ts` | Orchestrates STT and TTS providers, owns state machine, bridges to chat via `bindChat` |
| `frontend/app/composables/stt/types.ts` | `STTProvider` interface contract |
| `frontend/app/composables/stt/webSpeechSTT.ts` | Browser Web Speech API implementation of `STTProvider` |
| `frontend/app/composables/tts/types.ts` | `TTSProvider` interface contract |
| `frontend/app/composables/tts/webSpeechTTS.ts` | Browser SpeechSynthesis implementation of `TTSProvider` with chunking logic |
| `frontend/app/components/VoiceButton.vue` | Toggle button that reflects voice state visually, emits `toggle` |
| `frontend/app/components/TranscriptBar.vue` | Fading display of live interim transcript text |

## API / Interface

### STTProvider

```typescript
export interface STTProvider {
  readonly isSupported: boolean
  start(): void
  stop(): void
  onResult: (callback: (transcript: string, isFinal: boolean) => void) => void
  onError: (callback: (error: string) => void) => void
  onEnd: (callback: () => void) => void
}
```

`onResult` is called for every recognition event. When `isFinal` is `false`, the transcript is a live partial result. When `true`, it is the committed utterance. Callers must check `isFinal` before acting on the text.

`onEnd` fires when the recognition session closes — either naturally after a final result or after an explicit `stop()`. It is not guaranteed to fire after `onError`.

### TTSProvider

```typescript
export interface TTSProvider {
  readonly isSupported: boolean
  speak(text: string): Promise<void>
  stop(): void
  onStart: (callback: () => void) => void
  onEnd: (callback: () => void) => void
}
```

`speak` returns a Promise that resolves only after all chunks finish (or after `stop()` is called). Calling `stop()` from within an `onEnd` handler is safe — the internal `isSpeaking` flag guards against re-entrant cleanup.

### useVoice return value

```typescript
{
  state: Ref<OrbState>           // 'idle' | 'listening' | 'thinking' | 'speaking'
  transcript: Ref<string>        // live partial or committed transcript text
  error: Ref<string>             // last STT error string, cleared on startListening
  autoSpeak: Ref<boolean>        // when false, speakResponse() is a no-op
  isVoiceAvailable: ComputedRef<boolean>  // true only if both providers are supported
  bindChat(fn: (content: string) => void): void
  startListening(): void
  stopListening(): void
  speakResponse(text: string): Promise<void>
  cancel(): void
}
```

`bindChat` must be called before any voice interaction. If it is not called, transcribed speech is silently dropped — there is no error or warning.

## Gotchas

**`bindChat` is not guarded.** If `startListening()` is called before `bindChat()` registers a send function, the final transcript is discarded with no feedback. The caller is responsible for the setup order.

**`autoSpeak` bypasses TTS entirely.** Setting `autoSpeak.value = false` means `speakResponse()` returns immediately without speaking. This is intentional for text-only mode but can be confusing when debugging — a call to `speakResponse` that does nothing is not an error.

**`stopListening()` clears the transcript.** Unlike `cancel()`, `stopListening()` also zeroes `transcript.value`. If the caller wants to preserve whatever was captured before stopping, it must read `transcript.value` first.

**Chrome TTS queue bug.** The `synth.cancel()` call at the start of every `speak()` is not optional — without it, Chrome can silently queue utterances and play them out of order or not at all. Any future TTS implementation targeting Chrome must handle this.

**`onEnd` fires on `stop()` too.** When `stop()` is called on the TTS provider, it explicitly invokes the `endCallback`. This means `useVoice`'s `tts.onEnd` handler will fire and return state to `idle` even when a stop was requested by `cancel()`. The guard `if (state.value === 'speaking')` in `tts.onEnd` prevents spurious state resets from `cancel()` scenarios where state has already been set to `idle`.

**Single-utterance STT.** The Web Speech STT implementation uses `continuous: false`. It captures one utterance and then the session ends naturally. There is no long-running session; each `startListening()` is a discrete capture.

## Known Issues

**Medium — STT callbacks registered before `bindChat` is called (`useVoice.ts:19-25`).**
The `stt.onResult` callback is wired at composable construction time. The `_sendMessage` reference it closes over is `null` until `bindChat()` is called by the caller. If the STT provider fires a final result before `bindChat` has been invoked — for example, if `startListening()` is called immediately after composable construction in the same tick — the transcript is silently dropped. There is no warning, no queuing, and no error. The existing Gotchas section documents the consequence; this entry records it as a concrete code-level risk tied to the initialization order.
