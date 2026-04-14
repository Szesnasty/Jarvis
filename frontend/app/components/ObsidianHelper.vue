<template>
  <div class="obsidian-helper">
    <h3 class="obsidian-helper__title">Obsidian Integration</h3>
    <p class="obsidian-helper__desc">Open your Jarvis memory as an Obsidian vault for rich editing and graph visualization.</p>
    <button class="obsidian-helper__open-btn" @click="openInObsidian">
      Open in Obsidian
    </button>
    <details class="obsidian-helper__instructions">
      <summary>Setup Instructions</summary>
      <ol>
        <li>Install <a href="https://obsidian.md" target="_blank" rel="noopener">Obsidian</a></li>
        <li>Open Obsidian → "Open folder as vault"</li>
        <li>Select your <code>Jarvis/memory/</code> folder</li>
        <li>Recommended plugins: Graph view, Tags, Daily notes</li>
      </ol>
    </details>
  </div>
</template>

<script setup lang="ts">
function openInObsidian() {
  window.open('obsidian://open?vault=Jarvis', '_blank')
}
</script>

<style scoped>
.obsidian-helper {
  padding: 1rem;
  border: 1px solid var(--color-border, #333);
  border-radius: 8px;
  margin-top: 1rem;
}
.obsidian-helper__title {
  margin: 0 0 0.5rem;
  font-size: 1rem;
}
.obsidian-helper__desc {
  font-size: 0.9rem;
  opacity: 0.8;
  margin-bottom: 0.75rem;
}
.obsidian-helper__open-btn {
  padding: 0.5rem 1.25rem;
  background: #7c3aed;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
}
.obsidian-helper__open-btn:hover {
  background: #6d28d9;
}
.obsidian-helper__instructions {
  margin-top: 1rem;
  font-size: 0.85rem;
}
.obsidian-helper__instructions summary {
  cursor: pointer;
  opacity: 0.8;
}
.obsidian-helper__instructions ol {
  margin: 0.5rem 0 0 1.5rem;
}
.obsidian-helper__instructions li {
  margin: 0.25rem 0;
}
</style>
