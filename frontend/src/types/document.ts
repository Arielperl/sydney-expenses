import type { DocumentCategory } from './sale'

export interface ExtractedDocumentData {
  business_name: string | null
  receipt_number: string | null
  date: string | null
  total: number | string | null
  vat: number | string | null
  currency: string
  category: DocumentCategory
  confidence: number
  warnings: string[]
}

export interface DocumentImportResponse {
  sale_id: string
  document_url: string
  extraction_succeeded: boolean
  extracted_data: ExtractedDocumentData | null
  error_message: string | null
  document_status: string
  document_number: string | null
}
