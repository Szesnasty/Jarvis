<template>
  <SettingsSection id="providers" title="AI Providers" :collapsible="false">
    <template #suffix>
      <div class="providers-badge">
        <span class="providers-badge__icon" v-html="lockIcon"></span>
        <span class="providers-badge__label">Keys handled locally</span>
      </div>
    </template>

    <KeyProtectionInfo />

    <div v-if="settingsLoaded && serverKeyConfigured" class="server-key-notice">
      <svg class="server-key-notice__icon" viewBox="0 0 20 20" fill="none">
        <circle cx="10" cy="10" r="9" stroke="currentColor" stroke-width="1.5" />
        <path d="M6 10.5l2.5 2.5 5.5-5.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <div class="server-key-notice__text">
        <span class="server-key-notice__primary">Anthropic key stored on server</span>
        <span class="server-key-notice__secondary">
          <template v-if="keyStorage === 'keyring'">via system credential store</template>
          <template v-else-if="keyStorage === 'environment'">via environment variable</template>
          <template v-else-if="keyStorage === 'file'">via local file</template>
        </span>
      </div>
    </div>

    <div class="providers-list">
      <ProviderCard
        v-for="p in apiKeys.providers"
        :key="p.id"
        :provider="p"
        :configured="apiKeys.isConfigured(p.id)"
        :masked-key="apiKeys.getMaskedKey(p.id)"
        :remembered="apiKeys.isRemembered(p.id)"
        @add-key="openAddKey(p)"
        @remove-key="apiKeys.removeKey(p.id)"
      />
    </div>

    <AddKeyModal
      :provider="addKeyProvider"
      :show="showAddKeyModal"
      @close="showAddKeyModal = false"
      @saved="onKeySaved"
    />
  </SettingsSection>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { ProviderConfig } from '~/types'
import { ICON_LOCK } from '~/composables/providerIcons'
import { useSettingsStatus } from '~/composables/settings/useSettingsStatus'
import SettingsSection from '~/components/settings/SettingsSection.vue'

defineProps<{
  settingsLoaded: boolean
  serverKeyConfigured: boolean
  keyStorage?: string
}>()

const lockIcon = ICON_LOCK
const status = useSettingsStatus()
const apiKeys = useApiKeys()
const showAddKeyModal = ref(false)
const addKeyProvider = ref<ProviderConfig>(apiKeys.providers[0]!)

function openAddKey(provider: ProviderConfig) {
  addKeyProvider.value = provider
  showAddKeyModal.value = true
}

function onKeySaved(_providerId: string) {
  status.set('API key saved')
}
</script>
