<template>
  <SettingsSection
    id="graph-expansion"
    title="Graph Expansion in Chat"
    section-class="graph-expansion-section"
    :default-open="false"
  >
    <p class="settings-page__hint">
      When answering questions, Jarvis can include additional notes reached via
      confirmed graph links. Confirmed <em>related</em> and project (<em>part_of</em>)
      edges are safe to expand. Unconfirmed suggestions are off by default.
    </p>

    <div class="graph-expansion-section__rows">
      <label class="graph-expansion-section__toggle">
        <input
          type="checkbox"
          class="graph-expansion-section__checkbox"
          :checked="config.use_related"
          :disabled="saving"
          @change="onSet('use_related', ($event.target as HTMLInputElement).checked)"
        />
        <span class="graph-expansion-section__label">
          <strong>Use confirmed <code>related</code> links</strong>
          <span class="graph-expansion-section__sub">
            Notes you've explicitly linked via "Keep" — highest-trust edges.
          </span>
        </span>
      </label>

      <label class="graph-expansion-section__toggle">
        <input
          type="checkbox"
          class="graph-expansion-section__checkbox"
          :checked="config.use_part_of"
          :disabled="saving"
          @change="onSet('use_part_of', ($event.target as HTMLInputElement).checked)"
        />
        <span class="graph-expansion-section__label">
          <strong>Use project (<code>part_of</code>) membership</strong>
          <span class="graph-expansion-section__sub">
            Pull in sibling notes from the same project or area.
          </span>
        </span>
      </label>

      <label class="graph-expansion-section__toggle graph-expansion-section__toggle--opt-in">
        <input
          type="checkbox"
          class="graph-expansion-section__checkbox"
          :checked="config.use_suggested_strong"
          :disabled="saving"
          @change="onSet('use_suggested_strong', ($event.target as HTMLInputElement).checked)"
        />
        <span class="graph-expansion-section__label">
          <strong>Use strong <code>suggested_related</code> candidates</strong>
          <span class="graph-expansion-section__sub">
            Unconfirmed suggestions with confidence ≥ 80%. Off by default — enable once
            you've reviewed and kept the best ones.
          </span>
        </span>
      </label>
    </div>

    <p v-if="error" class="graph-expansion-section__error">{{ error }}</p>
  </SettingsSection>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import SettingsSection from '~/components/settings/SettingsSection.vue'
import { useGraphExpansionSettings, type GraphExpansionConfig } from '~/composables/settings/useGraphExpansionSettings'
import { useSettingsStatus } from '~/composables/settings/useSettingsStatus'

const { config, saving, error, load, set } = useGraphExpansionSettings()
const status = useSettingsStatus()

async function onSet(key: keyof GraphExpansionConfig, value: boolean) {
  await set(key, value)
  if (!error.value) {
    const label = key.replaceAll('_', ' ')
    status.set(value ? `Enabled: ${label}` : `Disabled: ${label}`)
  }
}

onMounted(load)
</script>

<style scoped>
.graph-expansion-section__rows {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.25rem;
}

.graph-expansion-section__toggle {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  cursor: pointer;
}

.graph-expansion-section__toggle--opt-in {
  opacity: 0.8;
}

.graph-expansion-section__checkbox {
  margin-top: 0.15rem;
  flex-shrink: 0;
  accent-color: var(--neon-cyan, #00c8ff);
}

.graph-expansion-section__label {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.graph-expansion-section__label strong {
  font-size: 0.88rem;
  color: var(--text-primary);
}

.graph-expansion-section__label code {
  font-size: 0.82em;
  background: var(--bg-elevated, rgba(255,255,255,0.04));
  padding: 0.05rem 0.3rem;
  border-radius: 3px;
}

.graph-expansion-section__sub {
  font-size: 0.78rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.graph-expansion-section__error {
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--danger, #f87171);
}
</style>
