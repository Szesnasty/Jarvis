<template>
  <section
    :id="anchor"
    class="settings-page__section settings-section"
    :class="[sectionClass, { 'settings-section--open': isOpen, 'settings-section--static': !collapsible }]"
  >
    <component
      :is="collapsible ? 'button' : 'div'"
      :type="collapsible ? 'button' : undefined"
      class="settings-section__header"
      :aria-expanded="collapsible ? isOpen : undefined"
      :aria-controls="collapsible ? bodyId : undefined"
      @click="collapsible && toggle()"
    >
      <span class="settings-section__title-row">
        <span v-if="collapsible" class="settings-section__chevron" aria-hidden="true" />
        <h2 class="settings-page__section-title settings-section__title">{{ title }}</h2>
      </span>
      <span v-if="$slots.suffix" class="settings-section__suffix" @click.stop>
        <slot name="suffix" />
      </span>
    </component>
    <div v-show="isOpen" :id="bodyId" class="settings-section__body">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  /** Stable identifier — used for localStorage persistence + DOM anchor id. */
  id: string
  title: string
  defaultOpen?: boolean
  /** Optional extra root class (e.g. "mcp-section" / "privacy-section"). */
  sectionClass?: string
  /** When false, the section is always open and has no toggle UI. */
  collapsible?: boolean
}>(), {
  defaultOpen: true,
  sectionClass: '',
  collapsible: true,
})

const STORAGE_PREFIX = 'jarvis_settings_open:'
const storageKey = computed(() => `${STORAGE_PREFIX}${props.id}`)

const isOpen = ref(props.collapsible ? props.defaultOpen : true)
const bodyId = computed(() => `settings-section__body--${props.id}`)
const anchor = computed(() => props.id)

function readStored(): boolean | null {
  if (typeof localStorage === 'undefined') return null
  try {
    const raw = localStorage.getItem(storageKey.value)
    if (raw === '1') return true
    if (raw === '0') return false
  } catch { /* ignore */ }
  return null
}

function persist(value: boolean) {
  if (typeof localStorage === 'undefined') return
  try {
    localStorage.setItem(storageKey.value, value ? '1' : '0')
  } catch { /* ignore */ }
}

function toggle() {
  isOpen.value = !isOpen.value
}

onMounted(() => {
  if (!props.collapsible) {
    isOpen.value = true
    return
  }
  const stored = readStored()
  if (stored !== null) isOpen.value = stored
  // If user navigated with a hash matching this section, force-open it.
  if (typeof window !== 'undefined' && window.location.hash === `#${props.id}`) {
    isOpen.value = true
  }
})

watch(isOpen, (v) => {
  if (props.collapsible) persist(v)
})
</script>
