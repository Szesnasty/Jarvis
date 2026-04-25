<script setup lang="ts">
import type { ChatMessage, DuelConfig, OrbState, UrlIngestResult } from '~/types'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useSpecialists } from '~/composables/useSpecialists'
import { MODEL_CATALOG } from '~/composables/useApiKeys'
import { PROVIDER_ICONS } from '~/composables/providerIcons'

marked.setOptions({ breaks: true, gfm: true })

function renderMarkdown(text: string): string {
  const html = marked.parse(text) as string
  return DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
}

function modelLabel(provider?: string, model?: string): string {
  if (!provider || !model) return ''
  const catalog = MODEL_CATALOG[provider]
  return catalog?.find(m => m.id === model)?.label ?? model
}

function providerIcon(provider?: string): string {
  if (!provider) return ''
  return (PROVIDER_ICONS as Record<string, string>)[provider] ?? ''
}

function formatTime(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('pl-PL', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

const { activeSpecialists, deactivate, specialists: allSpecialists, load: loadSpecialists } = useSpecialists()

const props = defineProps<{
  messages: ChatMessage[]
  currentResponse: string
  isLoading: boolean
  toolActivity: string
  error?: string
  canRetry?: boolean
  voiceState?: OrbState
  voiceSupported?: boolean
  duelSetupOpen?: boolean
  ollamaDown?: boolean
  slowResponse?: string
}>()

const emit = defineEmits<{
  send: [content: string]
  retry: []
  toggleVoice: []
  openDuel: []
  startDuel: [config: DuelConfig]
  cancelDuelSetup: []
  reconnectOllama: []
  switchToCloud: []
}>()

// Load specialists when duel setup opens so we have the list
watch(() => props.duelSetupOpen, (open) => {
  if (open && allSpecialists.value.length === 0) loadSpecialists()
})
const { ingestUrl } = useApi()

const input = ref('')
const inputEl = ref<HTMLTextAreaElement | null>(null)
const messagesContainer = ref<HTMLElement | null>(null)
const ingestLoading = ref(false)
const ingestResult = ref<string | null>(null)

const URL_RE = /https?:\/\/[^\s.,;!?)>\]]+/
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
  if (text.toLowerCase() === '/duel') {
    input.value = ''
    emit('openDuel')
    return
  }
  emit('send', text)
  input.value = ''
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    handleSend()
  }
}

function autoResize(event: Event): void {
  const el = event.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 150) + 'px'
}

watch(
  () => props.isLoading,
  (loading, wasLoading) => {
    if (wasLoading && !loading) {
      nextTick(() => inputEl.value?.focus())
    }
  },
)

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
    <Transition name="badge-slide">
      <div v-if="activeSpecialists.length" class="chat-panel__specialist-bar">
        <SpecialistBadge
          v-for="spec in activeSpecialists"
          :key="spec.id"
          :specialist="spec"
          @deactivate="deactivate(spec.id)"
        />
      </div>
    </Transition>

    <!-- Ollama offline banner -->
    <div v-if="ollamaDown" class="chat-panel__ollama-banner">
      <span class="chat-panel__ollama-banner-icon">⚠️</span>
      <span class="chat-panel__ollama-banner-text">Ollama is not responding. Local model chat is unavailable.</span>
      <button class="chat-panel__ollama-banner-btn" @click="emit('reconnectOllama')">Reconnect</button>
      <button class="chat-panel__ollama-banner-btn chat-panel__ollama-banner-btn--alt" @click="emit('switchToCloud')">Switch to Cloud AI</button>
    </div>

    <!-- Slow response indicator for local models -->
    <div v-if="slowResponse" class="chat-panel__slow-indicator">
      <span class="chat-panel__slow-icon">⏳</span>
      <span>{{ slowResponse }}</span>
    </div>

    <div ref="messagesContainer" class="chat-panel__messages">
      <div
        v-for="(msg, i) in messages"
        :key="`${msg.role}-${i}-${msg.content.slice(0, 20)}`"
        class="chat-panel__message"
        :class="msg.role"
      >
        <div
          class="chat-panel__bubble"
          :class="{ 'chat-panel__bubble--md': msg.role === 'assistant' }"
        >
          <div v-if="msg.role === 'assistant' && (msg.model || msg.timestamp)" class="chat-panel__meta">
            <span v-if="msg.model" class="chat-panel__meta-model">
              <span class="chat-panel__meta-icon" v-html="providerIcon(msg.provider)" />
              {{ modelLabel(msg.provider, msg.model) }}
            </span>
            <span v-if="msg.timestamp" class="chat-panel__meta-time">{{ formatTime(msg.timestamp) }}</span>
          </div>
          <div v-else-if="msg.role === 'user' && msg.timestamp" class="chat-panel__meta">
            <span class="chat-panel__meta-time">{{ formatTime(msg.timestamp) }}</span>
          </div>
          <div v-if="msg.role === 'assistant'" v-html="renderMarkdown(msg.content)" />
          <template v-else>{{ msg.content }}</template>
          <TraceList v-if="msg.role === 'assistant' && msg.trace" :items="msg.trace" />
        </div>
      </div>

      <div v-if="currentResponse" class="chat-panel__message assistant">
        <div class="chat-panel__bubble chat-panel__bubble--md">
          <span v-html="renderMarkdown(currentResponse)" />
          <span class="chat-panel__cursor">▊</span>
        </div>
      </div>

      <!-- Typing indicator (dots) when loading but no response yet -->
      <div v-if="isLoading && !currentResponse && !toolActivity" class="chat-panel__message assistant">
        <div class="chat-panel__bubble chat-panel__typing">
          <span class="chat-panel__dot" />
          <span class="chat-panel__dot" />
          <span class="chat-panel__dot" />
        </div>
      </div>

      <div v-if="toolActivity" class="chat-panel__activity">
        <span class="chat-panel__activity-spinner" />
        {{ toolActivity }}
      </div>

      <div v-if="error" class="chat-panel__error">
        <span class="chat-panel__error-icon">⚠</span>
        <span class="chat-panel__error-text">{{ error }}</span>
        <button v-if="canRetry" class="chat-panel__error-retry" @click="emit('retry')">Retry</button>
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

    <!-- Duel Setup Panel -->
    <Transition name="setup-slide">
      <DuelSetup
        v-if="duelSetupOpen"
        :specialists="allSpecialists"
        :prefill-topic="input.trim()"
        @start="emit('startDuel', $event)"
        @cancel="emit('cancelDuelSetup')"
      />
    </Transition>

    <div class="chat-panel__input-bar">
      <textarea
        ref="inputEl"
        v-model="input"
        class="chat-panel__input"
        placeholder="Talk to Jarvis..."
        rows="1"
        :disabled="isLoading"
        @keydown="handleKeydown"
        @input="autoResize"
      />
      <ModelSelector />
      <HelpIcon
        aria-label="About retrieval and Smart Connect"
        action-label="Open Settings → Smart Connect"
        text="Jarvis answers from your local notes. After importing big documents (PDFs, large Markdown), their sections are searchable right away — but cross-document connections only show up after Smart Connect runs on them."
      />
      <!-- Voice button hidden for now -->
      <button
        class="chat-panel__icon-btn chat-panel__icon-btn--duel"
        aria-label="Duel Mode"
        :disabled="isLoading"
        @click="emit('openDuel')"
      >
        ⚔️
      </button>
      <button
        class="chat-panel__icon-btn chat-panel__icon-btn--send"
        :disabled="isLoading || !input.trim()"
        aria-label="Send message"
        @click="handleSend"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"/>
          <polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
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
  width: 100%;
  max-width: 900px;
}

.chat-panel__specialist-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.4rem 1.5rem;
  border-radius: 16px;
  margin-top: 12px;
  border-bottom: 1px solid var(--border-subtle);
  background:
    linear-gradient(90deg, var(--neon-cyan-08) 0%, transparent 60%),
    var(--bg-surface);
  flex-shrink: 0;
}

.badge-slide-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.badge-slide-leave-active {
  transition: all 0.2s ease;
}
.badge-slide-enter-from {
  opacity: 0;
  transform: translateY(-100%);
}
.badge-slide-leave-to {
  opacity: 0;
  transform: translateY(-100%);
}

.chat-panel__messages {
  flex: 1;
  overflow-y: auto;
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Ollama offline banner */
.chat-panel__ollama-banner {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1rem;
  margin: 0.5rem 1.5rem 0;
  border-radius: 8px;
  background: rgba(251, 191, 36, 0.06);
  border: 1px solid rgba(251, 191, 36, 0.2);
  font-size: 0.82rem;
  color: #fbbf24;
  flex-shrink: 0;
}

.chat-panel__ollama-banner-icon {
  font-size: 0.9rem;
}

.chat-panel__ollama-banner-text {
  flex: 1;
}

.chat-panel__ollama-banner-btn {
  padding: 0.25rem 0.6rem;
  border-radius: 5px;
  border: 1px solid rgba(251, 191, 36, 0.3);
  background: transparent;
  color: #fbbf24;
  font-size: 0.75rem;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.chat-panel__ollama-banner-btn:hover {
  background: rgba(251, 191, 36, 0.1);
}

.chat-panel__ollama-banner-btn--alt {
  border-color: var(--border-default);
  color: var(--text-secondary);
}

.chat-panel__ollama-banner-btn--alt:hover {
  background: rgba(255, 255, 255, 0.04);
}

/* Slow response indicator */
.chat-panel__slow-indicator {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 1rem;
  margin: 0.3rem 1.5rem 0;
  font-size: 0.78rem;
  color: var(--text-muted);
  flex-shrink: 0;
}

.chat-panel__slow-icon {
  font-size: 0.85rem;
}

.chat-panel__message {
  display: flex;
  animation: slideIn 0.25s ease-out;
}

.chat-panel__message.user {
  justify-content: flex-end;
}

.chat-panel__message.assistant {
  justify-content: flex-start;
}

.chat-panel__bubble {
  max-width: 78%;
  padding: 0.7rem 1rem;
  border-radius: 0.85rem;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.55;
  font-size: 0.95rem;
}

/* Markdown content styles */
.chat-panel__bubble--md {
  white-space: normal;
}
.chat-panel__bubble--md :deep(p) {
  margin: 0 0 0.5em;
}
.chat-panel__bubble--md :deep(p:last-child) {
  margin-bottom: 0;
}
.chat-panel__bubble--md :deep(strong) {
  color: var(--neon-cyan);
  font-weight: 600;
}
.chat-panel__bubble--md :deep(em) {
  color: var(--text-secondary);
  font-style: italic;
}
.chat-panel__bubble--md :deep(code) {
  background: rgba(2, 254, 255, 0.08);
  border: 1px solid var(--neon-cyan-15);
  border-radius: 4px;
  padding: 0.1em 0.4em;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.88em;
  color: var(--neon-cyan);
}
.chat-panel__bubble--md :deep(pre) {
  background: var(--bg-deep);
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 0.85rem 1rem;
  overflow-x: auto;
  margin: 0.5em 0;
}
.chat-panel__bubble--md :deep(pre code) {
  background: none;
  border: none;
  padding: 0;
  font-size: 0.85em;
  color: var(--text-primary);
}
.chat-panel__bubble--md :deep(ul),
.chat-panel__bubble--md :deep(ol) {
  margin: 0.4em 0;
  padding-left: 1.4em;
}
.chat-panel__bubble--md :deep(li) {
  margin: 0.2em 0;
}
.chat-panel__bubble--md :deep(h1),
.chat-panel__bubble--md :deep(h2),
.chat-panel__bubble--md :deep(h3) {
  color: var(--neon-cyan);
  margin: 0.6em 0 0.3em;
  font-size: 1em;
  font-weight: 700;
}
.chat-panel__bubble--md :deep(blockquote) {
  border-left: 3px solid var(--neon-cyan-30);
  margin: 0.5em 0;
  padding-left: 0.75em;
  opacity: 0.8;
}
.chat-panel__bubble--md :deep(a) {
  color: var(--neon-cyan);
  text-decoration: underline;
  text-underline-offset: 2px;
}

/* --- Messages --- */
.chat-panel__message.user .chat-panel__bubble {
  background: rgba(2, 254, 255, 0.1);
  border: 1px solid rgba(2, 254, 255, 0.2);
  color: var(--text-primary);
}

.chat-panel__message.assistant .chat-panel__bubble {
  background: var(--bg-surface);
  border: 1px solid var(--border-subtle);
  color: var(--text-primary);
}

.chat-panel__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  font-size: 0.65rem;
  color: var(--text-muted);
  opacity: 0.6;
  margin-bottom: 0.35rem;
  user-select: none;
  line-height: 1;
}

.chat-panel__meta-model {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}

.chat-panel__meta-icon {
  display: inline-flex;
  width: 12px;
  height: 12px;
}

.chat-panel__meta-icon :deep(svg) {
  width: 12px;
  height: 12px;
}

.chat-panel__meta-time {
  margin-left: auto;
  white-space: nowrap;
}

.chat-panel__cursor {
  color: var(--neon-cyan);
  animation: blink 0.8s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

.chat-panel__activity {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  color: var(--neon-cyan-60);
  padding: 0.25rem 0;
  font-style: italic;
}

.chat-panel__activity-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--neon-cyan-30);
  border-top-color: var(--neon-cyan);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* --- Error bar --- */
.chat-panel__error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0.5rem 0;
  padding: 0.6rem 0.85rem;
  font-size: 0.85rem;
  color: rgba(251, 146, 60, 0.95);
  background: rgba(251, 146, 60, 0.06);
  border: 1px solid rgba(251, 146, 60, 0.2);
  border-radius: 8px;
  animation: slideIn 0.25s ease-out;
}

.chat-panel__error-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

.chat-panel__error-text {
  flex: 1;
}

.chat-panel__error-retry {
  flex-shrink: 0;
  padding: 0.25rem 0.75rem;
  font-size: 0.8rem;
  border: 1px solid rgba(251, 146, 60, 0.3);
  border-radius: 6px;
  background: rgba(251, 146, 60, 0.1);
  color: rgba(251, 146, 60, 0.95);
  cursor: pointer;
  transition: all 0.2s;
}

.chat-panel__error-retry:hover {
  background: rgba(251, 146, 60, 0.2);
  border-color: rgba(251, 146, 60, 0.5);
}

/* --- Empty state --- */
.chat-panel__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  gap: 0.75rem;
  opacity: 0.5;
  padding: 3rem 1rem;
}

.chat-panel__empty-icon {
  font-size: 2.5rem;
}

.chat-panel__empty-text {
  font-size: 0.9rem;
  color: var(--text-muted);
  text-align: center;
  max-width: 300px;
  line-height: 1.5;
}

/* --- Typing dots --- */
.chat-panel__typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0.85rem 1.1rem !important;
  min-height: auto;
}

.chat-panel__dot {
  width: 7px;
  height: 7px;
  background: var(--neon-cyan-60);
  border-radius: 50%;
  animation: typingBounce 1.2s ease-in-out infinite;
}

.chat-panel__dot:nth-child(2) { animation-delay: 0.15s; }
.chat-panel__dot:nth-child(3) { animation-delay: 0.3s; }

@keyframes typingBounce {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.4;
  }
  30% {
    transform: translateY(-5px);
    opacity: 1;
  }
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chat-panel__input-bar {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 1.2rem 1.5rem;
  border-top: 1px solid var(--border-default);
  background: var(--bg-base);
  flex-shrink: 0;
}

.chat-panel__input {
  flex: 1;
  resize: none;
  min-height: 46px;
  max-height: 150px;
  padding: 0.7rem 1rem;
  font-size: 0.95rem;
  line-height: 1.5;
  color: var(--text-primary);
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 12px;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
  font-family: inherit;
}

.chat-panel__input:focus {
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 0 2px var(--neon-cyan-08), 0 0 15px var(--neon-cyan-08);
}

.chat-panel__input::placeholder {
  color: var(--text-muted);
}

.chat-panel__icon-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
}

.chat-panel__icon-btn:hover {
  color: var(--neon-cyan);
  border-color: var(--neon-cyan-30);
  background: var(--bg-elevated);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}

.chat-panel__icon-btn--active {
  color: var(--neon-red);
  border-color: rgba(239, 68, 68, 0.5);
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.15);
  animation: mic-pulse 1.2s ease-in-out infinite;
}

.chat-panel__icon-btn--send {
  background: rgba(2, 254, 255, 0.12);
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan);
}

.chat-panel__icon-btn--send:hover {
  background: rgba(2, 254, 255, 0.2);
  border-color: var(--neon-cyan-60);
  color: var(--neon-cyan);
  box-shadow: 0 0 15px var(--neon-cyan-15);
}

.chat-panel__icon-btn--send:disabled {
  opacity: 0.25;
  cursor: not-allowed;
  background: var(--bg-surface);
  border-color: var(--border-subtle);
  color: var(--text-muted);
  box-shadow: none;
}

@keyframes mic-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.3); }
  50% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
}

.chat-panel__url-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.6rem 1.5rem;
  background: var(--neon-cyan-08);
  border-top: 1px solid var(--border-default);
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
  color: var(--text-secondary);
}

.chat-panel__url-action {
  flex-shrink: 0;
  padding: 0.3rem 0.85rem;
  border: 1px solid var(--neon-cyan-30);
  border-radius: 6px;
  background: transparent;
  color: var(--neon-cyan);
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.2s;
}

.chat-panel__url-action:hover {
  background: var(--neon-cyan-08);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}

.chat-panel__url-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-panel__url-result {
  padding: 0.4rem 1.5rem;
  font-size: 0.8rem;
  border-top: 1px solid var(--border-subtle);
  color: var(--text-secondary);
}

/* Duel button */
.chat-panel__icon-btn--duel {
  font-size: 1rem;
  line-height: 1;
}

.chat-panel__icon-btn--duel:hover {
  border-color: var(--neon-yellow);
  box-shadow: 0 0 10px rgba(234, 179, 8, 0.1);
}

.chat-panel__icon-btn--duel:disabled {
  opacity: 0.25;
  cursor: not-allowed;
}

/* Setup slide transition */
.setup-slide-enter-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.setup-slide-leave-active {
  transition: all 0.2s ease;
}
.setup-slide-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.setup-slide-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
</style>
