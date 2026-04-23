<script setup lang="ts">
const { items, dismiss } = useSnackbar()

const ICONS: Record<string, string> = {
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
  success: '✓',
}
</script>

<template>
  <Teleport to="body">
    <div class="snackbar-stack" aria-live="assertive" aria-atomic="false">
      <TransitionGroup name="snack">
        <div
          v-for="item in items"
          :key="item.id"
          class="snackbar"
          :class="`snackbar--${item.type}`"
          role="alert"
        >
          <span class="snackbar__icon">{{ ICONS[item.type] }}</span>
          <span class="snackbar__message">{{ item.message }}</span>
          <a
            v-if="item.action?.href"
            :href="item.action.href"
            target="_blank"
            rel="noopener"
            class="snackbar__action"
            @click="dismiss(item.id)"
          >{{ item.action.label }}</a>
          <button
            v-else-if="item.action?.onClick"
            class="snackbar__action"
            @click="() => { item.action!.onClick!(); dismiss(item.id) }"
          >{{ item.action.label }}</button>
          <button class="snackbar__close" :aria-label="'Dismiss'" @click="dismiss(item.id)">✕</button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<style scoped>
.snackbar-stack {
  position: fixed;
  bottom: 1.5rem;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  z-index: 9999;
  pointer-events: none;
  width: max-content;
  max-width: min(560px, 92vw);
}

.snackbar {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.75rem 1rem;
  border-radius: 10px;
  font-size: 0.875rem;
  font-weight: 500;
  line-height: 1.4;
  pointer-events: all;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
  border: 1px solid transparent;
}

.snackbar--error {
  background: #2a1010;
  border-color: #c0392b;
  color: #ff6b6b;
}

.snackbar--warning {
  background: #1f1a08;
  border-color: #b7860b;
  color: #f0c040;
}

.snackbar--success {
  background: #0d1f10;
  border-color: #27ae60;
  color: #5edf88;
}

.snackbar--info {
  background: #0d1a2a;
  border-color: #2980b9;
  color: #5dade2;
}

.snackbar__icon {
  flex-shrink: 0;
  font-size: 0.9rem;
}

.snackbar__message {
  flex: 1;
}

.snackbar__action {
  flex-shrink: 0;
  background: none;
  border: 1px solid currentColor;
  border-radius: 6px;
  color: inherit;
  cursor: pointer;
  font-size: 0.8rem;
  font-weight: 600;
  padding: 0.2rem 0.6rem;
  text-decoration: none;
  transition: opacity 0.15s;
  white-space: nowrap;
}

.snackbar__action:hover {
  opacity: 0.75;
}

.snackbar__close {
  flex-shrink: 0;
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 0.75rem;
  opacity: 0.5;
  padding: 0.1rem 0.25rem;
  transition: opacity 0.15s;
}

.snackbar__close:hover {
  opacity: 1;
}

/* TransitionGroup animations */
.snack-enter-active,
.snack-leave-active {
  transition: opacity 0.25s, transform 0.25s;
}

.snack-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.snack-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
