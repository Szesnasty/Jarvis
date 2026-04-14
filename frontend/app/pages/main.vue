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

        <!-- Duel debate view replaces chat when duel is active -->
        <DuelDebateView
          v-if="duel.isActive.value"
          :topic="duel.topic.value"
          :events="duel.events.value"
          :phase="duel.phase.value"
          :verdict="duel.verdict.value"
          :current-texts="duel.currentTexts.value"
          :error-msg="duel.errorMsg.value"
          @cancel="handleDuelCancel"
        />

        <ChatPanel
          v-else
          :messages="messages"
          :current-response="currentResponse"
          :is-loading="isLoading"
          :tool-activity="toolActivity"
          :error="error"
          :can-retry="canRetry"
          :voice-state="voiceState"
          :voice-supported="isVoiceAvailable"
          :duel-setup-open="duel.showSetup.value"
          @send="handleSend"
          @retry="chat.retry()"
          @toggle-voice="handleVoiceToggle"
          @open-duel="duel.openSetup()"
          @start-duel="handleDuelStart"
          @cancel-duel-setup="duel.closeSetup()"
        />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DuelConfig, OrbState } from '~/types'
import { createWebSpeechSTT } from '~/composables/stt/webSpeechSTT'
import { createWebSpeechTTS } from '~/composables/tts/webSpeechTTS'
import { useChat } from '~/composables/useChat'
import { useSessions } from '~/composables/useSessions'
import { useVoice } from '~/composables/useVoice'

const { checkHealth, chatActive } = useAppState()
const chat = useChat()
const { messages, currentResponse, isLoading, toolActivity, error, canRetry, duel, init, sendMessage } = chat

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

function handleDuelStart(config: DuelConfig): void {
  duel.start(config)
}

function handleDuelCancel(): void {
  duel.cancel()
}

// When duel finishes with a verdict, append it as a chat message and keep duel view for a bit
watch(() => duel.phase.value, (p) => {
  if (p === 'done' && duel.verdict.value) {
    const v = duel.verdict.value
    const summary = `⚔️ **Duel Verdict** — "${duel.topic.value}"\n\n🏆 Winner: **${v.winner}**\n\n${v.reasoning}${v.recommendation ? '\n\n**Recommendation:** ' + v.recommendation : ''}${v.action_items?.length ? '\n\n**Action Items:**\n' + v.action_items.map((a: string) => `- ${a}`).join('\n') : ''}`
    messages.value.push({ role: 'assistant', content: summary })
  }
})

async function handleSessionSelect(sessionId: string): Promise<void> {
  duel.cancel()
  const detail = await sessionsState.selectSession(sessionId)
  messages.value = detail.messages
  // Reconnect the WebSocket to the selected session so backend is in sync
  chat.sessionId.value = sessionId
  try { sessionStorage.setItem('jarvis_session_id', sessionId) } catch {}
  chat.disconnect()
  init()
}

function handleNewSession(): void {
  duel.cancel()
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
  (len) => { chatActive.value = len > 0 || duel.isActive.value },
  { immediate: true },
)

// Keep Orb shrunk while duel is active
watch(
  () => duel.isActive.value,
  (active) => { if (active) chatActive.value = true },
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

  // Handle graph_scope query param from "Ask about this" in graph view
  const route = useRoute()
  const graphScope = route.query.graph_scope as string | undefined
  if (graphScope) {
    const label = graphScope.includes(':') ? graphScope.split(':').slice(1).join(':') : graphScope
    sendMessage(
      `Summarize the key content of "${label}" and show how it connects to other notes in my knowledge base. Focus on insights, not metadata.`,
      { graphScope },
    )
  }
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
