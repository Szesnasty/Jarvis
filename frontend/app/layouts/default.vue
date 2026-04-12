<template>
  <div class="default-layout">
    <StatusBar />
    <slot />
  </div>
</template>

<style scoped>
.default-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}
</style>
