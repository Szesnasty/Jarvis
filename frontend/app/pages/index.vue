<script setup lang="ts">
const { isInitialized, checkWorkspaceStatus } = useAppState()

await checkWorkspaceStatus()

if (isInitialized.value) {
  await navigateTo('/main', { replace: true })
} else {
  await navigateTo('/onboarding', { replace: true })
}
</script>

<template>
  <div />
</template>
