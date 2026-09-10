import type { Sale } from './sale'

export interface TopService {
  service_name: string
  total: number | string
  count: number
}

export interface RevenueTrendPoint {
  period_start: string
  total: number | string
}

export interface DashboardStats {
  net_revenue_this_month: number | string
  net_revenue_previous_month: number | string
  percentage_change: number | null
  successful_sales_count: number
  average_transaction_value: number | string | null
  gross_revenue: number | string
  vat_collected: number | string
  processing_fees: number | string
  recent_sales: Sale[]
  top_services: TopService[]
  revenue_trend: RevenueTrendPoint[]
  pending_documents_count: number
  pending_documents_total: number | string
  document_failures_count: number
  failed_payments_count: number
  refunds_count: number
  refunds_total: number | string
}
