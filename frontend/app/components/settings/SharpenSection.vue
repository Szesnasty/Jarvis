<template>
  <SettingsSection
    id="sharpen"
    title="Sharpen with Local AI"
    section-class="sharpen-section"
    :default-open="false"
  >
    <p class="sharpen-section__lead">
      One-click pass through your local LLM to enrich every note and Jira issue
      with summaries, tags and entities — improves retrieval quality and graph density.
      Runs entirely on your machine via Ollama. No API calls to Anthropic.
    </p>
    <div class="sharpen-section__meta">
      <div class="sharpen-section__model-select">
        <label class="sharpen-section__model-label">Model:</label>
        <select
          class="sharpen-section__model-dropdown"
          :value="sharpen.enrichmentModelId.value"
          @change="onModelChange(($event.target as HTMLSelectElement).value)"
        >
          <option v-for="m in installedLocalModels" :key="m.litellm_model" :value="m.litellm_model">
            {{ m.label }} · {{ qualityDotsText(m.preset) }}
          </option>
        </select>
      </div>
      <span class="sharpen-section__chip" v-if="sharpen.queue.value">
        Queue: <strong>{{ sharpen.queue.value.pending }}</strong> pending /
        <strong>{{ sharpen.queue.value.processing }}</strong> processing
      </span>
      <span
        class="sharpen-section__chip sharpen-section__chip--warn"
        v-if="sharpen.queue.value && sharpen.queue.value.failed_last_hour > 0"
      >
        Failed (1h): {{ sharpen.queue.value.failed_last_hour }}
      </span>
    </div>
    <div class="settings-page__actions">
      <button
        class="settings-page__btn settings-page__btn--primary"
        :disabled="sharpen.running.value"
        @click="onRun(true)"
      >
        {{ sharpen.running.value ? 'Enqueuing…' : 'Sharpen all notes & issues' }}
      </button>
      <button
        class="settings-page__btn"
        :disabled="sharpen.running.value"
        @click="onRun(false)"
      >
        Notes only
      </button>
    </div>
    <label class="settings-page__toggle sharpen-section__battery" v-if="sharpen.onBattery.value !== null">
      <input
        type="checkbox"
        v-model="sharpen.allowOnBattery.value"
        @change="sharpen.updateBatterySetting()"
      />
      Allow processing on battery
      <span class="sharpen-section__battery-hint" v-if="sharpen.onBattery.value">
        &nbsp;⚡ Currently on battery — {{ sharpen.allowOnBattery.value ? 'worker will run' : 'worker paused' }}
      </span>
    </label>

    <div class="sharpen-progress" v-if="sharpen.total.value > 0">
      <div class="sharpen-progress__header">
        <span class="sharpen-progress__label">
          <span v-if="sharpen.active.value && sharpen.progress.value < 100" class="sharpen-progress__dot" />
          <template v-if="sharpen.progress.value >= 100">
            Done &mdash; <strong>{{ sharpen.total.value }}</strong> items sharpened
          </template>
          <template v-else>
            Processing&hellip; <strong>{{ sharpen.done.value }}</strong>&thinsp;/&thinsp;{{ sharpen.total.value }} items
          </template>
        </span>
        <span class="sharpen-progress__pct">{{ sharpen.progress.value }}&thinsp;%</span>
        <button
          v-if="sharpen.active.value && sharpen.progress.value < 100"
          class="settings-page__btn settings-page__btn--sm settings-page__btn--danger sharpen-progress__cancel"
          :disabled="sharpen.cancelling.value"
          @click="onCancel"
        >
          {{ sharpen.cancelling.value ? 'Cancelling…' : 'Cancel' }}
        </button>
      </div>
      <div class="sharpen-progress__track">
        <div
          class="sharpen-progress__fill"
          :class="{ 'sharpen-progress__fill--done': sharpen.progress.value >= 100 }"
          :style="{ width: Math.max(sharpen.progress.value, sharpen.total.value > 0 ? 1 : 0) + '%' }"
        />
        <div
          class="sharpen-progress__shimmer"
          v-if="sharpen.active.value && sharpen.progress.value < 100"
        />
      </div>
      <div class="sharpen-progress__footer">
        <template v-if="sharpen.progress.value < 100 && sharpen.queue.value">
          <span class="sharpen-progress__sub">{{ sharpen.queue.value.pending }} pending</span>
          <span class="sharpen-progress__sub">{{ sharpen.queue.value.processing }} processing</span>
        </template>
        <span
          class="sharpen-progress__sub sharpen-progress__sub--warn"
          v-if="sharpen.queue.value && sharpen.queue.value.failed_last_hour > 0"
        >{{ sharpen.queue.value.failed_last_hour }} failed (1h)</span>
        <span
          class="sharpen-progress__sub sharpen-section__skipped"
          v-if="sharpen.lastResult.value && sharpen.lastResult.value.skipped > 0"
        >
          {{ sharpen.lastResult.value.skipped }} skipped
        </span>
      </div>
    </div>
  </SettingsSection>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import SettingsSection from '~/components/settings/SettingsSection.vue'
import { useSharpen, qualityDotsText } from '~/composables/settings/useSharpen'
import { useSettingsStatus } from '~/composables/settings/useSettingsStatus'

const sharpen = useSharpen()
const status = useSettingsStatus()
const localModels = useLocalModels()

const installedLocalModels = computed(() =>
  localModels.catalog.value.filter(m => m.installed),
)

async function onRun(includeJira: boolean) {
  const result = await sharpen.run(includeJira)
  status.set(result
    ? `Enqueued ${result.queued} items for local AI sharpening`
    : 'Sharpen request failed')
}

async function onCancel() {
  const removed = await sharpen.cancel()
  status.set(removed != null
    ? `Cancelled — removed ${removed} pending items`
    : 'Cancel failed')
}

async function onModelChange(model: string) {
  const ok = await sharpen.changeEnrichmentModel(model)
  status.set(ok
    ? `Enrichment model set to ${model.replace('ollama_chat/', '')}`
    : 'Failed to update enrichment model')
}

onMounted(() => sharpen.init())
</script>
