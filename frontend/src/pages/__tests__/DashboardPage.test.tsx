import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { DashboardPage } from '../DashboardPage'
import { server } from '../../test/msw/server'
import { makeExpense } from '../../test/msw/handlers'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const STATS_URL = 'http://localhost:8000/api/dashboard/stats'

describe('DashboardPage', () => {
  it('shows the empty state when there are no expenses', async () => {
    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('עדיין אין הוצאות')).toBeInTheDocument()
    })
  })

  it('shows totals and recent expenses when data is present', async () => {
    server.use(
      http.get(STATS_URL, () =>
        HttpResponse.json({
          current_month_total: '150.00',
          previous_month_total: '100.00',
          percentage_change: 50,
          totals_by_category: [{ category: 'groceries', total: '150.00' }],
          recent_expenses: [makeExpense({ amount: '150.00' })],
        }),
      ),
    )

    renderWithProviders(<DashboardPage />)

    await waitFor(() => {
      expect(screen.getByText('Shufersal')).toBeInTheDocument()
    })
    expect(screen.getByText(/50\.0%/)).toBeInTheDocument()
  })
})
