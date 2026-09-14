import type { Sale } from './sale'

export const DASHBOARD_PERIODS = [
  'this_month',
  'previous_month',
  'last_3_months',
  'last_6_months',
  'this_year',
  'custom',
] as const
export type DashboardPeriodName = (typeof DASHBOARD_PERIODS)[number]

export type TrendGranularity = 'day' | 'week' | 'month'

// One currency's worth of a total that must never be summed with a
// different currency's — see the backend's dashboard_service.py module
// docstring. Every monetary dashboard field is a list of these, never a
// bare number: a single-currency dataset naturally produces a one-element
// list, a mixed-currency one produces one entry per currency.
export interface CurrencyAmount {
  currency: string
  amount: number | string
}

export interface PeriodComparison {
  currency: string
  percentage_change: number | null
  amount_change: number | string | null
}

export interface DashboardPeriodInfo {
  period: DashboardPeriodName
  start_date: string
  end_date: string
  previous_start_date: string
  previous_end_date: string
  trend_granularity: TrendGranularity
}

export interface TopService {
  service_name: string
  currency: string
  total: number | string
  count: number
  percentage_of_revenue: number
}

export interface RevenueTrendPoint {
  period_start: string
  currency: string
  gross_total: number | string
  net_total: number | string
}

export interface DashboardStats {
  period: DashboardPeriodInfo
  net_revenue_current_period: CurrencyAmount[]
  net_revenue_previous_period: CurrencyAmount[]
  comparison: PeriodComparison[]
  successful_sales_count: number
  average_transaction_value: CurrencyAmount[]
  gross_revenue: CurrencyAmount[]
  vat_collected: CurrencyAmount[]
  processing_fees: CurrencyAmount[]
  refunds_total: CurrencyAmount[]
  recent_sales: Sale[]
  top_services: TopService[]
  revenue_trend: RevenueTrendPoint[]
  // Operational "needs attention" counts — not scoped to the selected
  // period, see dashboard_service.py.
  pending_documents_count: number
  document_failures_count: number
  failed_payments_count: number
  refunds_needing_attention_count: number
  incomplete_details_count: number
}
