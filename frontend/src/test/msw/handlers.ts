import { http, HttpResponse } from 'msw'

import type { Sale } from '../../types/sale'

const API_BASE = 'http://localhost:8000/api'

export const emptyDashboardStats = {
  period: {
    period: 'this_month',
    start_date: '2026-08-01',
    end_date: '2026-08-31',
    previous_start_date: '2026-07-01',
    previous_end_date: '2026-07-31',
    trend_granularity: 'day',
  },
  net_revenue_current_period: [],
  net_revenue_previous_period: [],
  comparison: [],
  successful_sales_count: 0,
  average_transaction_value: [],
  gross_revenue: [],
  vat_collected: [],
  processing_fees: [],
  refunds_total: [],
  recent_sales: [],
  top_services: [],
  revenue_trend: [],
  pending_documents_count: 0,
  document_failures_count: 0,
  failed_payments_count: 0,
  refunds_needing_attention_count: 0,
  incomplete_details_count: 0,
}

export function makeSale(overrides: Partial<Sale> = {}): Sale {
  return {
    id: 'sale-1',
    external_id: null,
    source_provider: null,
    source: 'manual',
    status: 'succeeded',
    occurred_at: '2026-08-20T10:00:00',
    customer_name: 'Dana Cohen',
    customer_contact: 'dana@example.com',
    service_name: 'Consulting session',
    description: null,
    gross_amount: '184.90',
    vat_amount: '26.65',
    tax_treatment: 'standard',
    tax_treatment_needs_review: false,
    vat_rate: '0.1800',
    processing_fee: '5.00',
    net_amount: '153.25',
    refunded_amount: null,
    currency: 'ILS',
    payment_method: null,
    document_status: 'not_required',
    document_number: null,
    document_url: null,
    raw_description: null,
    created_at: '2026-08-20T10:00:00',
    updated_at: '2026-08-20T10:00:00',
    ...overrides,
  }
}

export const handlers = [
  http.get(`${API_BASE}/health`, () => HttpResponse.json({ status: 'ok' })),
  http.get(`${API_BASE}/sales`, () => HttpResponse.json([])),
  http.get(`${API_BASE}/connections`, () => HttpResponse.json([])),
  http.get(`${API_BASE}/assistant/conversations`, () => HttpResponse.json([])),
  http.get(`${API_BASE}/dashboard/stats`, () => HttpResponse.json(emptyDashboardStats)),
  http.get(`${API_BASE}/system/capabilities`, () =>
    HttpResponse.json({
      receipt_extraction_provider: 'mock',
      receipt_extraction_mode: 'demo',
      real_ai_enabled: false,
      ollama_available: null,
      tesseract_available: null,
      demo_simulator_enabled: true,
    }),
  ),
]
