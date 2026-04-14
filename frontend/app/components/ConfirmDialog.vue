<template>
  <Teleport to="body">
    <Transition name="confirm-dialog">
      <div v-if="visible" class="confirm-dialog__overlay" @click.self="$emit('cancel')">
        <div class="confirm-dialog">
          <div class="confirm-dialog__icon">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
              <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              <line x1="10" y1="11" x2="10" y2="17"/>
              <line x1="14" y1="11" x2="14" y2="17"/>
            </svg>
          </div>
          <h3 class="confirm-dialog__title">{{ title }}</h3>
          <p class="confirm-dialog__message">{{ message }}</p>
          <div class="confirm-dialog__actions">
            <button class="confirm-dialog__btn confirm-dialog__btn--cancel" :disabled="loading" @click="$emit('cancel')">Cancel</button>
            <button class="confirm-dialog__btn confirm-dialog__btn--confirm" :class="{ 'confirm-dialog__btn--loading': loading }" :disabled="loading" @click="$emit('confirm')">
              <span v-if="loading" class="confirm-dialog__spinner" />
              {{ loading ? 'Deleting…' : confirmLabel }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
defineProps<{
  visible: boolean
  title: string
  message: string
  confirmLabel?: string
  loading?: boolean
}>()

defineEmits<{
  confirm: []
  cancel: []
}>()
</script>

<style scoped>
.confirm-dialog__overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
}

.confirm-dialog {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 14px;
  padding: 1.75rem 2rem;
  max-width: 380px;
  width: 90vw;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.6rem;
  box-shadow:
    0 0 40px rgba(2, 254, 255, 0.06),
    0 20px 60px rgba(0, 0, 0, 0.5);
}

.confirm-dialog__icon {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: rgba(239, 68, 68, 0.85);
  margin-bottom: 0.25rem;
  box-shadow: 0 0 20px rgba(239, 68, 68, 0.1);
}

.confirm-dialog__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.confirm-dialog__message {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
  text-align: center;
  line-height: 1.5;
}

.confirm-dialog__actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 0.75rem;
  width: 100%;
}

.confirm-dialog__btn {
  flex: 1;
  padding: 0.55rem 1rem;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}

.confirm-dialog__btn--cancel {
  background: var(--bg-elevated);
  border-color: var(--border-default);
  color: var(--text-secondary);
}

.confirm-dialog__btn--cancel:hover {
  background: var(--bg-surface);
  color: var(--text-primary);
  border-color: var(--border-subtle);
}

.confirm-dialog__btn--confirm {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.3);
  color: rgba(239, 68, 68, 0.9);
}

.confirm-dialog__btn--confirm:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.2);
  border-color: rgba(239, 68, 68, 0.5);
  box-shadow: 0 0 15px rgba(239, 68, 68, 0.15);
  text-shadow: 0 0 6px rgba(239, 68, 68, 0.3);
}

.confirm-dialog__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.confirm-dialog__btn--loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.confirm-dialog__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(239, 68, 68, 0.2);
  border-top-color: rgba(239, 68, 68, 0.8);
  border-radius: 50%;
  animation: confirm-spin 0.6s linear infinite;
}

@keyframes confirm-spin {
  to { transform: rotate(360deg); }
}

/* Transition */
.confirm-dialog-enter-active,
.confirm-dialog-leave-active {
  transition: opacity 0.2s ease;
}
.confirm-dialog-enter-active .confirm-dialog,
.confirm-dialog-leave-active .confirm-dialog {
  transition: transform 0.2s ease, opacity 0.2s ease;
}
.confirm-dialog-enter-from,
.confirm-dialog-leave-to {
  opacity: 0;
}
.confirm-dialog-enter-from .confirm-dialog {
  transform: scale(0.95);
}
.confirm-dialog-leave-to .confirm-dialog {
  transform: scale(0.95);
}
</style>
