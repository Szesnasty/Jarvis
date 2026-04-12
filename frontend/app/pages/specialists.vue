<template>
  <div class="specialists-page">
    <h1 class="specialists-page__title">Specialists</h1>

    <div v-if="specialists.length === 0 && !showWizard" class="specialists-page__empty">
      Create your first specialist
    </div>

    <div v-if="!showWizard" class="specialists-page__grid">
      <SpecialistCard
        v-for="spec in specialists"
        :key="spec.id"
        :specialist="spec"
        :active="activeSpecialist?.id === spec.id"
        @activate="handleActivate(spec.id)"
        @delete="handleDelete(spec.id)"
        @click="handleCardClick(spec)"
      />
    </div>

    <button
      v-if="!showWizard"
      class="specialists-page__create-btn"
      @click="showWizard = true"
    >
      + Create Specialist
    </button>

    <SpecialistWizard
      v-if="showWizard"
      @save="handleSave"
      @cancel="showWizard = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { SpecialistSummary } from '~/types'
import { useSpecialists } from '~/composables/useSpecialists'
import { useApi } from '~/composables/useApi'

const { specialists, activeSpecialist, load, activate, deactivate, remove } = useSpecialists()
const api = useApi()
const showWizard = ref(false)
const selectedSpecialist = ref<SpecialistSummary | null>(null)

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

async function handleDelete(id: string) {
  await remove(id)
}

function handleCardClick(spec: SpecialistSummary) {
  selectedSpecialist.value = spec
}

async function handleSave(data: Record<string, unknown>) {
  await api.createSpecialist(data)
  showWizard.value = false
  await load()
}
</script>

<style scoped>
.specialists-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
}
.specialists-page__title {
  font-size: 1.5rem;
  margin-bottom: 1.5rem;
}
.specialists-page__empty {
  text-align: center;
  padding: 3rem 0;
  opacity: 0.6;
  font-size: 1.1rem;
}
.specialists-page__grid {
  display: grid;
  gap: 1rem;
}
.specialists-page__create-btn {
  margin-top: 1.5rem;
  padding: 0.75rem 1.5rem;
  border: 1px dashed var(--color-border, #333);
  border-radius: 8px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 1rem;
  width: 100%;
}
.specialists-page__create-btn:hover {
  border-style: solid;
  background: rgba(96, 165, 250, 0.08);
}
</style>
