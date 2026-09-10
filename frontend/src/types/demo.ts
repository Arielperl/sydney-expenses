import type { PaymentMethod, Sale, TaxTreatment, TransactionCurrency } from './sale'

export const DEMO_SCENARIOS = [
  'succeeded',
  'pending',
  'failed',
  'succeeded_document_failed',
  'succeeded_partial_refund',
  'succeeded_full_refund',
] as const
export type DemoScenario = (typeof DEMO_SCENARIOS)[number]

export interface DemoSimulationInput {
  customer_name: string
  customer_contact?: string | null
  service_name: string
  gross_amount: number
  currency: TransactionCurrency
  payment_method?: PaymentMethod | null
  tax_treatment: TaxTreatment
  scenario: DemoScenario
}

export interface DemoSimulationResult {
  sale: Sale
  scenario: DemoScenario
}

export interface DemoResetPreview {
  demo_sales_count: number
}

export interface DemoResetResult {
  deleted_sales_count: number
  deleted_events_count: number
}
