import type { Sale } from './sale'

// One currency's worth of a total that must never be summed with a
// different currency's — see the backend's dashboard_service.py module
// docstring. Every monetary dashboard field is a list of these, never a
// bare number: a single-currency dataset naturally produces a one-element
// list, a mixed-currency one produces one entry per currency.
export interface CurrencyAmount {
  currency: string
  amount: number | string
}

export interface TopService {
  service_name: string
  currency: string
  total: number | string
  count: number
}

export interface RevenueTrendPoint {
  period_start: string
  currency: string
  total: number | string
}

export interface DashboardStats {
  net_revenue_this_month: CurrencyAmount[]
  net_revenue_previous_month: CurrencyAmount[]
  // Keyed by currency — a currency with no revenue in the previous period
  // has no honest percentage to report (see StatCard's "no comparison
  // baseline" treatment), represented as `null` for that currency.
  percentage_change: Record<string, number | null>
  successful_sales_count: number
  average_transaction_value: CurrencyAmount[]
  gross_revenue: CurrencyAmount[]
  vat_collected: CurrencyAmount[]
  processing_fees: CurrencyAmount[]
  recent_sales: Sale[]
  top_services: TopService[]
  revenue_trend: RevenueTrendPoint[]
  pending_documents_count: number
  pending_documents_total: CurrencyAmount[]
  document_failures_count: number
  failed_payments_count: number
  refunds_count: number
  refunds_total: CurrencyAmount[]
}
