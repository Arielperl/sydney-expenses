import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { SalesPage } from '../SalesPage'
import { server } from '../../test/msw/server'
import { makeSale } from '../../test/msw/handlers'
import { renderWithProviders, screen, waitFor, within } from '../../test/test-utils'

const SALES_URL = 'http://localhost:8000/api/sales'

describe('SalesPage', () => {
  it('shows an "add sale manually" link to the fallback add-sale route', async () => {
    server.use(http.get(SALES_URL, () => HttpResponse.json([])))
    renderWithProviders(<SalesPage />)

    const link = await screen.findByRole('link', { name: 'הוספת מכירה ידנית' })
    expect(link).toHaveAttribute('href', '/add-sale')
  })

  it('lists sales with customer, service, and amount', async () => {
    server.use(http.get(SALES_URL, () => HttpResponse.json([makeSale()])))
    renderWithProviders(<SalesPage />)

    await waitFor(() => expect(screen.getByText('Dana Cohen')).toBeInTheDocument())
    expect(screen.getByText('Consulting session')).toBeInTheDocument()
  })

  it('opens the edit form pre-filled and saves changes', async () => {
    const user = userEvent.setup()
    const sale = makeSale()

    server.use(
      http.get(SALES_URL, () => HttpResponse.json([sale])),
      http.put(`${SALES_URL}/:id`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({ ...sale, ...body })
      }),
    )

    renderWithProviders(<SalesPage />)

    await waitFor(() => expect(screen.getByText('Dana Cohen')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /עריכת Dana Cohen/ }))

    const dialog = screen.getByRole('dialog')
    const customerNameInput = within(dialog).getByLabelText(/שם הלקוח/)
    expect(customerNameInput).toHaveValue('Dana Cohen')

    await user.clear(customerNameInput)
    await user.type(customerNameInput, 'Noa Levi')
    await user.click(within(dialog).getByRole('button', { name: 'שמירת שינויים' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('deletes a sale after confirmation', async () => {
    const user = userEvent.setup()
    const sale = makeSale()
    let deleteCalled = false

    server.use(
      http.get(SALES_URL, () => HttpResponse.json([sale])),
      http.delete(`${SALES_URL}/:id`, () => {
        deleteCalled = true
        return new HttpResponse(null, { status: 204 })
      }),
    )

    renderWithProviders(<SalesPage />)

    await waitFor(() => expect(screen.getByText('Dana Cohen')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /מחיקת Dana Cohen/ }))

    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'מחיקה' }))

    await waitFor(() => expect(deleteCalled).toBe(true))
  })

  it('shows the empty state when no sales match the filters', async () => {
    server.use(http.get(SALES_URL, () => HttpResponse.json([])))
    renderWithProviders(<SalesPage />)

    await waitFor(() => expect(screen.getByText('לא נמצאו מכירות')).toBeInTheDocument())
  })
})
