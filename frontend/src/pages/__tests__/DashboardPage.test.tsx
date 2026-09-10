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
          net_revenue_this_month: [{ currency: 'ILS', amount: '150.00' }],
          net_revenue_previous_month: [{ currency: 'ILS', amount: '100.00' }],
          percentage_change: { ILS: 50 },
          successful_sales_count: 3,
          average_transaction_value: [{ currency: 'ILS', amount: '50.00' }],
          gross_revenue: [{ currency: 'ILS', amount: '180.00' }],
          vat_collected: [{ currency: 'ILS', amount: '27.00' }],
          processing_fees: [{ currency: 'ILS', amount: '3.00' }],
          recent_sales: [makeSale({ gross_amount: '150.00', customer_name: 'Dana Cohen' })],
          top_services: [{ service_name: 'Consulting session', currency: 'ILS', total: '150.00', count: 1 }],
          revenue_trend: [{ period_start: '2026-08-01', currency: 'ILS', total: '150.00' }],
          pending_documents_count: 2,
          pending_documents_total: [{ currency: 'ILS', amount: '80.00' }],
          document_failures_count: 1,
          failed_payments_count: 1,
          refunds_count: 1,
          refunds_total: [{ currency: 'ILS', amount: '40.00' }],
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
          net_revenue_this_month: [{ currency: 'ILS', amount: '100.00' }],
          net_revenue_previous_month: [],
          percentage_change: { ILS: null },
          successful_sales_count: 1,
          average_transaction_value: [{ currency: 'ILS', amount: '100.00' }],
          gross_revenue: [{ currency: 'ILS', amount: '100.00' }],
          vat_collected: [],
          processing_fees: [],
          recent_sales: [makeSale({ gross_amount: '100.00', customer_name: 'Dana Cohen' })],
          top_services: [],
          revenue_trend: [],
          pending_documents_count: 0,
          pending_documents_total: [],
          document_failures_count: 0,
          failed_payments_count: 0,
          refunds_count: 0,
          refunds_total: [],
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

  it('never combines different currencies into one figure', async () => {
    server.use(
      http.get(STATS_URL, () =>
        HttpResponse.json({
          net_revenue_this_month: [
            { currency: 'ILS', amount: '100.00' },
            { currency: 'USD', amount: '30.00' },
          ],
          net_revenue_previous_month: [],
          percentage_change: {},
          successful_sales_count: 2,
          average_transaction_value: [],
          gross_revenue: [],
          vat_collected: [],
          processing_fees: [],
          recent_sales: [makeSale({ gross_amount: '100.00', currency: 'ILS', customer_name: 'Dana Cohen' })],
          top_services: [],
          revenue_trend: [],
          pending_documents_count: 0,
          pending_documents_total: [],
          document_failures_count: 0,
          failed_payments_count: 0,
          refunds_count: 0,
          refunds_total: [],
        }),
      ),
    )

    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Dana Cohen')).toBeInTheDocument()
    })
    // Both currency figures render as separate, clearly-labeled rows.
    expect(screen.getByText('ILS')).toBeInTheDocument()
    expect(screen.getByText('USD')).toBeInTheDocument()
    expect(screen.queryByText('130.00')).not.toBeInTheDocument()
  })
})
