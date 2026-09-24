import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { DashboardPage } from '../DashboardPage'
import { server } from '../../test/msw/server'
import { emptyDashboardStats, makeSale } from '../../test/msw/handlers'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const STATS_URL = 'http://localhost:8000/api/dashboard/stats'

describe('DashboardPage', () => {
  it('shows the primary metric and needs-attention all-clear state when there are no sales', async () => {
    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('הכול תקין — אין מכירות שממתינות לטיפול')).toBeInTheDocument()
    })
    expect(screen.getByText('עדיין אין מכירות — הוסיפו את הראשונה כדי לראות אותה כאן.')).toBeInTheDocument()
  })

  it('shows revenue totals, comparison, and recent sales when data is present', async () => {
    server.use(
      http.get(STATS_URL, () =>
        HttpResponse.json({
          ...emptyDashboardStats,
          net_revenue_current_period: [{ currency: 'ILS', amount: '150.00' }],
          net_revenue_previous_period: [{ currency: 'ILS', amount: '100.00' }],
          comparison: [{ currency: 'ILS', percentage_change: 50, amount_change: '50.00' }],
          successful_sales_count: 3,
          average_transaction_value: [{ currency: 'ILS', amount: '50.00' }],
          gross_revenue: [{ currency: 'ILS', amount: '180.00' }],
          vat_collected: [{ currency: 'ILS', amount: '27.00' }],
          processing_fees: [{ currency: 'ILS', amount: '3.00' }],
          recent_sales: [makeSale({ gross_amount: '150.00', customer_name: 'Dana Cohen' })],
          top_services: [
            { service_name: 'Consulting session', currency: 'ILS', total: '150.00', count: 1, percentage_of_revenue: 100 },
          ],
          revenue_trend: [{ period_start: '2026-08-01', currency: 'ILS', gross_total: '180.00', net_total: '150.00' }],
          pending_documents_count: 2,
          document_failures_count: 1,
          failed_payments_count: 1,
          refunds_needing_attention_count: 1,
          incomplete_details_count: 0,
        }),
      ),
    )

    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Dana Cohen')).toBeInTheDocument()
    })
    expect(screen.getByText(/50\.0%/)).toBeInTheDocument()
    expect(screen.getByText('2 מכירות ממתינות למסמך')).toBeInTheDocument()
    expect(screen.queryByText('1 זיכויים דורשים טיפול')).not.toBeInTheDocument()
  })

  it('shows a "not enough data" badge instead of a fabricated percentage when there is no previous-period baseline', async () => {
    server.use(
      http.get(STATS_URL, () =>
        HttpResponse.json({
          ...emptyDashboardStats,
          net_revenue_current_period: [{ currency: 'ILS', amount: '100.00' }],
          successful_sales_count: 1,
          average_transaction_value: [{ currency: 'ILS', amount: '100.00' }],
          gross_revenue: [{ currency: 'ILS', amount: '100.00' }],
          recent_sales: [makeSale({ gross_amount: '100.00', customer_name: 'Dana Cohen' })],
        }),
      ),
    )

    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Dana Cohen')).toBeInTheDocument()
    })
    expect(screen.getByText('אין עדיין מספיק נתונים להשוואה')).toBeInTheDocument()
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
  })

  it('never combines different currencies into one figure', async () => {
    server.use(
      http.get(STATS_URL, () =>
        HttpResponse.json({
          ...emptyDashboardStats,
          net_revenue_current_period: [
            { currency: 'ILS', amount: '100.00' },
            { currency: 'USD', amount: '30.00' },
          ],
          successful_sales_count: 2,
          recent_sales: [makeSale({ gross_amount: '100.00', currency: 'ILS', customer_name: 'Dana Cohen' })],
        }),
      ),
    )

    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Dana Cohen')).toBeInTheDocument()
    })
    // Both currency figures render as separate, clearly-labeled rows.
    expect(screen.getAllByText('ILS').length).toBeGreaterThan(0)
    expect(screen.getAllByText('USD').length).toBeGreaterThan(0)
    expect(screen.queryByText('130.00')).not.toBeInTheDocument()
  })
  it('explains an inverted custom range instead of requesting it', async () => {
    let requested = false
    server.use(http.get(STATS_URL, () => { requested = true; return HttpResponse.json(emptyDashboardStats) }))
    renderWithProviders(<DashboardPage />, { route: '/app?period=custom&custom_start=2026-09-30&custom_end=2026-01-01' })

    expect(await screen.findByText('תאריך הסיום מוקדם מתאריך ההתחלה')).toBeInTheDocument()
    expect(requested).toBe(false)
  })

  it('defines net receipts honestly and never presents them as profit or a balance', async () => {
    server.use(http.get(STATS_URL, () => HttpResponse.json({
      ...emptyDashboardStats,
      net_revenue_current_period: [{ currency: 'ILS', amount: '840.00' }],
      net_revenue_previous_period: [{ currency: 'ILS', amount: '700.00' }],
      comparison: [{ currency: 'ILS', percentage_change: 20, amount_change: '140.00' }],
      gross_revenue: [{ currency: 'ILS', amount: '1180.00' }],
      successful_sales_count: 2,
    })))
    renderWithProviders(<DashboardPage />)

    expect(await screen.findByText(/אינו רווח ואינו יתרה בחשבון הבנק/)).toBeInTheDocument()
    expect(screen.queryByText(/^יתרה/)).not.toBeInTheDocument()
    // The comparison names the actual previous range, not just "previous period".
    expect(screen.getByText(/20\.0%/)).toBeInTheDocument()
    expect(screen.getByText(/לעומת 1 ביולי 2026/)).toBeInTheDocument()
    // The breakdown explains why its rows are not a line-by-line subtraction.
    expect(screen.getByText(/אינם חיסור שורה אחר שורה/)).toBeInTheDocument()
  })
})
