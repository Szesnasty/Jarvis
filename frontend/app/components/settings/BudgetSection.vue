<template>
  <SettingsSection
    id="budget"
    title="Token Usage & Budget"
    section-class="budget-section"
    :default-open="false"
  >
    <!-- Today's gauge -->
    <div class="budget-today" v-if="budget">
      <div class="budget-gauge">
        <div class="budget-gauge__track">
          <div
            class="budget-gauge__fill"
            :class="{
              'budget-gauge__fill--warning': budget.level === 'warning',
              'budget-gauge__fill--exceeded': budget.level === 'exceeded',
            }"
            :style="{ width: Math.min(budget.percent, 100) + '%' }"
          />
          <div
            v-if="budget.percent > 100"
            class="budget-gauge__overflow"
            :style="{ width: Math.min(budget.percent - 100, 100) + '%' }"
          />
        </div>
        <div class="budget-gauge__labels">
          <span
            class="budget-gauge__pct"
            :class="{
              'budget-gauge__pct--warning': budget.level === 'warning',
              'budget-gauge__pct--exceeded': budget.level === 'exceeded',
            }"
          >
            {{ (budget.budget ?? 0) > 0 ? budget.percent + '%' : 'No limit' }}
          </span>
          <span class="budget-gauge__detail">
            {{ formatTokens(budget.used_today) }} / {{ (budget.budget ?? 0) > 0 ? formatTokens(budget.budget ?? 0) : '\u221E' }} tokens today
          </span>
        </div>
      </div>
      <p v-if="budget.level === 'exceeded'" class="budget-exceeded-msg">
        Budget exceeded — chat is blocked until tomorrow or you raise the limit.
      </p>
    </div>

    <!-- Budget control -->
    <div class="budget-control">
      <label class="budget-control__label">Daily token budget</label>
      <div class="budget-control__row">
        <input
          type="range"
          class="budget-control__slider"
          :min="0"
          :max="2000000"
          :step="50000"
          v-model.number="budgetValue"
          @change="onSave"
        />
        <div class="budget-control__input-wrap">
          <input
            type="number"
            class="budget-control__input"
            v-model.number="budgetValue"
            @change="onSave"
            :min="0"
            :step="50000"
          />
          <span class="budget-control__unit">tokens</span>
        </div>
      </div>
      <div class="budget-control__presets">
        <button
          v-for="p in BUDGET_PRESETS"
          :key="p.value"
          class="budget-preset"
          :class="{ 'budget-preset--active': budgetValue === p.value }"
          @click="budgetValue = p.value; onSave()"
        >{{ p.label }}</button>
      </div>
      <p class="budget-control__hint">
        Set to <strong>0</strong> for unlimited. Est. cost at limit:
        <span class="settings-page__mono">{{ budgetValue > 0 ? '$' + estimateCost(budgetValue) : 'N/A' }}</span>/day
      </p>
    </div>

    <!-- All-time stats -->
    <div class="budget-stats" v-if="usage">
      <div class="budget-stat">
        <span class="budget-stat__value">{{ formatTokens(usage.total) }}</span>
        <span class="budget-stat__label">All-time tokens</span>
      </div>
      <div class="budget-stat">
        <span class="budget-stat__value">{{ usage.request_count }}</span>
        <span class="budget-stat__label">Requests</span>
      </div>
      <div class="budget-stat">
        <span class="budget-stat__value">${{ (usage.cost_estimate ?? 0).toFixed(2) }}</span>
        <span class="budget-stat__label">Est. total cost</span>
      </div>
    </div>

    <!-- Daily history sparkline -->
    <div class="budget-history" v-if="history.length > 0">
      <span class="budget-history__title">Last 14 days</span>
      <div class="budget-history__chart">
        <div
          v-for="(day, i) in history"
          :key="day.date"
          class="budget-history__bar-wrap"
          :title="day.date + ': ' + formatTokens(day.total_tokens) + ' tokens'"
        >
          <div
            class="budget-history__bar"
            :style="{
              height: historyMax > 0 ? Math.max((day.total_tokens / historyMax) * 100, 2) + '%' : '2%',
              animationDelay: (i * 40) + 'ms',
            }"
            :class="{
              'budget-history__bar--over': budgetValue > 0 && day.total_tokens > budgetValue,
              'budget-history__bar--today': i === 0,
            }"
          />
          <span class="budget-history__day">{{ day.date.slice(8) }}</span>
        </div>
      </div>
      <div
        v-if="budgetValue > 0 && historyMax > 0"
        class="budget-history__limit"
        :style="{ bottom: Math.min((budgetValue / historyMax) * 100, 100) + '%' }"
      >
        <span class="budget-history__limit-label">limit</span>
      </div>
    </div>
  </SettingsSection>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import SettingsSection from '~/components/settings/SettingsSection.vue'
import {
  useBudgetSettings,
  formatTokens,
  estimateCost,
  BUDGET_PRESETS,
} from '~/composables/settings/useBudgetSettings'
import { useSettingsStatus } from '~/composables/settings/useSettingsStatus'

const { usage, budget, budgetValue, history, load, save } = useBudgetSettings()
const status = useSettingsStatus()

const historyMax = computed(() => {
  const maxTokens = Math.max(...history.value.map(d => d.total_tokens), 0)
  return budgetValue.value > 0 ? Math.max(maxTokens, budgetValue.value) : maxTokens
})

async function onSave() {
  const ok = await save()
  if (!ok) status.set('Failed to update budget')
}

onMounted(load)
</script>
