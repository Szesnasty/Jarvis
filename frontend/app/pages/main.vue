<template>
  <div class="main-page">
    <StatusBar />
    <main class="main-page__content">
      <Orb :state="orbState" />
      <TranscriptBar :transcript="transcript" :visible="voiceState !== 'idle'" />
      <ChatPanel
        :messages="messages"
        :current-response="currentResponse"
        :is-loading="isLoading"
        :tool-activity="toolActivity"
        @send="handleSend"
      />
      <div class="main-page__voice-bar">
        <VoiceButton
          :state="voiceState"
          :supported="isVoiceAvailable"
          @toggle="handleVoiceToggle"
        />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import type { OrbState } from '~/types'
import { createWebSpeechSTT } from '~/composables/stt/webSpeechSTT'
import { createWebSpeechTTS } from '~/composables/tts/webSpeechTTS'
import { useChat } from '~/composables/useChat'
import { useVoice } from '~/composables/useVoice'

const { checkHealth } = useAppState()
const chat = useChat()
const { messages, currentResponse, isLoading, toolActivity, init, sendMessage } = chat

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

onMounted(() => {
  checkHealth()
  init()
})
</script>

<style scoped>
.main-page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.main-page__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding-top: 2rem;
}

.main-page__voice-bar {
  padding: 0.5rem;
  display: flex;
  justify-content: center;
}
</style>
