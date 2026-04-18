<template>
  <div class="settings-page">
    <h1 class="settings-page__title">Settings</h1>

    <ProvidersSection
      :settings-loaded="general.loaded.value"
      :server-key-configured="general.serverKeyConfigured.value"
      :key-storage="general.keyStorage.value"
    />

    <LocalModelsSection />

    <WorkspaceSection :path="general.workspacePath.value" />

    <McpSection />

    <VoiceSection
      v-model="general.autoSpeak.value"
      @change="general.updateVoice()"
    />

    <MaintenanceSection />

    <PrivacySection />

    <SharpenSection />

    <BudgetSection />

    <p v-if="status.message.value" class="settings-page__status">
      {{ status.message.value }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import ProvidersSection from '~/components/settings/ProvidersSection.vue'
import LocalModelsSection from '~/components/settings/LocalModelsSection.vue'
import WorkspaceSection from '~/components/settings/WorkspaceSection.vue'
import McpSection from '~/components/settings/McpSection.vue'
import VoiceSection from '~/components/settings/VoiceSection.vue'
import MaintenanceSection from '~/components/settings/MaintenanceSection.vue'
import PrivacySection from '~/components/settings/PrivacySection.vue'
import SharpenSection from '~/components/settings/SharpenSection.vue'
import BudgetSection from '~/components/settings/BudgetSection.vue'
import { useGeneralSettings } from '~/composables/settings/useGeneralSettings'
import { useSettingsStatus } from '~/composables/settings/useSettingsStatus'

const general = useGeneralSettings()
const status = useSettingsStatus()

onMounted(async () => {
  await general.load()
  if (general.error.value) status.set(general.error.value)
})
</script>
