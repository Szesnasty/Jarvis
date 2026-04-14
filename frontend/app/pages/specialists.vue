<template>
  <div class="spec-page">
    <!-- Header -->
    <header class="spec-page__header">
      <div class="spec-page__header-top">
        <div class="spec-page__title-group">
          <h1 class="spec-page__title">Specialists</h1>
          <span v-if="specialists.length" class="spec-page__count">{{ specialists.length }}</span>
        </div>
        <button
          v-if="!showWizard"
          class="spec-page__create-btn"
          @click="editingSpec = null; showWizard = true"
        >
          <span class="spec-page__create-icon">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="12" y1="5" x2="12" y2="19"/>
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
          </span>
          New Specialist
        </button>
      </div>
      <p class="spec-page__subtitle">Custom knowledge profiles for focused expertise</p>
      <div class="spec-page__divider" />
    </header>

    <!-- Empty state -->
    <div v-if="specialists.length === 0 && !showWizard" class="spec-page__empty">
      <div class="spec-page__empty-graphic">
        <div class="spec-page__empty-ring" />
        <div class="spec-page__empty-ring spec-page__empty-ring--outer" />
        <svg class="spec-page__empty-svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
          <circle cx="9" cy="7" r="4"/>
          <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
          <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
        </svg>
      </div>
      <p class="spec-page__empty-text">No specialists yet</p>
      <p class="spec-page__empty-hint">Create a specialist to give Jarvis focused knowledge and behavior</p>
      <button class="spec-page__empty-btn" @click="editingSpec = null; showWizard = true">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="5" x2="12" y2="19"/>
          <line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
        Create your first specialist
      </button>
    </div>

    <!-- Card grid -->
    <TransitionGroup v-if="!showWizard && specialists.length" name="card-list" tag="div" class="spec-page__grid">
      <SpecialistCard
        v-for="spec in specialists"
        :key="spec.id"
        :specialist="spec"
        :active="activeSpecialist?.id === spec.id"
        :expanded="expandedId === spec.id"
        @activate="handleActivate(spec.id)"
        @edit="handleEdit(spec.id)"
        @delete="handleDeleteRequest(spec)"
        @toggle-expand="toggleExpand(spec.id)"
      />
    </TransitionGroup>

    <!-- Wizard error -->
    <Transition name="fade">
      <div v-if="showWizard && saveError" class="spec-page__save-error" @click="saveError = ''">{{ saveError }}</div>
    </Transition>

    <!-- Wizard -->
    <Transition name="wizard-slide">
      <SpecialistWizard
        v-if="showWizard"
        ref="wizardRef"
        :initial-data="editingSpec"
        @save="handleSave"
        @cancel="() => { showWizard = false; editingSpec = null; saveError = '' }"
      />
    </Transition>

    <!-- Delete confirmation -->
    <ConfirmDialog
      :visible="!!deletingSpec"
      :title="`Delete ${deletingSpec?.name || 'specialist'}?`"
      message="This specialist and its knowledge files will be moved to trash."
      confirm-label="Delete"
      @confirm="confirmDelete"
      @cancel="deletingSpec = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { SpecialistSummary, SpecialistDetail } from '~/types'
import { useSpecialists } from '~/composables/useSpecialists'
import { useApi } from '~/composables/useApi'
import { ApiError } from '~/types'
import SpecialistWizard from '~/components/SpecialistWizard.vue'

const {
  specialists,
  activeSpecialist,
  expandedId,
  load,
  activate,
  deactivate,
  update,
  remove,
  toggleExpand,
  uploadFile,
} = useSpecialists()

const api = useApi()
const showWizard = ref(false)
const editingSpec = ref<SpecialistDetail | null>(null)
const deletingSpec = ref<SpecialistSummary | null>(null)
const saveError = ref('')
const wizardRef = ref<InstanceType<typeof SpecialistWizard> | null>(null)

onMounted(() => {
  load()
})

async function handleActivate(id: string) {
  if (activeSpecialist.value?.id === id) {
    await deactivate()
  } else {
    await activate(id)
  }
}

async function handleEdit(id: string) {
  try {
    editingSpec.value = await api.fetchSpecialist(id)
    showWizard.value = true
  } catch {
    // silently fail — card stays visible
  }
}

function handleDeleteRequest(spec: SpecialistSummary) {
  deletingSpec.value = spec
}

async function confirmDelete() {
  if (!deletingSpec.value) return
  await remove(deletingSpec.value.id)
  deletingSpec.value = null
}

async function handleSave(data: Record<string, unknown>, stagedFiles: File[]) {
  saveError.value = ''

  if (editingSpec.value) {
    // Edit mode — update existing specialist
    try {
      await update(editingSpec.value.id, data as Partial<SpecialistDetail>)
    } catch (err: unknown) {
      saveError.value = err instanceof ApiError ? err.message : 'Failed to update specialist'
      wizardRef.value?.resetSubmitting()
      return
    }

    // Upload any new staged files
    if (stagedFiles.length) {
      for (const file of stagedFiles) {
        try {
          await uploadFile(editingSpec.value.id, file)
        } catch {
          // Individual file failures are non-blocking
        }
      }
    }

    showWizard.value = false
    editingSpec.value = null
    await load()
    return
  }

  // Create mode
  let created
  try {
    created = await api.createSpecialist(data)
  } catch (err: unknown) {
    saveError.value = err instanceof ApiError ? err.message : 'Failed to create specialist'
    wizardRef.value?.resetSubmitting()
    return
  }

  // Upload staged files — failures are non-blocking, specialist was already created
  if (stagedFiles.length && created.id) {
    for (const file of stagedFiles) {
      try {
        await uploadFile(created.id, file)
      } catch {
        // Individual file failures are non-blocking
      }
    }
  }

  showWizard.value = false
  await load()
}
</script>

<style scoped>
.spec-page {
  width: 680px;
  margin: 0 auto;
  padding: 2.25rem 0 3rem;
}

@media (max-width: 780px) {
  .spec-page {
    width: 540px;
  }
}

@media (max-width: 600px) {
  .spec-page {
    width: 420px;
  }
}

@media (max-width: 460px) {
  .spec-page {
    width: 320px;
  }
}

/* --- Header --- */
.spec-page__header {
  margin-bottom: 1.75rem;
}

.spec-page__header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.4rem;
}

.spec-page__title-group {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
}

.spec-page__title {
  font-size: 1.5rem;
  font-weight: 700;
  margin: 0;
  color: var(--text-primary);
  letter-spacing: -0.025em;
}

.spec-page__count {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--neon-cyan-60);
  background: var(--neon-cyan-08);
  border: 1px solid var(--neon-cyan-15);
  border-radius: 10px;
  padding: 0.1rem 0.5rem;
  letter-spacing: 0.02em;
  line-height: 1.4;
}

.spec-page__subtitle {
  font-size: 0.8rem;
  color: var(--text-muted);
  margin: 0;
  letter-spacing: 0.01em;
}

.spec-page__divider {
  margin-top: 1.25rem;
  height: 1px;
  background: linear-gradient(
    90deg,
    var(--neon-cyan-15) 0%,
    var(--border-default) 40%,
    transparent 100%
  );
}

.spec-page__create-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.45rem 1rem 0.45rem 0.65rem;
  border: 1px solid var(--neon-cyan-15);
  border-radius: 8px;
  background: transparent;
  color: var(--neon-cyan);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.25s ease;
  white-space: nowrap;
  letter-spacing: 0.01em;
}

.spec-page__create-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 5px;
  background: var(--neon-cyan-08);
  border: 1px solid var(--neon-cyan-15);
  transition: all 0.25s ease;
}

.spec-page__create-btn:hover {
  background: var(--neon-cyan-08);
  border-color: var(--neon-cyan-30);
  box-shadow: 0 0 20px var(--neon-cyan-08), 0 2px 8px rgba(0, 0, 0, 0.3);
  text-shadow: 0 0 8px var(--neon-cyan-30);
}

.spec-page__create-btn:hover .spec-page__create-icon {
  background: var(--neon-cyan-15);
  border-color: var(--neon-cyan-30);
}

.spec-page__create-btn:active {
  transform: scale(0.97);
}

/* --- Empty state --- */
.spec-page__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 4.5rem 2rem 5rem;
  text-align: center;
}

.spec-page__empty-graphic {
  position: relative;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1.5rem;
}

.spec-page__empty-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1px solid var(--border-default);
  animation: empty-pulse 4s ease-in-out infinite;
}

.spec-page__empty-ring--outer {
  inset: -12px;
  border-color: var(--border-subtle);
  animation-delay: 0.5s;
}

@keyframes empty-pulse {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.03); }
}

.spec-page__empty-svg {
  color: var(--text-muted);
  position: relative;
  z-index: 1;
}

.spec-page__empty-text {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
}

.spec-page__empty-hint {
  font-size: 0.78rem;
  color: var(--text-muted);
  margin: 0.4rem 0 1.75rem;
  max-width: 280px;
  line-height: 1.5;
}

.spec-page__empty-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.65rem 1.5rem;
  border: 1px dashed var(--neon-cyan-30);
  border-radius: 8px;
  background: transparent;
  color: var(--neon-cyan);
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.25s ease;
}

.spec-page__empty-btn:hover {
  border-style: solid;
  background: var(--neon-cyan-08);
  box-shadow: 0 0 24px var(--neon-cyan-08), 0 4px 12px rgba(0, 0, 0, 0.2);
  transform: translateY(-1px);
}

.spec-page__empty-btn:active {
  transform: translateY(0);
}

/* --- Grid --- */
.spec-page__grid {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

/* --- Transitions --- */
.card-list-enter-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.card-list-leave-active {
  transition: all 0.25s ease;
}
.card-list-enter-from {
  opacity: 0;
  transform: translateY(14px);
}
.card-list-leave-to {
  opacity: 0;
  transform: scale(0.97);
}
.card-list-move {
  transition: transform 0.3s ease;
}

.wizard-slide-enter-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.wizard-slide-leave-active {
  transition: all 0.2s ease;
}
.wizard-slide-enter-from {
  opacity: 0;
  transform: translateY(20px);
}
.wizard-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.spec-page__save-error {
  margin-bottom: 0.75rem;
  padding: 0.55rem 0.85rem;
  border-radius: 6px;
  font-size: 0.78rem;
  color: var(--neon-red);
  background: rgba(239, 68, 68, 0.06);
  border: 1px solid rgba(239, 68, 68, 0.15);
  cursor: pointer;
  transition: opacity 0.2s;
}

.spec-page__save-error:hover {
  opacity: 0.7;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
