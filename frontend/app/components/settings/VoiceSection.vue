<template>
  <SettingsSection id="voice" title="Voice Settings" :default-open="false">
    <label class="settings-page__toggle">
      <input
        type="checkbox"
        :checked="modelValue"
        @change="onToggle(($event.target as HTMLInputElement).checked)"
      />
      Auto-speak responses
    </label>
  </SettingsSection>
</template>

<script setup lang="ts">
import SettingsSection from '~/components/settings/SettingsSection.vue'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  'change': []
}>()

function onToggle(value: boolean) {
  emit('update:modelValue', value)
  emit('change')
}

// Suppress unused-prop warning in TS
void props
</script>
