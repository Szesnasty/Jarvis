<template>
  <SettingsSection id="workspace" title="Workspace" :default-open="true">
    <p class="settings-page__path">{{ path }}</p>
  </SettingsSection>
</template>

<script setup lang="ts">
import SettingsSection from '~/components/settings/SettingsSection.vue'

defineProps<{ path: string }>()
</script>
