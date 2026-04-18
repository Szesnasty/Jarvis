<template>
  <Teleport to="body">
    <div v-if="show" class="modal-overlay" @click.self="$emit('close')" @keydown.escape="$emit('close')">
      <div class="modal-card" role="dialog" aria-modal="true" ref="modalRef">
        <h2 class="modal-card__title">
          <span class="modal-card__icon" :style="{ color: provider.color }" v-html="provider.icon"></span>
          Add {{ provider.name }} Key
        </h2>

        <div class="modal-card__info">
          <span class="modal-card__info-icon" v-html="ICON_INFO"></span>
          <span>Stored locally in your browser. Never sent to our server.</span>
        </div>

        <div class="modal-card__warning-box" role="alert">
          <strong>⚠️ Privacy notice</strong>
          <p>
            Adding a {{ provider.name }} key means your chats — including any
            <strong>retrieved notes, imported Jira issues</strong> and other context
            Jarvis pulls in to answer — will be sent to {{ provider.name }} whenever
            you select this provider.
          </p>
          <p>
            Prefer fully local? Use <strong>Ollama</strong> instead, or enable
            <strong>Offline mode</strong> in Settings → Privacy &amp; Network to
            hard-block all cloud providers.
          </p>
        </div>

        <label class="modal-card__label" for="api-key-input">API Key</label>
        <div class="modal-card__input-row">
          <input
            id="api-key-input"
            ref="inputRef"
            v-model="keyValue"
            :type="showKey ? 'text' : 'password'"
            class="modal-card__input"
            :placeholder="provider.keyPrefix + '...'"
            autocomplete="off"
            spellcheck="false"
            @keydown.enter="save"
          />
          <button class="modal-card__toggle" type="button" @click="showKey = !showKey" :title="showKey ? 'Hide' : 'Show'">
            <span v-html="showKey ? ICON_EYE_CLOSED : ICON_EYE_OPEN"></span>
          </button>
        </div>

        <p v-if="prefixWarning" class="modal-card__warning">
          Key doesn't start with "{{ provider.keyPrefix }}" — are you sure it's correct?
        </p>

        <label class="modal-card__checkbox">
          <input type="checkbox" v-model="remember" />
          <span>Remember on this device</span>
        </label>
        <p class="modal-card__checkbox-hint">Key will persist across browser sessions</p>

        <div class="modal-card__help">
          This key is used to call {{ provider.name }}'s API directly.
          <a :href="provider.docsUrl" target="_blank" rel="noopener" class="modal-card__link">
            Get yours at {{ provider.docsUrl.replace('https://', '').split('/')[0] }} →
          </a>
        </div>

        <div class="modal-card__footer">
          <button class="modal-card__btn modal-card__btn--cancel" @click="$emit('close')">Cancel</button>
          <button class="modal-card__btn modal-card__btn--save" :disabled="!keyValue.trim()" @click="save">Save Key</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import type { ProviderConfig } from '~/types'
import { ICON_EYE_OPEN, ICON_EYE_CLOSED, ICON_INFO } from '~/composables/providerIcons'

const props = defineProps<{
  provider: ProviderConfig
  show: boolean
}>()

const emit = defineEmits<{
  close: []
  saved: [providerId: string]
}>()

const keyValue = ref('')
const showKey = ref(false)
const remember = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)
const modalRef = ref<HTMLElement | null>(null)

const prefixWarning = computed(() => {
  if (!keyValue.value.trim()) return false
  return props.provider.keyPrefix && !keyValue.value.startsWith(props.provider.keyPrefix)
})

function save() {
  const key = keyValue.value.trim()
  if (!key) return
  const { setKey } = useApiKeys()
  setKey(props.provider.id, key, remember.value)
  keyValue.value = ''
  showKey.value = false
  remember.value = false
  emit('saved', props.provider.id)
  emit('close')
}

// Focus input when modal opens
watch(() => props.show, (val) => {
  if (val) {
    nextTick(() => inputRef.value?.focus())
  } else {
    keyValue.value = ''
    showKey.value = false
    remember.value = false
  }
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}
.modal-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 10px;
  padding: 1.75rem;
  width: 100%;
  max-width: 440px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 40px rgba(2, 254, 255, 0.03);
}
.modal-card__title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.1rem;
  font-weight: 600;
  margin-bottom: 1rem;
}
.modal-card__icon {
  width: 1.25rem;
  height: 1.25rem;
  display: flex;
  align-items: center;
}
.modal-card__icon :deep(svg) {
  width: 100%;
  height: 100%;
}
.modal-card__info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  background: rgba(2, 254, 255, 0.04);
  border: 1px solid var(--border-subtle);
  font-size: 0.8rem;
  color: var(--text-secondary);
  margin-bottom: 1rem;
}
.modal-card__info-icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  color: var(--neon-cyan-60);
}
.modal-card__info-icon :deep(svg) {
  width: 14px;
  height: 14px;
}
.modal-card__label {
  font-size: 0.82rem;
  color: var(--text-secondary);
  margin-bottom: 0.35rem;
  display: block;
}
.modal-card__input-row {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}
.modal-card__input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.85rem;
}
.modal-card__input:focus {
  outline: none;
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}
.modal-card__toggle {
  padding: 0.4rem 0.5rem;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  background: var(--bg-base);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: border-color 0.15s, color 0.15s;
}
.modal-card__toggle :deep(svg) {
  width: 18px;
  height: 18px;
}
.modal-card__toggle:hover {
  border-color: var(--border-strong);
}
.modal-card__warning {
  font-size: 0.75rem;
  color: rgba(251, 191, 36, 0.9);
  margin-bottom: 0.5rem;
}
.modal-card__warning-box {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.7rem 0.85rem;
  border-radius: 6px;
  background: rgba(251, 191, 36, 0.06);
  border: 1px solid rgba(251, 191, 36, 0.35);
  color: rgba(251, 191, 36, 0.95);
  font-size: 0.78rem;
  line-height: 1.45;
  margin-bottom: 1rem;
}
.modal-card__warning-box strong {
  font-size: 0.82rem;
}
.modal-card__warning-box p {
  margin: 0;
  color: var(--text-secondary);
}
.modal-card__warning-box p strong {
  color: rgba(251, 191, 36, 0.95);
  font-size: inherit;
}
.modal-card__checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  cursor: pointer;
  margin-top: 0.5rem;
}
.modal-card__checkbox input[type="checkbox"] {
  accent-color: var(--neon-cyan);
}
.modal-card__checkbox-hint {
  font-size: 0.72rem;
  color: var(--text-muted);
  padding-left: 1.6rem;
  margin-bottom: 0.75rem;
}
.modal-card__help {
  font-size: 0.78rem;
  color: var(--text-muted);
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  margin-bottom: 1.25rem;
  line-height: 1.5;
}
.modal-card__link {
  color: var(--neon-cyan-60);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.modal-card__link:hover {
  color: var(--neon-cyan);
}
.modal-card__footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.6rem;
}
.modal-card__btn {
  padding: 0.45rem 1rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  border: 1px solid;
}
.modal-card__btn--cancel {
  border-color: var(--border-default);
  background: transparent;
  color: var(--text-secondary);
}
.modal-card__btn--cancel:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.modal-card__btn--save {
  border-color: var(--neon-cyan-30);
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
}
.modal-card__btn--save:hover:not(:disabled) {
  background: rgba(2, 254, 255, 0.15);
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 12px var(--neon-cyan-08);
}
.modal-card__btn--save:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
