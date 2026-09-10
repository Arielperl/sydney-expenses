import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { AddSalePage } from '../AddSalePage'
import { server } from '../../test/msw/server'
import { makeSale } from '../../test/msw/handlers'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const SALES_URL = 'http://localhost:8000/api/sales'

describe('AddSalePage', () => {
  it('creates a sale manually with customer and service info', async () => {
    let capturedBody: Record<string, unknown> | null = null
    server.use(
      http.post(SALES_URL, async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(makeSale({ customer_name: 'Noa Levi', service_name: 'Design package' }), {
          status: 201,
        })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<AddSalePage />)

    await user.type(screen.getByLabelText(/שם הלקוח/), 'Noa Levi')
    await user.type(screen.getByLabelText(/מוצר או שירות/), 'Design package')
    const amountInput = screen.getByLabelText(/סכום שחויב/)
    await user.clear(amountInput)
    await user.type(amountInput, '250')

    await user.click(screen.getByRole('button', { name: 'שמירת המכירה' }))

    await waitFor(() => expect(screen.getByText('המכירה נשמרה. מעביר אתכם לרשימת המכירות...')).toBeInTheDocument())
    expect(capturedBody).toMatchObject({ customer_name: 'Noa Levi', service_name: 'Design package', gross_amount: 250 })
  })

  it('shows a validation error when required fields are missing', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AddSalePage />)

    await user.click(screen.getByRole('button', { name: 'שמירת המכירה' }))

    expect(await screen.findByText('שם הלקוח הוא שדה חובה')).toBeInTheDocument()
  })
})
