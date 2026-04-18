import { ref } from 'vue'

export type BudgetSnapshot = {
  daily_budget: number
  /** Some templates check `budget.budget` directly — kept optional for back-compat. */
  budget?: number
  used_today: number
  percent: number
  level: string
}

export type UsageStats = {
  total: number
  request_count: number
  cost_estimate: number
}

export type UsageHistoryEntry = {
  date: string
  total_tokens: number
}

export const BUDGET_PRESETS = [
  { label: '50K', value: 50000 },
  { label: '100K', value: 100000 },
  { label: '250K', value: 250000 },
  { label: '500K', value: 500000 },
  { label: '1M', value: 1000000 },
  { label: 'Unlimited', value: 0 },
]

export function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K'
  return String(n)
}

export function estimateCost(tokens: number): string {
  return ((tokens / 1_000_000) * 9).toFixed(2)
}

export function useBudgetSettings() {
  const usage = ref<UsageStats | null>(null)
  const budget = ref<BudgetSnapshot | null>(null)
  const budgetValue = ref(100000)
  const history = ref<UsageHistoryEntry[]>([])

  async function load() {
    try {
      usage.value = await $fetch<UsageStats>('/api/settings/usage')
    } catch { /* non-critical */ }
    try {
      const b = await $fetch<BudgetSnapshot>('/api/settings/budget')
      budget.value = b
      budgetValue.value = b.daily_budget
    } catch { /* non-critical */ }
    try {
      const h = await $fetch<UsageHistoryEntry[]>('/api/settings/usage/history')
      history.value = h.slice(0, 14)
    } catch { /* non-critical */ }
  }

  async function save(): Promise<boolean> {
    try {
      await $fetch('/api/settings/budget', {
        method: 'PATCH',
        body: { daily_token_budget: budgetValue.value },
      })
      const b = await $fetch<BudgetSnapshot>('/api/settings/budget')
      budget.value = b
      return true
    } catch {
      return false
    }
  }

  return { usage, budget, budgetValue, history, load, save }
}
