<script setup lang="ts">
import type { ChatMessage } from '~/types'

const props = defineProps<{
  messages: ChatMessage[]
  currentResponse: string
  isLoading: boolean
  toolActivity: string
}>()

const emit = defineEmits<{
  send: [content: string]
}>()

const input = ref('')
const messagesContainer = ref<HTMLElement | null>(null)

function handleSend(): void {
  const text = input.value.trim()
  if (!text || props.isLoading) return
  emit('send', text)
  input.value = ''
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

watch(
  () => [props.messages.length, props.currentResponse],
  () => {
    nextTick(() => {
      if (messagesContainer.value) {
        messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
      }
    })
  },
)
</script>

<template>
  <div class="chat-panel">
    <div ref="messagesContainer" class="chat-panel__messages">
      <div
        v-for="(msg, i) in messages"
        :key="i"
        class="chat-panel__message"
        :class="msg.role"
      >
        <div class="chat-panel__bubble">
          {{ msg.content }}
        </div>
      </div>

      <div v-if="currentResponse" class="chat-panel__message assistant">
        <div class="chat-panel__bubble">
          {{ currentResponse }}
          <span class="chat-panel__cursor">▊</span>
        </div>
      </div>

      <div v-if="toolActivity" class="chat-panel__activity">
        {{ toolActivity }}
      </div>
    </div>

    <div class="chat-panel__input-bar">
      <input
        v-model="input"
        type="text"
        class="chat-panel__input"
        placeholder="Talk to Jarvis..."
        :disabled="isLoading"
        @keydown="handleKeydown"
      />
      <button
        class="chat-panel__send"
        :disabled="isLoading || !input.trim()"
        @click="handleSend"
      >
        Send
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.chat-panel__messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.chat-panel__message {
  display: flex;
}

.chat-panel__message.user {
  justify-content: flex-end;
}

.chat-panel__message.assistant {
  justify-content: flex-start;
}

.chat-panel__bubble {
  max-width: 75%;
  padding: 0.5rem 0.75rem;
  border-radius: 0.75rem;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-panel__message.user .chat-panel__bubble {
  background: #2563eb;
  color: white;
}

.chat-panel__message.assistant .chat-panel__bubble {
  background: #1e293b;
  color: #e2e8f0;
}

.chat-panel__cursor {
  animation: blink 0.8s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

.chat-panel__activity {
  font-size: 0.8rem;
  color: #94a3b8;
  padding: 0.25rem 0;
  font-style: italic;
}

.chat-panel__input-bar {
  display: flex;
  gap: 0.5rem;
  padding: 1rem;
  border-top: 1px solid #222;
}

.chat-panel__input {
  flex: 1;
}

.chat-panel__send {
  padding: 0.5rem 1rem;
  background: #2563eb;
  color: white;
  border: none;
  border-radius: 0.5rem;
  cursor: pointer;
}

.chat-panel__send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
