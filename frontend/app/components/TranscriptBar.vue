<script setup lang="ts">
const props = defineProps<{
  transcript: string
  visible: boolean
}>()
</script>

<template>
  <Transition name="fade">
    <div v-if="visible && transcript" class="transcript-bar">
      {{ transcript }}
    </div>
  </Transition>
</template>

<style scoped>
.transcript-bar {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
  color: #94a3b8;
  text-align: center;
  font-style: italic;
  min-height: 1.5rem;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
