import { http, HttpResponse } from 'msw'

const API_BASE = 'http://localhost:8000/api'

export const emptyDashboardStats = {
  current_month_total: '0.00',
  previous_month_total: '0.00',
  percentage_change: null,
  totals_by_category: [],
  recent_expenses: [],
  missing_documents_count: 0,
  missing_documents_total: '0.00',
  matches_awaiting_confirmation_count: 0,
  document_attachment_rate: null,
}

export function makeExpense(overrides: Record<string, unknown> = {}) {
  return {
    id: 'expense-1',
    business_name: 'Shufersal',
    receipt_number: null,
    amount: '184.90',
    vat_amount: '26.65',
    currency: 'ILS',
    category: 'groceries',
    expense_date: '2026-08-20',
    payment_method: null,
    notes: null,
    receipt_image_url: null,
    extraction_confidence: null,
    extraction_status: 'manual',
    source: 'manual',
    external_id: null,
    source_provider: null,
    raw_description: null,
    occurred_at: null,
    document_status: 'not_required',
    reconciliation_confidence: null,
    reconciliation_reasons: null,
    created_at: '2026-08-20T10:00:00',
    updated_at: '2026-08-20T10:00:00',
    ...overrides,
  }
}

export function makeUnassignedDocument(overrides: Record<string, unknown> = {}) {
  return {
    id: 'upload-1',
    received_at: '2026-08-20T10:00:00',
    preview_url: '/uploads/upload-1.png',
    extracted_business_name: 'Cofix',
    extracted_total: '42.50',
    extracted_vat: '6.15',
    extracted_currency: 'ILS',
    extracted_date: '2026-08-20',
    extracted_receipt_number: 'R-500',
    extracted_category: 'dining',
    extraction_confidence: 0.8,
    extraction_warnings: [],
    ...overrides,
  }
}

export const handlers = [
  http.get(`${API_BASE}/health`, () => HttpResponse.json({ status: 'ok' })),
  http.get(`${API_BASE}/expenses`, () => HttpResponse.json([])),
  http.get(`${API_BASE}/dashboard/stats`, () => HttpResponse.json(emptyDashboardStats)),
  http.get(`${API_BASE}/system/capabilities`, () =>
    HttpResponse.json({
      receipt_extraction_provider: 'mock',
      receipt_extraction_mode: 'demo',
      real_ai_enabled: false,
      ollama_available: null,
      tesseract_available: null,
    }),
  ),
]
