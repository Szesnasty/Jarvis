<template>
  <div class="main-page">
    <div class="main-page__layout">
      <SessionHistory
        :sessions="sessions"
        :active-session-id="activeSessionId"
        :loading="sessionsState.loading.value"
        :on-delete="handleSessionDelete"
        @select="handleSessionSelect"
        @new-session="handleNewSession"
      />
      <main class="main-page__content">
        <div class="main-page__orb-area" :class="{ 'main-page__orb-area--hero': !chatActive }">
          <Orb :state="orbState" />
        </div>
        <TranscriptBar :transcript="transcript" :visible="voiceState !== 'idle'" />
        <ChatPanel
          :messages="messages"
          :current-response="currentResponse"
          :is-loading="isLoading"
          :tool-activity="toolActivity"
          :error="error"
          :can-retry="canRetry"
          :voice-state="voiceState"
          :voice-supported="isVoiceAvailable"
          @send="handleSend"
          @retry="chat.retry()"
          @toggle-voice="handleVoiceToggle"
        />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { OrbState } from '~/types'
import { createWebSpeechSTT } from '~/composables/stt/webSpeechSTT'
import { createWebSpeechTTS } from '~/composables/tts/webSpeechTTS'
import { useChat } from '~/composables/useChat'
import { useSessions } from '~/composables/useSessions'
import { useVoice } from '~/composables/useVoice'

const { checkHealth, chatActive } = useAppState()
const chat = useChat()
const { messages, currentResponse, isLoading, toolActivity, error, canRetry, init, sendMessage } = chat

const sessionsState = useSessions()
const { sessions, activeSessionId } = sessionsState

const stt = createWebSpeechSTT()
const tts = createWebSpeechTTS()
const voice = useVoice(stt, tts)
const { state: voiceState, transcript, isVoiceAvailable } = voice

voice.bindChat(sendMessage)

const orbState = computed<OrbState>(() => {
  if (voiceState.value !== 'idle') return voiceState.value
  if (isLoading.value) return 'thinking'
  return 'idle'
})

// When chat response completes and voice initiated the request, speak it
watch(isLoading, async (loading, wasLoading) => {
  if (wasLoading && !loading && voiceState.value === 'thinking') {
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg?.role === 'assistant') {
      await voice.speakResponse(lastMsg.content)
    }
  }
})

function handleSend(content: string): void {
  sendMessage(content)
}

function handleVoiceToggle(): void {
  if (voiceState.value === 'listening') {
    voice.stopListening()
  } else if (voiceState.value === 'speaking') {
    voice.cancel()
  } else {
    voice.startListening()
  }
}

async function handleSessionSelect(sessionId: string): Promise<void> {
  const detail = await sessionsState.selectSession(sessionId)
  messages.value = detail.messages
  // Reconnect the WebSocket to the selected session so backend is in sync
  chat.sessionId.value = sessionId
  try { sessionStorage.setItem('jarvis_session_id', sessionId) } catch {}
  chat.disconnect()
  init()
}

function handleNewSession(): void {
  sessionsState.clearActive()
  messages.value = []
  chat.sessionId.value = ''
  try { sessionStorage.removeItem('jarvis_session_id') } catch {}
  chat.disconnect()
  init()
}

async function handleSessionDelete(sessionId: string): Promise<void> {
  try {
    await sessionsState.removeSession(sessionId)
  } catch {
    return
  }
  if (messages.value.length && !activeSessionId.value) {
    messages.value = []
    chat.sessionId.value = ''
    try { sessionStorage.removeItem('jarvis_session_id') } catch {}
    chat.disconnect()
    init()
  }
}

watch(
  () => messages.value.length,
  (len) => { chatActive.value = len > 0 },
  { immediate: true },
)

// Refresh session list when a new session starts
watch(
  () => chat.sessionId.value,
  (id) => {
    if (id) sessionsState.loadSessions()
  },
)

// Refresh session list when a response completes (updates title/preview)
watch(isLoading, (loading, wasLoading) => {
  if (wasLoading && !loading && chat.sessionId.value) {
    sessionsState.loadSessions()
  }
})

onMounted(async () => {
  checkHealth()
  init()
  await sessionsState.loadSessions()
})
</script>

<style scoped>
.main-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

.main-page__layout {
  flex: 1;
  display: flex;
  min-height: 0;
}

.main-page__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 0;
  overflow: hidden;
}

/*
  Orb is position:fixed so it can escape all containers and fly to the navbar.
  Hero  → centered inside main content area (sidebar ≈ 280px, navbar ≈ 40px)
  Mini  → overlaid on the "JARVIS" logo text in the top-left of the status bar
*/
.main-page__orb-area {
  position: fixed;
  z-index: 200;
  pointer-events: none;
  /* Mini: center of the JARVIS label (navbar padding 20px, text ≈ 56px wide → center ≈ 48px; navbar height ≈ 40px → center ≈ 20px) */
  top: 20px;
  left: 48px;
  transform: translate(-50%, -50%) scale(0.13);
  transition:
    top 0.85s cubic-bezier(0.4, 0, 0.2, 1),
    left 0.85s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.85s cubic-bezier(0.4, 0, 0.2, 1);
}

/* Hero: centered in the content area (viewport minus sidebar 280px and navbar 40px) */
.main-page__orb-area--hero {
  top: calc(20px + 50vh);
  left: calc(140px + 50vw);
  transform: translate(-50%, -50%) scale(1);
}
</style>
