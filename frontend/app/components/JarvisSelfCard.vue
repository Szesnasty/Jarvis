<template>
  <section class="jarvis-card" aria-labelledby="jarvis-card-title">
    <header class="jarvis-card__header">
      <div class="jarvis-card__title-row">
        <!-- Mini Jarvis orb: concentric cyan rings + glowing core. Mirrors the
             main Orb.vue aesthetic at icon scale (no animation overhead). -->
        <span class="jarvis-card__icon" aria-hidden="true">
          <svg viewBox="0 0 32 32" width="32" height="32">
            <defs>
              <radialGradient id="jarvis-orb-core" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stop-color="var(--neon-cyan, #5ee7ff)" stop-opacity="0.95" />
                <stop offset="55%" stop-color="var(--neon-cyan, #5ee7ff)" stop-opacity="0.35" />
                <stop offset="100%" stop-color="var(--neon-cyan, #5ee7ff)" stop-opacity="0" />
              </radialGradient>
            </defs>
            <circle cx="16" cy="16" r="14" fill="none" stroke="currentColor" stroke-width="0.6" opacity="0.35" />
            <circle cx="16" cy="16" r="11" fill="none" stroke="currentColor" stroke-width="0.8" opacity="0.6" />
            <circle cx="16" cy="16" r="8" fill="none" stroke="currentColor" stroke-width="1" opacity="0.85" />
            <circle cx="16" cy="16" r="6" fill="url(#jarvis-orb-core)" />
          </svg>
        </span>
        <div>
          <h2 id="jarvis-card-title" class="jarvis-card__title">JARVIS</h2>
          <p class="jarvis-card__subtitle">Your assistant's core configuration</p>
        </div>
        <span class="jarvis-card__always-tag" title="JARVIS is always active">Always on</span>
      </div>
      <p class="jarvis-card__intro">
        This is Jarvis itself. Two controls let you shape how it speaks and behaves
        in <strong>every</strong> conversation. Other Specialists below add focused
        knowledge on top — JARVIS is the foundation.
      </p>
    </header>

    <!-- Override block -->
    <div class="jarvis-card__block">
      <label class="jarvis-card__check">
        <input
          type="checkbox"
          :checked="overrideEnabled"
          :disabled="loading || saving"
          @change="onToggleOverride(($event.target as HTMLInputElement).checked)"
        />
        <span class="jarvis-card__check-label">Override Jarvis's default system prompt</span>
      </label>
      <p class="jarvis-card__hint">
        When enabled, your text below <strong>fully replaces</strong> the built-in
        Jarvis personality. Leave it unchecked to keep the default behavior.
        The default is intentionally hidden — you write your own from scratch.
      </p>
      <textarea
        v-if="overrideEnabled"
        v-model="form.system_prompt"
        class="jarvis-card__textarea"
        rows="8"
        :maxlength="maxChars"
        :disabled="saving"
        placeholder="Write your own Jarvis personality here. Example:&#10;&#10;You are a concise, no-nonsense assistant. Reply in short bullet points. Never apologise. Always cite sources."
      />
      <p v-if="overrideEnabled" class="jarvis-card__counter">
        {{ form.system_prompt.length }} / {{ maxChars }}
      </p>
    </div>

    <!-- Extension block -->
    <div class="jarvis-card__block">
      <h3 class="jarvis-card__block-title">Extra behavior rules</h3>
      <p class="jarvis-card__hint">
        Always appended to whatever system prompt is in effect (default or
        overridden). Use this for small, persistent tweaks — tone, sign-offs,
        forbidden topics, preferred formats.
      </p>
      <textarea
        v-model="form.behavior_extension"
        class="jarvis-card__textarea"
        rows="5"
        :maxlength="maxChars"
        :disabled="saving"
        placeholder="Examples:&#10;- Sign every reply with —J.&#10;- Never use bullet points; reply as flowing paragraphs.&#10;- When unsure, ask one clarifying question first."
      />
      <p class="jarvis-card__counter">
        {{ form.behavior_extension.length }} / {{ maxChars }}
      </p>
    </div>

    <!-- Footer -->
    <footer class="jarvis-card__footer">
      <span v-if="error" class="jarvis-card__error" role="alert">{{ error }}</span>
      <span v-else-if="savedAt" class="jarvis-card__saved">Saved.</span>
      <button
        class="jarvis-card__save"
        :disabled="!dirty || saving || loading"
        @click="save"
      >
        {{ saving ? 'Saving…' : 'Save' }}
      </button>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { useApi } from '~/composables/useApi'
import { ApiError, type JarvisSelfConfig } from '~/types'

const api = useApi()

// Mirrors backend `JARVIS_PROMPT_MAX_CHARS` (models/schemas.py).
const maxChars = 16000

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const savedAt = ref<number | null>(null)

const form = reactive<JarvisSelfConfig>({
  system_prompt: '',
  behavior_extension: '',
})
let original: JarvisSelfConfig = { system_prompt: '', behavior_extension: '' }

// `overrideEnabled` is purely UI state. It's true if the user currently has
// (or wants to have) a custom system prompt. Unchecking it clears the field
// so the next save returns Jarvis to its built-in default.
const overrideEnabled = ref(false)

const dirty = computed(
  () =>
    form.system_prompt !== original.system_prompt ||
    form.behavior_extension !== original.behavior_extension,
)

function onToggleOverride(checked: boolean) {
  overrideEnabled.value = checked
  if (!checked) form.system_prompt = ''
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.fetchJarvisConfig()
    form.system_prompt = data.system_prompt || ''
    form.behavior_extension = data.behavior_extension || ''
    original = { ...data }
    overrideEnabled.value = form.system_prompt.length > 0
  } catch (err: unknown) {
    error.value = err instanceof ApiError ? err.message : 'Failed to load JARVIS config'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const data = await api.updateJarvisConfig({
      system_prompt: form.system_prompt,
      behavior_extension: form.behavior_extension,
    })
    form.system_prompt = data.system_prompt || ''
    form.behavior_extension = data.behavior_extension || ''
    original = { ...data }
    savedAt.value = Date.now()
  } catch (err: unknown) {
    error.value = err instanceof ApiError ? err.message : 'Failed to save JARVIS config'
  } finally {
    saving.value = false
  }
}

// Hide "Saved." after 3 s of inactivity.
watch(savedAt, () => {
  if (!savedAt.value) return
  const stamp = savedAt.value
  setTimeout(() => {
    if (savedAt.value === stamp) savedAt.value = null
  }, 3000)
})

onMounted(load)
</script>

<style scoped>
.jarvis-card {
  position: relative;
  margin-bottom: 1.75rem;
  padding: 1.25rem 1.4rem 1.1rem;
  border: 1px solid var(--neon-cyan-15);
  border-radius: 14px;
  background:
    linear-gradient(180deg, var(--neon-cyan-08) 0%, transparent 60%),
    var(--surface-elevated, rgba(255, 255, 255, 0.02));
  box-shadow: 0 0 24px var(--neon-cyan-08), 0 4px 16px rgba(0, 0, 0, 0.25);
}

.jarvis-card__header {
  margin-bottom: 1rem;
}

.jarvis-card__title-row {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  margin-bottom: 0.45rem;
}

.jarvis-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  color: var(--neon-cyan, #5ee7ff);
  filter: drop-shadow(0 0 6px var(--neon-cyan-30));
  flex-shrink: 0;
}

.jarvis-card__icon svg {
  display: block;
}

.jarvis-card__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--neon-cyan, #5ee7ff);
  text-shadow: 0 0 10px var(--neon-cyan-30);
}

.jarvis-card__subtitle {
  margin: 0.05rem 0 0;
  font-size: 0.72rem;
  color: var(--text-muted);
}

.jarvis-card__always-tag {
  margin-left: auto;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--neon-cyan-60);
  background: var(--neon-cyan-08);
  border: 1px solid var(--neon-cyan-15);
  border-radius: 999px;
  padding: 0.18rem 0.55rem;
  text-transform: uppercase;
}

.jarvis-card__intro {
  margin: 0;
  font-size: 0.78rem;
  line-height: 1.55;
  color: var(--text-secondary, var(--text-muted));
}

.jarvis-card__intro strong {
  color: var(--text-primary);
}

.jarvis-card__block {
  padding: 0.85rem 0;
  border-top: 1px solid var(--border-default);
}

.jarvis-card__block-title {
  margin: 0 0 0.3rem;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}

.jarvis-card__check {
  display: inline-flex;
  align-items: center;
  gap: 0.55rem;
  cursor: pointer;
  user-select: none;
}

.jarvis-card__check input[type='checkbox'] {
  accent-color: var(--neon-cyan, #5ee7ff);
  width: 14px;
  height: 14px;
  cursor: pointer;
}

.jarvis-card__check-label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary);
}

.jarvis-card__hint {
  margin: 0.35rem 0 0.55rem;
  font-size: 0.72rem;
  line-height: 1.55;
  color: var(--text-muted);
}

.jarvis-card__hint strong {
  color: var(--text-secondary, var(--text-primary));
}

.jarvis-card__textarea {
  width: 100%;
  box-sizing: border-box;
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--border-default);
  border-radius: 8px;
  color: var(--text-primary);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.78rem;
  line-height: 1.55;
  padding: 0.65rem 0.75rem;
  resize: vertical;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.jarvis-card__textarea:focus {
  outline: none;
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 0 2px var(--neon-cyan-08);
}

.jarvis-card__textarea:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.jarvis-card__counter {
  margin: 0.3rem 0 0;
  text-align: right;
  font-size: 0.66rem;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.jarvis-card__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
  margin-top: 0.6rem;
  padding-top: 0.85rem;
  border-top: 1px solid var(--border-default);
}

.jarvis-card__error {
  font-size: 0.74rem;
  color: var(--error, #ff7a7a);
}

.jarvis-card__saved {
  font-size: 0.74rem;
  color: var(--neon-cyan-60);
}

.jarvis-card__save {
  display: inline-flex;
  align-items: center;
  padding: 0.45rem 1.1rem;
  border: 1px solid var(--neon-cyan-30);
  border-radius: 8px;
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  cursor: pointer;
  transition: all 0.2s ease;
}

.jarvis-card__save:hover:not(:disabled) {
  background: var(--neon-cyan-15);
  box-shadow: 0 0 16px var(--neon-cyan-15);
}

.jarvis-card__save:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
