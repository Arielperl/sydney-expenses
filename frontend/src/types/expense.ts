export const EXPENSE_CATEGORIES = [
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

export type ExpenseCategory = (typeof EXPENSE_CATEGORIES)[number]

export const EXTRACTION_STATUSES = ['manual', 'pending', 'extracted', 'confirmed', 'failed'] as const

export type ExtractionStatus = (typeof EXTRACTION_STATUSES)[number]

export interface Expense {
  id: string
  business_name: string
  receipt_number: string | null
  amount: number | string
  vat_amount: number | string | null
  currency: string
  category: ExpenseCategory
  expense_date: string
  payment_method: string | null
  notes: string | null
  receipt_image_url: string | null
  extraction_confidence: number | null
  extraction_status: ExtractionStatus
  created_at: string
  updated_at: string
}

export interface ExpenseInput {
  business_name: string
  receipt_number?: string | null
  amount: number
  vat_amount?: number | null
  currency: string
  category: ExpenseCategory
  expense_date: string
  payment_method?: string | null
  notes?: string | null
}

export interface ExpenseFilters {
  search?: string
  category?: ExpenseCategory | ''
  date_from?: string
  date_to?: string
}
