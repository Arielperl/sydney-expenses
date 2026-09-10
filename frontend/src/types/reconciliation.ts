import type { Expense, ExpenseCategory } from './expense'

export interface UnassignedDocument {
  id: string
  received_at: string
  preview_url: string | null
  extracted_business_name: string | null
  extracted_total: number | string | null
  extracted_vat: number | string | null
  extracted_currency: string | null
  extracted_date: string | null
  extracted_receipt_number: string | null
  extracted_category: ExpenseCategory | null
  extraction_confidence: number | null
  extraction_warnings: string[]
}

export interface SuggestedMatch {
  expense: Expense
  document: UnassignedDocument | null
}

export interface ReconciliationInbox {
  missing_documents: Expense[]
  suggested_matches: SuggestedMatch[]
  documents_without_transactions: UnassignedDocument[]
  needs_review: Expense[]
  recently_completed: Expense[]
}

export interface MatchDecisionResponse {
  expense: Expense
}

export interface EligibleExpense {
  expense: Expense
  score: number
  reasons: string[]
  has_conflict: boolean
}

export interface RematchResponse {
  decision: 'auto_match' | 'needs_review' | 'suggested' | 'no_match'
  expense: Expense | null
  reasons: string[]
}
