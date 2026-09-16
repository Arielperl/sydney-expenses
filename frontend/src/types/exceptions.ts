import type { Sale } from './sale'

export interface ExceptionCenter {
  attention_count: number
  pending_documents_count: number
  document_failures_count: number
  refunds_needing_attention_count: number
  incomplete_details_count: number
  pending_documents: Sale[]
  document_failures: Sale[]
  refunds_needing_attention: Sale[]
  incomplete_details: Sale[]
}
