<template>
  <span class="help-icon" :class="{ 'help-icon--inline': inline }">
    <button
      type="button"
      class="help-icon__btn"
      :aria-label="ariaLabel || 'Help'"
      @click.stop="onClick"
      @mouseenter="open = true"
      @mouseleave="open = false"
      @focus="open = true"
      @blur="open = false"
    >
      ?
    </button>
    <span v-if="open" class="help-icon__tip" role="tooltip">
      <slot>{{ text }}</slot>
      <span v-if="actionLabel" class="help-icon__action">
        <NuxtLink to="/settings#smart-connect" class="help-icon__link">
          {{ actionLabel }}
        </NuxtLink>
      </span>
    </span>
  </span>
</template>

<script setup lang="ts">
import { ref } from 'vue'

withDefaults(defineProps<{
  text?: string
  ariaLabel?: string
  actionLabel?: string
  inline?: boolean
}>(), {
  text: '',
  ariaLabel: '',
  actionLabel: '',
  inline: false,
})

const open = ref(false)

function onClick() {
  open.value = !open.value
}
</script>

<style scoped>
.help-icon {
  position: relative;
  display: inline-flex;
  align-items: center;
}
.help-icon--inline {
  margin-left: 0.35rem;
}
.help-icon__btn {
  width: 16px;
  height: 16px;
  padding: 0;
  border-radius: 50%;
  border: 1px solid var(--neon-cyan-30, rgba(120, 220, 255, 0.3));
  background: transparent;
  color: var(--neon-cyan, #78dcff);
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  cursor: help;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}
.help-icon__btn:hover,
.help-icon__btn:focus-visible {
  background: var(--neon-cyan-08, rgba(120, 220, 255, 0.08));
  border-color: var(--neon-cyan, #78dcff);
  outline: none;
}
.help-icon__tip {
  position: absolute;
  z-index: 100;
  top: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  min-width: 220px;
  max-width: 320px;
  padding: 0.55rem 0.7rem;
  border-radius: 6px;
  background: var(--surface-elevated, #1a1d24);
  border: 1px solid var(--neon-cyan-15, rgba(120, 220, 255, 0.18));
  color: var(--text-primary, #e6e6e6);
  font-size: 0.78rem;
  line-height: 1.4;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
  pointer-events: auto;
  white-space: normal;
}
.help-icon__action {
  display: block;
  margin-top: 0.4rem;
  padding-top: 0.4rem;
  border-top: 1px solid var(--neon-cyan-15, rgba(120, 220, 255, 0.18));
}
.help-icon__link {
  color: var(--neon-cyan, #78dcff);
  text-decoration: none;
  font-weight: 500;
}
.help-icon__link:hover {
  text-decoration: underline;
}
</style>
