<template>
  <div class="specialist-wizard">
    <div class="specialist-wizard__steps">
      <span
        v-for="s in stepLabels"
        :key="s.num"
        class="specialist-wizard__step"
        :class="{ 'specialist-wizard__step--active': step === s.num }"
      >
        {{ s.num }}. {{ s.label }}
      </span>
    </div>

    <div class="specialist-wizard__body">
      <!-- Step 1: Name + Icon -->
      <div v-if="step === 1" class="specialist-wizard__section">
        <label class="specialist-wizard__label">Name</label>
        <input v-model="form.name" class="specialist-wizard__input" placeholder="e.g. Health Guide" />
        <label class="specialist-wizard__label">Icon (emoji)</label>
        <input v-model="form.icon" class="specialist-wizard__input" placeholder="�" />
      </div>

      <!-- Step 2: Role -->
      <div v-if="step === 2" class="specialist-wizard__section">
        <label class="specialist-wizard__label">Role description</label>
        <textarea v-model="form.role" class="specialist-wizard__textarea" placeholder="Describe what this specialist does..." />
      </div>

      <!-- Step 3: Sources -->
      <div v-if="step === 3" class="specialist-wizard__section">
        <label class="specialist-wizard__label">Source folders (one per line)</label>
        <textarea v-model="sourcesText" class="specialist-wizard__textarea" placeholder="memory/knowledge/health/&#10;memory/daily/" />
      </div>

      <!-- Step 4: Style -->
      <div v-if="step === 4" class="specialist-wizard__section">
        <label class="specialist-wizard__label">Tone</label>
        <input v-model="form.style.tone" class="specialist-wizard__input" placeholder="e.g. calm, supportive" />
        <label class="specialist-wizard__label">Format</label>
        <input v-model="form.style.format" class="specialist-wizard__input" placeholder="e.g. checklist, prose" />
        <label class="specialist-wizard__label">Length</label>
        <input v-model="form.style.length" class="specialist-wizard__input" placeholder="e.g. concise, detailed" />
      </div>

      <!-- Step 5: Rules -->
      <div v-if="step === 5" class="specialist-wizard__section">
        <label class="specialist-wizard__label">Rules (one per line)</label>
        <textarea v-model="rulesText" class="specialist-wizard__textarea" placeholder="Never diagnose conditions&#10;Always reference user notes first" />
      </div>

      <!-- Step 6: Tools -->
      <div v-if="step === 6" class="specialist-wizard__section">
        <label class="specialist-wizard__label">Allowed tools</label>
        <div v-for="tool in availableTools" :key="tool" class="specialist-wizard__checkbox">
          <input type="checkbox" :value="tool" v-model="form.tools" :id="'tool-' + tool" />
          <label :for="'tool-' + tool">{{ tool }}</label>
        </div>
      </div>

      <!-- Step 7: Review -->
      <div v-if="step === 7" class="specialist-wizard__section specialist-wizard__review">
        <p><strong>{{ form.icon }} {{ form.name }}</strong></p>
        <p>{{ form.role }}</p>
        <p>Sources: {{ form.sources.length }}</p>
        <p>Rules: {{ form.rules.length }}</p>
        <p>Tools: {{ form.tools.length }}</p>
      </div>
    </div>

    <div class="specialist-wizard__nav">
      <button v-if="step > 1" class="specialist-wizard__back-btn" @click="step--">Back</button>
      <span v-else />
      <button v-if="step < 7" class="specialist-wizard__next-btn" @click="nextStep" :disabled="!canProceed">
        Next
      </button>
      <button v-else class="specialist-wizard__submit-btn" @click="submit" :disabled="!canProceed">
        Create Specialist
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'

const emit = defineEmits<{
  save: [data: Record<string, unknown>]
  cancel: []
}>()

const step = ref(1)

const form = reactive({
  name: '',
  icon: '�',
  role: '',
  sources: [] as string[],
  style: { tone: '', format: '', length: '' },
  rules: [] as string[],
  tools: [] as string[],
  examples: [] as { user: string; assistant: string }[],
})

const sourcesText = ref('')
const rulesText = ref('')

watch(sourcesText, (val) => {
  form.sources = val.split('\n').map(s => s.trim()).filter(Boolean)
})

watch(rulesText, (val) => {
  form.rules = val.split('\n').map(s => s.trim()).filter(Boolean)
})

const availableTools = [
  'search_notes',
  'read_note',
  'write_note',
  'append_note',
  'create_plan',
  'update_plan',
  'summarize_context',
  'save_preference',
  'query_graph',
]

const stepLabels = [
  { num: 1, label: 'Name' },
  { num: 2, label: 'Role' },
  { num: 3, label: 'Sources' },
  { num: 4, label: 'Style' },
  { num: 5, label: 'Rules' },
  { num: 6, label: 'Tools' },
  { num: 7, label: 'Review' },
]

const canProceed = computed(() => {
  if (step.value === 1) return form.name.trim().length > 0
  return true
})

function nextStep() {
  if (canProceed.value && step.value < 7) {
    step.value++
  }
}

function submit() {
  emit('save', { ...form })
}
</script>

<style scoped>
.specialist-wizard {
  max-width: 600px;
  margin: 0 auto;
}
.specialist-wizard__steps {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}
.specialist-wizard__step {
  font-size: 0.8rem;
  opacity: 0.5;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}
.specialist-wizard__step--active {
  opacity: 1;
  background: var(--neon-cyan-30);
  color: var(--neon-cyan);
  text-shadow: 0 0 6px var(--neon-cyan-30);
}
.specialist-wizard__section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.specialist-wizard__label {
  font-size: 0.9rem;
  font-weight: 500;
}
.specialist-wizard__input {
  padding: 0.5rem;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  background: var(--bg-base);
  color: inherit;
  font-size: 1rem;
}
.specialist-wizard__input:focus {
  outline: none;
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 10px var(--neon-cyan-08);
}
.specialist-wizard__textarea {
  padding: 0.5rem;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  background: var(--bg-base);
  color: inherit;
  font-size: 1rem;
  min-height: 120px;
  resize: vertical;
}
.specialist-wizard__checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.specialist-wizard__nav {
  display: flex;
  justify-content: space-between;
  margin-top: 1.5rem;
}
.specialist-wizard__back-btn,
.specialist-wizard__next-btn,
.specialist-wizard__submit-btn {
  padding: 0.5rem 1.5rem;
  border: 1px solid var(--neon-cyan-30);
  border-radius: 4px;
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}
.specialist-wizard__next-btn:hover,
.specialist-wizard__submit-btn:hover {
  background: rgba(2, 254, 255, 0.15);
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 12px var(--neon-cyan-08);
  text-shadow: 0 0 6px var(--neon-cyan-30);
}
.specialist-wizard__submit-btn {
  background: var(--neon-cyan-30);
  color: var(--neon-cyan);
}
.specialist-wizard__review p {
  margin: 0.25rem 0;
}
</style>
