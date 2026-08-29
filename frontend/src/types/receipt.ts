import type { ExpenseCategory } from './expense'

export interface ExtractedReceiptData {
  business_name: string | null
  receipt_number: string | null
  date: string | null
  total: number | string | null
  vat: number | string | null
  currency: string
  category: ExpenseCategory
  confidence: number
  warnings: string[]
}

export interface ReceiptUploadResponse {
  upload_id: string
  receipt_image_url: string
  extraction_succeeded: boolean
  extracted_data: ExtractedReceiptData | null
  error_message: string | null
}

export interface ReceiptConfirmInput {
  upload_id: string
  business_name: string
  receipt_number?: string | null
  amount: number
  vat_amount?: number | null
  currency: string
  category: ExpenseCategory
  expense_date: string
  payment_method?: string | null
  notes?: string | null
  extraction_confidence?: number | null
}
