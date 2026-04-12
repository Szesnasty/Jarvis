<template>
  <div class="main-page">
    <div class="main-page__layout">
      <SessionHistory
        :sessions="sessions"
        :active-session-id="activeSessionId"
        @select="handleSessionSelect"
        @new-session="handleNewSession"
      />
      <main class="main-page__content">
        <div class="main-page__orb-area" :class="{ 'main-page__orb-area--hero': messages.length === 0 }">
          <Orb :state="orbState" />
        </div>
        <TranscriptBar :transcript="transcript" :visible="voiceState !== 'idle'" />
        <ChatPanel
          :messages="messages"
          :current-response="currentResponse"
          :is-loading="isLoading"
          :tool-activity="toolActivity"
          :voice-state="voiceState"
          :voice-supported="isVoiceAvailable"
          @send="handleSend"
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

const { checkHealth } = useAppState()
const chat = useChat()
const { messages, currentResponse, isLoading, toolActivity, init, sendMessage } = chat

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
}

function handleNewSession(): void {
  sessionsState.clearActive()
  messages.value = []
  init()
}

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

.main-page__orb-area {
  padding: 1rem 0;
  transition: all 0.5s ease;
  flex-shrink: 0;
}

.main-page__orb-area--hero {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
