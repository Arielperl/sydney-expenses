import { http, HttpResponse } from 'msw'

const API_BASE = 'http://localhost:8000/api'

export const emptyDashboardStats = {
  current_month_total: '0.00',
  previous_month_total: '0.00',
  percentage_change: null,
  totals_by_category: [],
  recent_expenses: [],
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
    created_at: '2026-08-20T10:00:00',
    updated_at: '2026-08-20T10:00:00',
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
