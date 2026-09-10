export const DOCUMENT_CATEGORIES = [
  'groceries',
  'dining',
  'transport',
  'utilities',
  'health',
  'shopping',
  'entertainment',
  'travel',
  'housing',
  'other',
] as const
export type DocumentCategory = (typeof DOCUMENT_CATEGORIES)[number]

export const SALE_SOURCES = ['manual', 'csv', 'webhook'] as const
export type SaleSource = (typeof SALE_SOURCES)[number]

export const SALE_STATUSES = ['succeeded', 'pending', 'failed', 'refunded', 'partially_refunded'] as const
export type SaleStatus = (typeof SALE_STATUSES)[number]

export const DOCUMENT_STATUSES = ['pending', 'issued', 'failed', 'not_required'] as const
export type DocumentStatus = (typeof DOCUMENT_STATUSES)[number]

export interface Sale {
  id: string
  external_id: string | null
  source_provider: string | null
  source: SaleSource
  status: SaleStatus
  occurred_at: string
  customer_name: string
  customer_contact: string | null
  service_name: string
  description: string | null
  gross_amount: number | string
  vat_amount: number | string | null
  processing_fee: number | string | null
  net_amount: number | string
  refunded_amount: number | string | null
  currency: string
  payment_method: string | null
  document_status: DocumentStatus
  document_number: string | null
  document_url: string | null
  raw_description: string | null
  created_at: string
  updated_at: string
}

export interface SaleInput {
  customer_name: string
  customer_contact?: string | null
  service_name: string
  description?: string | null
  gross_amount: number
  vat_amount?: number | null
  processing_fee?: number | null
  currency: string
  payment_method?: string | null
  occurred_at: string
}

export interface SaleFilters {
  search?: string
  status?: SaleStatus | ''
  date_from?: string
  date_to?: string
}
