<template>
  <div class="key-info">
    <div class="key-info__header">
      <span class="key-info__icon">{{ icon }}</span>
      <span class="key-info__title">{{ title }}</span>
    </div>
    <ul class="key-info__list">
      <li>Keys are stored in your browser only</li>
      <li>Never sent to our server or logged</li>
      <li>Passed directly to the AI provider</li>
      <li>Session keys clear when you close tab</li>
    </ul>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  icon?: string
}>(), {
  title: 'How we protect your keys',
  icon: 'ℹ️',
})
</script>

<style scoped>
.key-info {
  padding: 0.65rem 0.85rem;
  border-radius: 6px;
  background: rgba(2, 254, 255, 0.03);
  border: 1px solid var(--border-subtle);
  margin-bottom: 1rem;
}
.key-info__header {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.4rem;
}
.key-info__icon {
  font-size: 0.9rem;
  flex-shrink: 0;
}
.key-info__title {
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-primary);
}
.key-info__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}
.key-info__list li {
  font-size: 0.78rem;
  color: var(--text-secondary);
  padding-left: 1rem;
  position: relative;
}
.key-info__list li::before {
  content: '•';
  position: absolute;
  left: 0.2rem;
  color: var(--neon-cyan-30);
}
</style>
