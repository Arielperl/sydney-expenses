import type { Expense, ExpenseCategory } from './expense'

export interface ReconciliationInbox {
  missing_documents: Expense[]
  suggested_matches: Expense[]
  documents_without_transactions: Expense[]
  needs_review: Expense[]
  recently_completed: Expense[]
}

export interface ApproveMatchInput {
  vat_amount?: number | null
  receipt_number?: string | null
  category?: ExpenseCategory | null
}

export interface MatchDecisionResponse {
  expense: Expense
}
