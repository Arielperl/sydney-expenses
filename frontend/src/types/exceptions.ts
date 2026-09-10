import type { Sale } from './sale'

export interface ExceptionCenter {
  pending_documents: Sale[]
  document_failures: Sale[]
  refunds_needing_attention: Sale[]
  incomplete_details: Sale[]
}
