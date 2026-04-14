<template>
  <div class="wiz">
    <!-- Step indicator -->
    <div class="wiz__steps">
      <button
        v-for="s in stepLabels"
        :key="s.num"
        class="wiz__step"
        :class="{
          'wiz__step--active': step === s.num,
          'wiz__step--done': step > s.num,
        }"
        @click="goToStep(s.num)"
      >
        <span class="wiz__step-num">{{ step > s.num ? '\u2713' : s.num }}</span>
        <span class="wiz__step-label">{{ s.label }}</span>
      </button>
    </div>

    <!-- Step body -->
    <div class="wiz__body">
      <Transition :name="slideDir" mode="out-in">
        <!-- Step 1: Name + Icon -->
        <div v-if="step === 1" key="1" class="wiz__section">
          <div class="wiz__field">
            <label class="wiz__label">Name</label>
            <p class="wiz__hint">Give your specialist a clear, descriptive name</p>
            <input
              v-model="form.name"
              class="wiz__input"
              :class="{ 'wiz__input--readonly': isEditMode }"
              placeholder="e.g. Health Guide"
              :readonly="isEditMode"
              autofocus
            />
            <p v-if="isEditMode" class="wiz__hint wiz__hint--lock">Name cannot be changed after creation</p>
          </div>
          <div class="wiz__field">
            <label class="wiz__label">Icon</label>
            <p class="wiz__hint">Pick an icon for this specialist</p>
            <div class="wiz__icon-picker">
              <div class="wiz__icon-selected">
                <span class="wiz__icon-selected-emoji">{{ form.icon }}</span>
                <span class="wiz__icon-selected-label">Selected</span>
              </div>
              <div class="wiz__icon-grid">
                <button
                  v-for="emoji in iconOptions"
                  :key="emoji"
                  type="button"
                  class="wiz__icon-option"
                  :class="{ 'wiz__icon-option--active': form.icon === emoji }"
                  @click="form.icon = emoji"
                >
                  {{ emoji }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 2: Role -->
        <div v-else-if="step === 2" key="2" class="wiz__section">
          <div class="wiz__field">
            <label class="wiz__label">Role description</label>
            <p class="wiz__hint">Describe this specialist's expertise and purpose</p>
            <textarea
              v-model="form.role"
              class="wiz__textarea"
              placeholder="You are a health advisor who helps me interpret lab results, track supplements, and optimize sleep..."
            />
          </div>
        </div>

        <!-- Step 3: Knowledge Sources -->
        <div v-else-if="step === 3" key="3" class="wiz__section">
          <div class="wiz__field">
            <label class="wiz__label">Knowledge Sources</label>
            <p class="wiz__hint">
              A dedicated folder <code class="wiz__code">memory/specialists/{{ slugifiedName || '{id}' }}/</code>
              will be created automatically. You can also add files now or after creation.
            </p>

            <!-- Drop zone for staging files -->
            <div
              class="wiz__dropzone"
              :class="{ 'wiz__dropzone--dragover': isDragOver }"
              @dragover.prevent="isDragOver = true"
              @dragleave.prevent="isDragOver = false"
              @drop.prevent="handleStageDrop"
            >
              <div class="wiz__drop-content">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                  <polyline points="17 8 12 3 7 8"/>
                  <line x1="12" y1="3" x2="12" y2="15"/>
                </svg>
                <span>Drop files to stage for upload</span>
                <button class="wiz__browse-link" type="button" @click="stageFileInput?.click()">
                  or browse
                </button>
              </div>
              <input
                ref="stageFileInput"
                type="file"
                accept=".md,.txt,.pdf,.csv,.json"
                multiple
                style="display: none"
                @change="handleStageSelect"
              />
            </div>

            <!-- Staged files preview -->
            <div v-if="stagedFiles.length" class="wiz__staged">
              <div v-for="(f, i) in stagedFiles" :key="f.name + i" class="wiz__staged-file">
                <span class="wiz__staged-name">{{ f.name }}</span>
                <span class="wiz__staged-size">{{ formatSize(f.size) }}</span>
                <button class="wiz__staged-remove" @click="stagedFiles.splice(i, 1)">&times;</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Step 4: Style -->
        <div v-else-if="step === 4" key="4" class="wiz__section">
          <div class="wiz__field">
            <label class="wiz__label">Response Style</label>
            <p class="wiz__hint">How should this specialist communicate?</p>
          </div>
          <div class="wiz__field-row">
            <div class="wiz__field wiz__field--half">
              <label class="wiz__label wiz__label--small">Tone</label>
              <input v-model="form.style.tone" class="wiz__input" placeholder="e.g. calm, supportive" />
            </div>
            <div class="wiz__field wiz__field--half">
              <label class="wiz__label wiz__label--small">Format</label>
              <input v-model="form.style.format" class="wiz__input" placeholder="e.g. checklist, prose" />
            </div>
          </div>
          <div class="wiz__field">
            <label class="wiz__label wiz__label--small">Length</label>
            <input v-model="form.style.length" class="wiz__input" placeholder="e.g. concise, detailed" />
          </div>

          <!-- Default model -->
          <div class="wiz__field wiz__field--model">
            <label class="wiz__label">Default Model</label>
            <p class="wiz__hint">Which model should this specialist use? Leave on "Use global" to follow the chat selector.</p>
            <div class="wiz__model-options">
              <button
                type="button"
                class="wiz__model-option"
                :class="{ 'wiz__model-option--active': !form.default_model }"
                @click="form.default_model = null"
              >
                <span class="wiz__model-option-label">Use global default</span>
              </button>
              <template v-for="provider in configuredProviders()" :key="provider.id">
                <button
                  v-for="model in MODEL_CATALOG[provider.id]"
                  :key="model.id"
                  type="button"
                  class="wiz__model-option"
                  :class="{ 'wiz__model-option--active': form.default_model?.provider === provider.id && form.default_model?.model === model.id }"
                  @click="form.default_model = { provider: provider.id, model: model.id }"
                >
                  <span class="wiz__model-option-icon" v-html="provider.icon" />
                  <span class="wiz__model-option-label">{{ model.label }}</span>
                  <span class="wiz__model-option-cost" :class="'wiz__cost--' + model.cost">{{ model.cost === 1 ? '$' : model.cost === 2 ? '$$' : '$$$' }}</span>
                </button>
              </template>
            </div>
          </div>
        </div>

        <!-- Step 5: Rules -->
        <div v-else-if="step === 5" key="5" class="wiz__section">
          <div class="wiz__field">
            <label class="wiz__label">Rules</label>
            <p class="wiz__hint">Constraints the specialist must always follow (one per line)</p>
            <textarea
              v-model="rulesText"
              class="wiz__textarea"
              placeholder="Never diagnose conditions&#10;Always reference user notes first&#10;Keep responses under 200 words"
            />
          </div>
        </div>

        <!-- Step 6: Tools -->
        <div v-else-if="step === 6" key="6" class="wiz__section">
          <div class="wiz__field">
            <label class="wiz__label">Allowed Tools</label>
            <p class="wiz__hint">Leave all unchecked to allow every tool</p>
            <div class="wiz__tools-grid">
              <label
                v-for="tool in availableTools"
                :key="tool.id"
                class="wiz__tool"
                :class="{ 'wiz__tool--checked': form.tools.includes(tool.id) }"
                :title="tool.desc"
              >
                <input type="checkbox" :value="tool.id" v-model="form.tools" class="wiz__tool-input" />
                <span class="wiz__tool-name">{{ tool.id }}</span>
                <span class="wiz__tool-tooltip">{{ tool.desc }}</span>
              </label>
            </div>
          </div>
        </div>

        <!-- Step 7: Review -->
        <div v-else-if="step === 7" key="7" class="wiz__section">
          <div class="wiz__review">
            <div class="wiz__review-header">
              <span class="wiz__review-icon">{{ form.icon }}</span>
              <div>
                <h3 class="wiz__review-name">{{ form.name }}</h3>
                <p class="wiz__review-role">{{ form.role || 'No role set' }}</p>
              </div>
            </div>
            <div class="wiz__review-grid">
              <div class="wiz__review-stat">
                <span class="wiz__review-stat-val">{{ stagedFiles.length }}</span>
                <span class="wiz__review-stat-label">staged files</span>
              </div>
              <div class="wiz__review-stat">
                <span class="wiz__review-stat-val">{{ form.sources.length }}</span>
                <span class="wiz__review-stat-label">source folders</span>
              </div>
              <div class="wiz__review-stat">
                <span class="wiz__review-stat-val">{{ form.rules.length }}</span>
                <span class="wiz__review-stat-label">rules</span>
              </div>
              <div class="wiz__review-stat">
                <span class="wiz__review-stat-val">{{ form.tools.length || 'All' }}</span>
                <span class="wiz__review-stat-label">tools</span>
              </div>
              <div class="wiz__review-stat">
                <span class="wiz__review-stat-val">{{ form.default_model ? getModelLabel(form.default_model.provider, form.default_model.model) : 'Global' }}</span>
                <span class="wiz__review-stat-label">model</span>
              </div>
            </div>
            <p v-if="stagedFiles.length && !isEditMode" class="wiz__review-note">
              Files will be uploaded after the specialist is created.
            </p>
            <p v-if="stagedFiles.length && isEditMode" class="wiz__review-note">
              New files will be uploaded after saving.
            </p>
          </div>
        </div>
      </Transition>
    </div>

    <!-- Navigation -->
    <div class="wiz__nav">
      <button class="wiz__cancel-btn" @click="$emit('cancel')">Cancel</button>
      <div class="wiz__nav-right">
        <button v-if="step > 1" class="wiz__back-btn" @click="prev">Back</button>
        <button
          v-if="step < 7"
          class="wiz__next-btn"
          :disabled="!canProceed"
          @click="next"
        >
          Next
        </button>
        <button
          v-else
          class="wiz__submit-btn"
          :disabled="!canProceed || submitting"
          @click="submit"
        >
          <span v-if="submitting" class="wiz__spinner" />
          <span v-else>{{ isEditMode ? 'Save Changes' : 'Create Specialist' }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import type { SpecialistDetail } from '~/types'
import { useApiKeys, MODEL_CATALOG, type ModelInfo } from '~/composables/useApiKeys'

const { configuredProviders, providers: allProviders } = useApiKeys()

const props = defineProps<{
  initialData?: SpecialistDetail | null
}>()

const emit = defineEmits<{
  save: [data: Record<string, unknown>, stagedFiles: File[]]
  cancel: []
}>()

const isEditMode = computed(() => !!props.initialData)

const step = ref(1)
const slideDir = ref('slide-left')
const submitting = ref(false)
const isDragOver = ref(false)
const stageFileInput = ref<HTMLInputElement | null>(null)
const stagedFiles = ref<File[]>([])

const form = reactive({
  name: '',
  icon: '\u{1F916}',
  role: '',
  sources: [] as string[],
  style: { tone: '', format: '', length: '' },
  rules: [] as string[],
  tools: [] as string[],
  examples: [] as { user: string; assistant: string }[],
  default_model: null as { provider: string; model: string } | null,
})

const sourcesText = ref('')
const rulesText = ref('')

// Pre-fill form when editing
onMounted(() => {
  if (props.initialData) {
    const d = props.initialData
    form.name = d.name
    form.icon = d.icon || '\u{1F916}'
    form.role = d.role || ''
    form.sources = [...(d.sources || [])]
    form.style = {
      tone: d.style?.tone || '',
      format: d.style?.format || '',
      length: d.style?.length || '',
    }
    form.rules = [...(d.rules || [])]
    form.tools = [...(d.tools || [])]
    form.examples = [...(d.examples || [])]
    form.default_model = d.default_model ? { ...d.default_model } : null
    sourcesText.value = form.sources.join('\n')
    rulesText.value = form.rules.join('\n')
  }
})

watch(sourcesText, (val) => {
  form.sources = val.split('\n').map(s => s.trim()).filter(Boolean)
})

watch(rulesText, (val) => {
  form.rules = val.split('\n').map(s => s.trim()).filter(Boolean)
})

const slugifiedName = computed(() => {
  return form.name.trim()
    ? form.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
    : ''
})

const iconOptions = [
  // People & roles
  '\u{1F916}', '\u{1F9D1}\u200D\u{1F4BB}', '\u{1F468}\u200D\u{1F52C}', '\u{1F469}\u200D\u{1F3EB}', '\u{1F9D1}\u200D\u{1F3A8}', '\u{1F468}\u200D\u{1F527}',
  // Knowledge & learning
  '\u{1F4DA}', '\u{1F4D6}', '\u{1F9E0}', '\u{1F393}', '\u{1F4DD}', '\u270D\uFE0F',
  // Health & wellness
  '\u{1F3E5}', '\u{1F489}', '\u{1F48A}', '\u{1F34E}', '\u{1F9D8}', '\u{1F6B4}',
  // Planning & productivity
  '\u{1F4C5}', '\u{1F4CB}', '\u{1F3AF}', '\u{1F680}', '\u26A1', '\u{1F4A1}',
  // Finance & business
  '\u{1F4B0}', '\u{1F4C8}', '\u{1F4BC}', '\u{1F3E6}', '\u{1F4B3}', '\u{1F4CA}',
  // Travel & places
  '\u2708\uFE0F', '\u{1F30D}', '\u{1F5FA}\uFE0F', '\u{1F3D6}\uFE0F', '\u{1F697}', '\u{1F3D4}\uFE0F',
  // Nature & science
  '\u{1F52C}', '\u{1F331}', '\u{1F30E}', '\u2697\uFE0F', '\u{1F9EA}', '\u{1F52D}',
  // Creative & media
  '\u{1F3A8}', '\u{1F3B5}', '\u{1F4F7}', '\u{1F3AC}', '\u{1F58B}\uFE0F', '\u{1F3AD}',
  // Tech & tools
  '\u{1F4BB}', '\u{1F5A5}\uFE0F', '\u2699\uFE0F', '\u{1F50C}', '\u{1F6E0}\uFE0F', '\u{1F50D}',
  // Misc
  '\u{1F3C6}', '\u2764\uFE0F', '\u{1F30C}', '\u{1F525}', '\u{1F48E}', '\u{1F308}',
]

const availableTools = [
  { id: 'search_notes', desc: 'Search your memory by keyword, tag, folder, or date. Lets the specialist find relevant notes to answer questions or build context.' },
  { id: 'read_note', desc: 'Open and read a specific note in full. Used when the specialist needs the complete content of a file, not just search snippets.' },
  { id: 'write_note', desc: 'Create a new note or overwrite an existing one. Enables the specialist to save plans, summaries, or organized outputs to your memory.' },
  { id: 'append_note', desc: 'Add content to the end of an existing note without replacing it. Great for logs, journals, or incremental updates.' },
  { id: 'create_plan', desc: 'Generate a structured plan with steps and timelines. The specialist can break down goals into actionable checklists.' },
  { id: 'update_plan', desc: 'Modify an existing plan — mark steps done, add new ones, or adjust priorities. Keeps your plans alive and up to date.' },
  { id: 'summarize_context', desc: 'Condense long notes or multiple sources into a brief summary. Saves tokens and helps the specialist focus on what matters.' },
  { id: 'save_preference', desc: 'Remember a personal rule or preference (e.g. "always respond in Polish"). Stored in memory so it persists across conversations.' },
  { id: 'query_graph', desc: 'Explore your knowledge graph — find connections between people, topics, projects, and notes that simple search might miss.' },
]

const stepLabels = [
  { num: 1, label: 'Name' },
  { num: 2, label: 'Role' },
  { num: 3, label: 'Knowledge' },
  { num: 4, label: 'Style' },
  { num: 5, label: 'Rules' },
  { num: 6, label: 'Tools' },
  { num: 7, label: 'Review' },
]

const canProceed = computed(() => {
  if (step.value === 1) return form.name.trim().length > 0
  return true
})

function goToStep(target: number) {
  if (target < step.value || canProceed.value) {
    slideDir.value = target > step.value ? 'slide-left' : 'slide-right'
    step.value = target
  }
}

function next() {
  if (canProceed.value && step.value < 7) {
    slideDir.value = 'slide-left'
    step.value++
  }
}

function prev() {
  if (step.value > 1) {
    slideDir.value = 'slide-right'
    step.value--
  }
}

function handleStageDrop(event: DragEvent) {
  isDragOver.value = false
  const dropped = event.dataTransfer?.files
  if (dropped) {
    stagedFiles.value.push(...Array.from(dropped))
  }
}

function handleStageSelect(event: Event) {
  const input = event.target as HTMLInputElement
  if (input.files) {
    stagedFiles.value.push(...Array.from(input.files))
    input.value = ''
  }
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function getModelLabel(provider: string, model: string): string {
  const catalog = MODEL_CATALOG[provider]
  return catalog?.find((m: ModelInfo) => m.id === model)?.label ?? model
}

function submit() {
  if (!form.name.trim()) return
  submitting.value = true
  emit('save', { ...form }, [...stagedFiles.value])
}

function resetSubmitting() {
  submitting.value = false
}

defineExpose({ resetSubmitting })
</script>

<style scoped>
.wiz {
  width: 100%;
}

/* --- Steps indicator --- */
.wiz__steps {
  display: flex;
  gap: 0.15rem;
  margin-bottom: 1.75rem;
  overflow-x: auto;
  width: 100%;
}

.wiz__step {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.35rem 0.6rem;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--text-muted);
  font-size: 0.72rem;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.wiz__step:hover {
  color: var(--text-secondary);
  background: var(--bg-hover);
}

.wiz__step--active {
  color: var(--neon-cyan);
  background: var(--neon-cyan-08);
  border-color: var(--neon-cyan-15);
}

.wiz__step--done {
  color: var(--neon-green);
}

.wiz__step-num {
  font-weight: 700;
  font-size: 0.68rem;
  font-variant-numeric: tabular-nums;
}

.wiz__step-label {
  font-weight: 500;
}

/* --- Body --- */
.wiz__body {
  position: relative;
  margin-bottom: 1.75rem;
  width: 100%;
}

.wiz__section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  width: 100%;
}

.wiz__field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  width: 100%;
  min-width: 0;
}

.wiz__field-row {
  display: flex;
  gap: 0.75rem;
}

.wiz__field--half {
  flex: 1;
}

.wiz__label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-primary);
}

.wiz__label--small {
  font-size: 0.78rem;
  font-weight: 500;
}

.wiz__hint {
  font-size: 0.72rem;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.4;
}

.wiz__code {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.68rem;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
  color: var(--neon-cyan-60);
}

.wiz__input {
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-base);
  color: var(--text-primary);
  font-size: 0.88rem;
  transition: all 0.2s;
  box-sizing: border-box;
}

.wiz__input:focus {
  outline: none;
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 0 2px var(--neon-cyan-08), 0 0 12px var(--neon-cyan-08);
}

.wiz__input--readonly {
  opacity: 0.5;
  cursor: not-allowed;
  border-style: dashed;
}

.wiz__hint--lock {
  font-size: 0.68rem;
  color: var(--text-muted);
  opacity: 0.7;
  font-style: italic;
}

/* --- Icon Picker --- */
.wiz__icon-picker {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.25rem;
}

.wiz__icon-selected {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.5rem 0.75rem;
  border-radius: 8px;
  background: var(--neon-cyan-08);
  border: 1px solid var(--neon-cyan-15);
  width: fit-content;
}

.wiz__icon-selected-emoji {
  font-size: 2rem;
  line-height: 1;
}

.wiz__icon-selected-label {
  font-size: 0.68rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--neon-cyan-60);
}

.wiz__icon-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(38px, 1fr));
  gap: 4px;
  padding: 0.5rem;
  border-radius: 8px;
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
  max-height: 180px;
  overflow-y: auto;
}

.wiz__icon-option {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  font-size: 1.25rem;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  transition: all 0.15s ease;
  line-height: 1;
  padding: 0;
}

.wiz__icon-option:hover {
  background: var(--bg-hover);
  border-color: var(--border-default);
  transform: scale(1.15);
}

.wiz__icon-option--active {
  background: var(--neon-cyan-08);
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 10px var(--neon-cyan-08);
  transform: scale(1.1);
}

.wiz__icon-option--active:hover {
  transform: scale(1.18);
}


.wiz__textarea {
  width: 100%;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border-default);
  border-radius: 6px;
  background: var(--bg-base);
  color: var(--text-primary);
  font-size: 0.85rem;
  min-height: 120px;
  resize: vertical;
  box-sizing: border-box;
  line-height: 1.5;
  transition: all 0.2s;
}

.wiz__textarea:focus {
  outline: none;
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 0 2px var(--neon-cyan-08);
}

.wiz__textarea--small {
  min-height: 72px;
  font-size: 0.78rem;
  margin-top: 0.5rem;
}

/* --- Dropzone (Step 3) --- */
.wiz__dropzone {
  border: 1.5px dashed var(--border-default);
  border-radius: 8px;
  padding: 1.25rem;
  text-align: center;
  transition: all 0.25s;
  margin-top: 0.25rem;
}

.wiz__dropzone--dragover {
  border-color: var(--neon-cyan-60);
  border-style: solid;
  background: var(--neon-cyan-08);
  box-shadow: inset 0 0 30px var(--neon-cyan-08);
}

.wiz__drop-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  color: var(--text-muted);
  font-size: 0.8rem;
}

.wiz__drop-content svg {
  opacity: 0.5;
}

.wiz__dropzone--dragover .wiz__drop-content svg {
  opacity: 1;
  color: var(--neon-cyan);
}

.wiz__browse-link {
  background: none;
  border: none;
  color: var(--neon-cyan-60);
  font-size: 0.78rem;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.wiz__browse-link:hover {
  color: var(--neon-cyan);
}

/* Staged files */
.wiz__staged {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 0.5rem;
}

.wiz__staged-file {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.35rem 0.5rem;
  border-radius: 4px;
  background: var(--bg-elevated);
  font-size: 0.78rem;
}

.wiz__staged-name {
  flex: 1;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wiz__staged-size {
  color: var(--text-muted);
  font-size: 0.68rem;
  font-variant-numeric: tabular-nums;
}

.wiz__staged-remove {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 1rem;
  padding: 0 0.15rem;
  line-height: 1;
}

.wiz__staged-remove:hover {
  color: var(--neon-red);
}


/* --- Tools grid (Step 6) --- */
.wiz__tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 0.35rem;
  margin-top: 0.25rem;
}

.wiz__tool {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.4rem 0.55rem;
  border: 1px solid var(--border-subtle);
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.15s;
  font-size: 0.75rem;
}

.wiz__tool:hover {
  border-color: var(--border-default);
  background: var(--bg-hover);
}

.wiz__tool--checked {
  border-color: var(--neon-cyan-30);
  background: var(--neon-cyan-08);
}

.wiz__tool-input {
  display: none;
}

.wiz__tool-name {
  color: var(--text-secondary);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.7rem;
}

.wiz__tool--checked .wiz__tool-name {
  color: var(--neon-cyan);
}

/* Hover tooltip */
.wiz__tool-tooltip {
  display: none;
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  width: max-content;
  max-width: 280px;
  padding: 0.55rem 0.7rem;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 0.72rem;
  line-height: 1.45;
  font-family: inherit;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  z-index: 100;
  pointer-events: none;
  white-space: normal;
}

.wiz__tool-tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 6px solid transparent;
  border-top-color: var(--border-default);
}

.wiz__tool:hover .wiz__tool-tooltip {
  display: block;
}

/* --- Model picker (Step 4) --- */
.wiz__field--model {
  margin-top: 0.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--border-subtle);
}

.wiz__model-options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.25rem;
}

.wiz__model-option {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.4rem 0.65rem;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 0.8rem;
  transition: all 0.15s;
}

.wiz__model-option:hover {
  border-color: var(--neon-cyan-30);
  background: var(--bg-elevated);
}

.wiz__model-option--active {
  border-color: var(--neon-cyan);
  background: var(--neon-cyan-08);
  color: var(--neon-cyan);
}

.wiz__model-option-icon {
  width: 14px;
  height: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.wiz__model-option-icon :deep(svg) {
  width: 12px;
  height: 12px;
}

.wiz__model-option-cost {
  font-size: 0.65rem;
  font-weight: 600;
  padding: 0.05rem 0.25rem;
  border-radius: 3px;
  line-height: 1;
}

.wiz__cost--1 {
  color: rgba(74, 222, 128, 0.9);
  background: rgba(74, 222, 128, 0.1);
}

.wiz__cost--2 {
  color: rgba(251, 191, 36, 0.9);
  background: rgba(251, 191, 36, 0.1);
}

.wiz__cost--3 {
  color: rgba(251, 146, 60, 0.9);
  background: rgba(251, 146, 60, 0.1);
}

/* --- Review (Step 7) --- */
.wiz__review {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.wiz__review-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  border-radius: 8px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
}

.wiz__review-icon {
  font-size: 2rem;
}

.wiz__review-name {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.wiz__review-role {
  margin: 0.15rem 0 0;
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.3;
}

.wiz__review-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5rem;
}

.wiz__review-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.6rem;
  border-radius: 6px;
  background: var(--bg-base);
  border: 1px solid var(--border-subtle);
}

.wiz__review-stat-val {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--neon-cyan);
  font-variant-numeric: tabular-nums;
}

.wiz__review-stat-label {
  font-size: 0.62rem;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-top: 0.15rem;
}

.wiz__review-note {
  font-size: 0.72rem;
  color: var(--text-muted);
  text-align: center;
  margin: 0;
}

/* --- Nav --- */
.wiz__nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 1rem;
  border-top: 1px solid var(--border-subtle);
  width: 100%;
}

.wiz__nav-right {
  display: flex;
  gap: 0.5rem;
}

.wiz__cancel-btn,
.wiz__back-btn,
.wiz__next-btn,
.wiz__submit-btn {
  padding: 0.5rem 1.25rem;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.wiz__cancel-btn {
  background: transparent;
  border-color: var(--border-subtle);
  color: var(--text-muted);
}

.wiz__cancel-btn:hover {
  color: var(--text-secondary);
  border-color: var(--border-default);
}

.wiz__back-btn {
  background: transparent;
  border-color: var(--border-default);
  color: var(--text-secondary);
}

.wiz__back-btn:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.wiz__next-btn {
  background: var(--neon-cyan-08);
  border-color: var(--neon-cyan-30);
  color: var(--neon-cyan);
}

.wiz__next-btn:hover:not(:disabled) {
  background: var(--neon-cyan-15);
  border-color: var(--neon-cyan-60);
  box-shadow: 0 0 12px var(--neon-cyan-08);
  text-shadow: 0 0 6px var(--neon-cyan-30);
}

.wiz__next-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.wiz__submit-btn {
  background: var(--neon-cyan-30);
  border-color: var(--neon-cyan-60);
  color: var(--bg-deep);
  font-weight: 600;
}

.wiz__submit-btn:hover:not(:disabled) {
  background: var(--neon-cyan-60);
  box-shadow: 0 0 20px var(--neon-cyan-15);
}

.wiz__submit-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* --- Spinner --- */
.wiz__spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid var(--bg-deep);
  border-top-color: transparent;
  border-radius: 50%;
  animation: wiz-spin 0.6s linear infinite;
}

@keyframes wiz-spin {
  to { transform: rotate(360deg); }
}

/* --- Slide transitions (out-in mode: no overlap) --- */
.slide-left-leave-active,
.slide-right-leave-active {
  transition: opacity 0.1s ease;
}

.slide-left-enter-active,
.slide-right-enter-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.slide-left-enter-from {
  opacity: 0;
  transform: translateX(16px);
}

.slide-right-enter-from {
  opacity: 0;
  transform: translateX(-16px);
}

.slide-left-leave-to,
.slide-right-leave-to {
  opacity: 0;
}

/* --- Mobile --- */
@media (max-width: 480px) {
  .wiz__steps {
    gap: 0.1rem;
    margin-bottom: 1.25rem;
    -webkit-overflow-scrolling: touch;
  }

  .wiz__step {
    padding: 0.3rem 0.45rem;
    font-size: 0.65rem;
  }

  .wiz__step-label {
    display: none;
  }

  .wiz__field-row {
    flex-direction: column;
    gap: 0.75rem;
  }

  .wiz__icon-grid {
    grid-template-columns: repeat(auto-fill, minmax(34px, 1fr));
    max-height: 150px;
  }

  .wiz__icon-option {
    width: 34px;
    height: 34px;
    font-size: 1.1rem;
  }

  .wiz__tools-grid {
    grid-template-columns: 1fr;
  }

  .wiz__review-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .wiz__nav {
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .wiz__cancel-btn,
  .wiz__back-btn,
  .wiz__next-btn,
  .wiz__submit-btn {
    padding: 0.5rem 1rem;
    font-size: 0.78rem;
  }
}
</style>
