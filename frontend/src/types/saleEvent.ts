export const SALE_EVENT_TYPES = [
  'sale_received',
  'sale_created_manually',
  'sale_imported_from_csv',
  'payment_succeeded',
  'payment_pending',
  'payment_failed',
  'document_issuance_attempted',
  'document_issued',
  'document_issuance_failed',
  'refund_partial',
  'refund_full',
  'sale_details_edited',
] as const
export type SaleEventType = (typeof SALE_EVENT_TYPES)[number]

export const SALE_EVENT_SOURCES = ['manual', 'webhook', 'csv', 'demo', 'system'] as const
export type SaleEventSourceType = (typeof SALE_EVENT_SOURCES)[number]

export interface SaleEvent {
  id: string
  sale_id: string
  event_type: SaleEventType
  source: SaleEventSourceType
  created_at: string
  event_metadata: Record<string, unknown> | null
}
