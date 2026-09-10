import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { DashboardPage } from '../DashboardPage'
import { server } from '../../test/msw/server'
import { makeSale } from '../../test/msw/handlers'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const STATS_URL = 'http://localhost:8000/api/dashboard/stats'

describe('DashboardPage', () => {
  it('shows the empty state when there are no sales', async () => {
    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('עדיין אין מכירות')).toBeInTheDocument()
    })
  })

  it('shows revenue totals and recent sales when data is present', async () => {
    server.use(
      http.get(STATS_URL, () =>
        HttpResponse.json({
          net_revenue_this_month: '150.00',
          net_revenue_previous_month: '100.00',
          percentage_change: 50,
          successful_sales_count: 3,
          average_transaction_value: '50.00',
          gross_revenue: '180.00',
          vat_collected: '27.00',
          processing_fees: '3.00',
          recent_sales: [makeSale({ gross_amount: '150.00', customer_name: 'Dana Cohen' })],
          top_services: [{ service_name: 'Consulting session', total: '150.00', count: 1 }],
          revenue_trend: [{ period_start: '2026-08-01', total: '150.00' }],
          pending_documents_count: 2,
          pending_documents_total: '80.00',
          document_failures_count: 1,
          failed_payments_count: 1,
          refunds_count: 1,
          refunds_total: '40.00',
        }),
      ),
    )

    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Dana Cohen')).toBeInTheDocument()
    })
    expect(screen.getByText(/50\.0%/)).toBeInTheDocument()
    expect(screen.getByText('2 מכירות ממתינות למסמך')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('1 זיכויים')).toBeInTheDocument()
  })

  it('shows a "no comparison baseline" badge instead of a fabricated percentage when the previous month had no revenue', async () => {
    server.use(
      http.get(STATS_URL, () =>
        HttpResponse.json({
          net_revenue_this_month: '100.00',
          net_revenue_previous_month: '0.00',
          percentage_change: null,
          successful_sales_count: 1,
          average_transaction_value: '100.00',
          gross_revenue: '100.00',
          vat_collected: '0.00',
          processing_fees: '0.00',
          recent_sales: [makeSale({ gross_amount: '100.00', customer_name: 'Dana Cohen' })],
          top_services: [],
          revenue_trend: [],
          pending_documents_count: 0,
          pending_documents_total: '0.00',
          document_failures_count: 0,
          failed_payments_count: 0,
          refunds_count: 0,
          refunds_total: '0.00',
        }),
      ),
    )

    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Dana Cohen')).toBeInTheDocument()
    })
    expect(screen.getByText('אין בסיס להשוואה (בחודש שעבר לא הייתה הכנסה)')).toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })
})
