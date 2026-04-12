# Step 06 — Voice Input/Output + States

> **Guidelines**: [CODING-GUIDELINES.md](../CODING-GUIDELINES.md)
> **Plan**: [JARVIS-PLAN.md](../JARVIS-PLAN.md)
> **Previous**: [Step 05 — Claude Integration](step-05-claude-integration.md) | **Next**: [Step 07 — Planning & Ops](step-07-planning-ops.md) | **Index**: [index-spec.md](../index-spec.md)

---

## Goal

User can talk to Jarvis using their microphone and hear responses spoken back. The Orb reflects current state (idle / listening / thinking / speaking).

---

## Files to Create / Modify

### Frontend
```
frontend/src/
├── composables/
│   ├── useVoice.ts            # NEW — orchestrates STT + TTS + state
│   ├── stt/
│   │   ├── types.ts           # NEW — STTProvider interface
│   │   └── webSpeechSTT.ts    # NEW — Web Speech API implementation
│   └── tts/
│       ├── types.ts           # NEW — TTSProvider interface
│       └── webSpeechTTS.ts    # NEW — SpeechSynthesis implementation
├── components/
│   ├── VoiceButton.vue        # NEW — mic button (push-to-talk / toggle)
│   └── TranscriptBar.vue      # NEW — shows live transcript
│   └── Orb.vue                # MODIFY — animate based on voice state
├── stores/
│   └── voice.ts               # NEW — voice state store
└── views/
    └── MainView.vue           # MODIFY — add VoiceButton + TranscriptBar
```

---

## Specification

### Provider Interfaces

**These interfaces are critical.** All voice functionality goes through them so providers can be swapped later.

```typescript
// composables/stt/types.ts
export interface STTProvider {
  readonly isSupported: boolean
  start(): void
  stop(): void
  onResult: (callback: (transcript: string, isFinal: boolean) => void) => void
  onError: (callback: (error: string) => void) => void
  onEnd: (callback: () => void) => void
}

// composables/tts/types.ts
export interface TTSProvider {
  readonly isSupported: boolean
  speak(text: string): Promise<void>
  stop(): void
  onStart: (callback: () => void) => void
  onEnd: (callback: () => void) => void
}
```

### Web Speech STT (`webSpeechSTT.ts`)

- Uses `window.SpeechRecognition` (or `webkitSpeechRecognition`)
- Settings: `continuous = false`, `interimResults = true`, `lang = navigator.language`
- Returns interim results for live transcript, final result on end
- Handles: `no-speech`, `audio-capture`, `not-allowed` errors gracefully

### Web Speech TTS (`webSpeechTTS.ts`)

- Uses `window.speechSynthesis`
- Selects best available voice for the detected language
- Configurable: `rate`, `pitch`, `volume`
- Handles the Chrome bug: cancel() before speak() to avoid queue issues
- Splits long text into chunks < 200 chars at sentence boundaries (some browsers cut off long utterances)

### Voice Composable (`useVoice.ts`)

Orchestrates the full voice loop:

```typescript
export function useVoice(stt: STTProvider, tts: TTSProvider) {
  const state = ref<'idle' | 'listening' | 'thinking' | 'speaking'>('idle')
  const transcript = ref('')
  const lastResponse = ref('')

  function startListening() { ... }
  function stopListening() { ... }
  async function speakResponse(text: string) { ... }
  function cancel() { ... }

  return { state, transcript, lastResponse, startListening, stopListening, speakResponse, cancel }
}
```

**State machine:**
```
idle → [user clicks mic] → listening
listening → [speech recognized] → thinking (send to chat)
thinking → [response received] → speaking
speaking → [TTS done] → idle
```

Any state → [user clicks cancel / mic] → idle

### Voice Store (`stores/voice.ts`)

```typescript
export const useVoiceStore = defineStore('voice', () => {
  const state = ref<'idle' | 'listening' | 'thinking' | 'speaking'>('idle')
  const isVoiceEnabled = ref(true)
  const transcript = ref('')
  const autoSpeak = ref(true)  // auto-speak responses

  return { state, isVoiceEnabled, transcript, autoSpeak }
})
```

### VoiceButton.vue

- Circular mic button at bottom of main view
- Click: toggle listening on/off
- Visual states:
  - `idle`: grey mic icon
  - `listening`: pulsing red ring + active mic icon
  - `thinking`: spinning indicator
  - `speaking`: animated sound waves
- Long-press support (optional MVP enhancement)

### TranscriptBar.vue

- Thin bar above input showing:
  - While listening: live interim transcript (grey, updating)
  - After final: final transcript (white, static)
  - While speaking: currently spoken text
- Fades out after 5 seconds of idle

### Orb.vue Update

Map voice states to visual:
- `idle`: gentle slow pulse, dim accent color
- `listening`: bright pulse, expanding rings
- `thinking`: rotating gradient, medium brightness
- `speaking`: rhythmic pulse synced with speech cadence (simplified: just faster pulse)

Use CSS animations/transitions. No canvas/WebGL — keep it lightweight.

---

## Integration with Chat

1. User clicks mic → STT starts → live transcript shown
2. STT returns final transcript → transcript sent to chat (`useChat.sendMessage()`)
3. Voice state changes to `thinking`
4. When chat response streams in:
   - Text displayed in ChatPanel as normal
   - When response is complete, full text sent to TTS
5. Voice state changes to `speaking`
6. When TTS finishes → state returns to `idle`

**If `autoSpeak` is off:** skip steps 4-6, response is text-only.

---

## Key Decisions

- Web Speech API for both STT and TTS on MVP — zero extra API keys
- Provider interfaces allow swapping to Whisper/Kokoro/Piper later without rewriting components
- STT `continuous = false` — one utterance at a time, simpler to manage
- TTS text chunking to avoid browser truncation bugs
- No server-side voice processing in this step — everything in browser
- Voice is optional — app works fully via text input

---

## Acceptance Criteria

- [ ] Clicking mic starts speech recognition, transcript appears in real-time
- [ ] Final transcript sent as chat message automatically
- [ ] Claude response is spoken via TTS
- [ ] Orb animates correctly for all 4 states
- [ ] VoiceButton shows correct visual state
- [ ] If Web Speech API not supported: mic button disabled with tooltip
- [ ] App remains fully functional via text input with voice disabled
- [ ] No extra API keys required

---

## Tests

### Frontend — `tests/composables/useSTT.test.ts` (~10 tests)
- `startListening()` calls `SpeechRecognition.start()`
- `stopListening()` calls `SpeechRecognition.stop()`
- `onresult` event updates `transcript` ref in real-time
- `onresult` with `isFinal` emits final transcript
- `onend` sets `isListening = false`
- `onerror` sets `error` ref with message
- `onerror` sets `isListening = false`
- `isSupported` is `false` when no SpeechRecognition API
- `startListening()` is no-op when not supported
- `startListening()` while already listening is no-op

### Frontend — `tests/composables/useTTS.test.ts` (~8 tests)
- `speak(text)` calls `SpeechSynthesis.speak()` with `SpeechSynthesisUtterance`
- `speak(text)` sets `isSpeaking = true`
- `onend` event sets `isSpeaking = false`
- `stop()` calls `SpeechSynthesis.cancel()`
- `stop()` sets `isSpeaking = false`
- `isSupported` is `false` when no SpeechSynthesis API
- `speak()` is no-op when not supported
- `speak()` while already speaking stops previous and starts new

### Frontend — `tests/composables/useVoiceFlow.test.ts` (~8 tests)
- Full flow: start listening → transcript → send to chat → receive response → speak
- `state` transitions: idle → listening → thinking → speaking → idle
- Cancel during listening returns to idle
- Cancel during speaking stops TTS and returns to idle
- Error during STT → state returns to idle + error set
- Text input works when voice disabled (state stays idle)
- `isVoiceAvailable` computed from STT + TTS support
- Concurrent voice request queued, not dropped

### Frontend — `tests/components/VoiceButton.test.ts` (~7 tests)
- Renders mic icon when idle
- Renders stop icon when listening
- Applies `.recording` CSS class when listening
- Click calls `startListening()` when idle
- Click calls `stopListening()` when listening
- Disabled with tooltip when voice not supported
- Accessible: has `aria-label` for screen readers

### Frontend — `tests/components/Orb.test.ts` (~6 tests)
- Renders with `idle` state by default
- Applies `.orb--idle` class for idle
- Applies `.orb--listening` class for listening
- Applies `.orb--thinking` class for thinking
- Applies `.orb--speaking` class for speaking
- Transition between states updates class immediately

### Frontend — `tests/components/TranscriptBar.test.ts` (~4 tests)
- Hidden when no transcript
- Shows interim transcript while listening
- Shows final transcript briefly after recognition ends
- Clears after timeout

### Regression suite
```bash
cd backend && python -m pytest tests/ -v           # ALL backend tests
cd frontend && npx vitest run                       # ALL frontend tests
```

### Run
```bash
cd backend && python -m pytest tests/ -v           # ~96 backend tests (regression)
cd frontend && npx vitest run                      # ~103 frontend tests
```

**Expected total: ~199 tests**

---

## Definition of Done

- [ ] All files listed in this step are created
- [ ] `python -m pytest tests/ -v` — all backend tests still pass (regression)
- [ ] `npx vitest run` — all ~103 frontend tests pass (including regression)
- [ ] Manual: mic click → speech recognized → response spoken
- [ ] Orb transitions through all 4 states correctly
- [ ] App works fully in text-only mode when voice unavailable
- [ ] Committed with message `feat: step-06 voice input/output`
- [ ] [index-spec.md](../index-spec.md) updated with ✅
