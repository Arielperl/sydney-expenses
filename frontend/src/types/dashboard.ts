import type { Expense } from './expense'

export interface CategoryTotal {
  category: string
  total: number | string
}

export interface DashboardStats {
  current_month_total: number | string
  previous_month_total: number | string
  percentage_change: number | null
  totals_by_category: CategoryTotal[]
  recent_expenses: Expense[]
}
