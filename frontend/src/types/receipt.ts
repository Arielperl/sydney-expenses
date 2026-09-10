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

export interface MatchCandidate {
  expense_id: string
  business_name: string
  amount: number | string
  currency: string
  expense_date: string
  score: number
  reasons: string[]
}

export interface ReceiptUploadResponse {
  upload_id: string
  receipt_image_url: string
  extraction_succeeded: boolean
  extracted_data: ExtractedReceiptData | null
  error_message: string | null
  auto_matched: boolean
  matched_expense_id: string | null
  match_reasons: string[]
  suggested_match: MatchCandidate | null
  // Set only when the upload was scoped to a specific expense (?expenseId=).
  attached_to_expense_id: string | null
  conflict: MatchCandidate | null
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
