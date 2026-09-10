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

export const PAYMENT_METHODS = ['card', 'cash', 'other'] as const
export type PaymentMethod = (typeof PAYMENT_METHODS)[number]

// The closed set of transaction currencies selectable through the Sale
// form — see backend app/domain/demo_business.py. Currency is never the
// same thing as tax jurisdiction: this demo business is always taxed under
// Israeli VAT rules regardless of which of these a given sale is charged in.
export const TRANSACTION_CURRENCIES = ['ILS', 'USD', 'EUR'] as const
export type TransactionCurrency = (typeof TRANSACTION_CURRENCIES)[number]

// How Israeli VAT applies to a sale — see backend app/models/sale.py's
// TaxTreatment docstring. `standard` is the default; `zero_rate` and
// `exempt` both always produce vat_amount = 0.
export const TAX_TREATMENTS = ['standard', 'zero_rate', 'exempt'] as const
export type TaxTreatment = (typeof TAX_TREATMENTS)[number]

export const SALE_SOURCES = ['manual', 'csv', 'webhook', 'demo'] as const
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
  // Null only for a legacy sale a data migration couldn't safely classify
  // (see the backend migration's docstring) — every sale created going
  // forward always has a concrete value.
  tax_treatment: TaxTreatment | null
  tax_treatment_needs_review: boolean
  vat_rate: number | string | null
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
  // vat_amount is deliberately absent: it is always backend-computed from
  // gross_amount + tax_treatment, never client-supplied — see SaleForm.
  tax_treatment?: TaxTreatment
  processing_fee?: number | null
  currency: TransactionCurrency | string
  payment_method?: PaymentMethod | null
  occurred_at: string
}

export interface SaleFilters {
  search?: string
  status?: SaleStatus | ''
  date_from?: string
  date_to?: string
}
