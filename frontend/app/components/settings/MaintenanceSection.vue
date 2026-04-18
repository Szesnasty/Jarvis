<template>
  <SettingsSection id="maintenance" title="Maintenance" :default-open="false">
    <div class="settings-page__actions">
      <button class="settings-page__btn" @click="onReindex">Reindex Memory</button>
      <button class="settings-page__btn" @click="onRebuild">Rebuild Graph</button>
    </div>
  </SettingsSection>
</template>

<script setup lang="ts">
import SettingsSection from '~/components/settings/SettingsSection.vue'
import { useGeneralSettings } from '~/composables/settings/useGeneralSettings'
import { useSettingsStatus } from '~/composables/settings/useSettingsStatus'

const general = useGeneralSettings()
const status = useSettingsStatus()

async function onReindex() {
  const indexed = await general.reindexMemory()
  status.set(indexed != null ? `Reindexed ${indexed} notes` : 'Reindex failed')
}

async function onRebuild() {
  const ok = await general.rebuildGraph()
  status.set(ok ? 'Graph rebuilt' : 'Rebuild failed')
}
</script>
