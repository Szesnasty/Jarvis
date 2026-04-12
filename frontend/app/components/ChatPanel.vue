<script setup lang="ts">
import type { ChatMessage, UrlIngestResult } from '~/types'

const props = defineProps<{
  messages: ChatMessage[]
  currentResponse: string
  isLoading: boolean
  toolActivity: string
}>()

const emit = defineEmits<{
  send: [content: string]
}>()

const { ingestUrl } = useApi()

const input = ref('')
const messagesContainer = ref<HTMLElement | null>(null)
const ingestLoading = ref(false)
const ingestResult = ref<string | null>(null)

const URL_RE = /https?:\/\/[^\s]+/
const YT_RE = /(?:youtube\.com\/watch\?.*v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([\w-]{11})/

const detectedUrl = computed(() => {
  const match = input.value.match(URL_RE)
  return match ? match[0] : null
})

const urlType = computed(() => {
  if (!detectedUrl.value) return null
  return YT_RE.test(detectedUrl.value) ? 'youtube' : 'webpage'
})

async function handleSaveUrl() {
  if (!detectedUrl.value || ingestLoading.value) return
  ingestLoading.value = true
  ingestResult.value = null
  try {
    const res = await ingestUrl(detectedUrl.value)
    ingestResult.value = `✅ Saved: ${res.path} (${res.word_count} words)`
    setTimeout(() => { ingestResult.value = null }, 4000)
  } catch {
    ingestResult.value = '❌ Import failed'
    setTimeout(() => { ingestResult.value = null }, 4000)
  } finally {
    ingestLoading.value = false
  }
}

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

    <div v-if="detectedUrl" class="chat-panel__url-bar">
      <span class="chat-panel__url-icon">{{ urlType === 'youtube' ? '🎬' : '🔗' }}</span>
      <span class="chat-panel__url-text">{{ detectedUrl }}</span>
      <button
        class="chat-panel__url-action"
        :disabled="ingestLoading"
        @click="handleSaveUrl"
      >
        {{ ingestLoading ? 'Saving...' : 'Save to memory' }}
      </button>
    </div>

    <div v-if="ingestResult" class="chat-panel__url-result">
      {{ ingestResult }}
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

.chat-panel__url-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background: rgba(96, 165, 250, 0.08);
  border-top: 1px solid #222;
  font-size: 0.85rem;
}

.chat-panel__url-icon {
  flex-shrink: 0;
}

.chat-panel__url-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  opacity: 0.7;
}

.chat-panel__url-action {
  flex-shrink: 0;
  padding: 0.25rem 0.75rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 4px;
  background: transparent;
  color: #60a5fa;
  cursor: pointer;
  font-size: 0.8rem;
}

.chat-panel__url-action:hover {
  background: rgba(96, 165, 250, 0.15);
}

.chat-panel__url-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-panel__url-result {
  padding: 0.35rem 1rem;
  font-size: 0.8rem;
  border-top: 1px solid #222;
}
</style>
