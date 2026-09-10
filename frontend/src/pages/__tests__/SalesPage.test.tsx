import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import i18n from '../../i18n'
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

  it('opens the edit dialog with "card" selected for an existing credit-card sale', async () => {
    const user = userEvent.setup()
    const sale = makeSale({ payment_method: 'card' })
    server.use(http.get(SALES_URL, () => HttpResponse.json([sale])))

    renderWithProviders(<SalesPage />)

    await waitFor(() => expect(screen.getByText('Dana Cohen')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /עריכת Dana Cohen/ }))

    const dialog = screen.getByRole('dialog')
    const select = within(dialog).getByLabelText('אמצעי תשלום') as HTMLSelectElement
    expect(select).toHaveValue('card')
    expect(within(select).getByRole('option', { name: 'כרטיס אשראי', selected: true })).toBeInTheDocument()
  })

  it('changing payment method to "cash" sends payment_method: "cash" in the update request', async () => {
    const user = userEvent.setup()
    const sale = makeSale({ payment_method: 'card' })
    let capturedBody: Record<string, unknown> | null = null

    server.use(
      http.get(SALES_URL, () => HttpResponse.json([sale])),
      http.put(`${SALES_URL}/:id`, async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({ ...sale, ...capturedBody })
      }),
    )

    renderWithProviders(<SalesPage />)

    await waitFor(() => expect(screen.getByText('Dana Cohen')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /עריכת Dana Cohen/ }))

    const dialog = screen.getByRole('dialog')
    const select = within(dialog).getByLabelText('אמצעי תשלום')
    await user.selectOptions(select, 'cash')
    await user.click(within(dialog).getByRole('button', { name: 'שמירת שינויים' }))

    await waitFor(() => expect(capturedBody).toMatchObject({ payment_method: 'cash' }))
  })

  it('normalizes an unknown legacy payment_method to "other" instead of crashing the edit form', async () => {
    const user = userEvent.setup()
    const sale = makeSale({ payment_method: 'bit' })
    server.use(http.get(SALES_URL, () => HttpResponse.json([sale])))

    renderWithProviders(<SalesPage />)

    await waitFor(() => expect(screen.getByText('Dana Cohen')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /עריכת Dana Cohen/ }))

    const dialog = screen.getByRole('dialog')
    const select = within(dialog).getByLabelText('אמצעי תשלום') as HTMLSelectElement
    expect(select).toHaveValue('other')
  })

  it('renders a webhook-created sale with payment_method "card" correctly', async () => {
    const sale = makeSale({ source: 'webhook', payment_method: 'card', source_provider: 'demo-pay' })
    server.use(http.get(SALES_URL, () => HttpResponse.json([sale])))

    renderWithProviders(<SalesPage />)

    await waitFor(() => expect(screen.getByText('Dana Cohen')).toBeInTheDocument())
    expect(screen.getByText('ספק תשלומים')).toBeInTheDocument()
  })

  it('renders Hebrew and English payment method option labels correctly', async () => {
    const user = userEvent.setup()
    const sale = makeSale({ payment_method: 'card' })
    server.use(http.get(SALES_URL, () => HttpResponse.json([sale])))

    const { unmount } = renderWithProviders(<SalesPage />)
    await waitFor(() => expect(screen.getByText('Dana Cohen')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /עריכת Dana Cohen/ }))
    let dialog = screen.getByRole('dialog')
    let select = within(dialog).getByLabelText('אמצעי תשלום')
    expect(within(select).getByRole('option', { name: 'כרטיס אשראי' })).toBeInTheDocument()
    expect(within(select).getByRole('option', { name: 'מזומן' })).toBeInTheDocument()
    expect(within(select).getByRole('option', { name: 'אחר' })).toBeInTheDocument()
    unmount()

    await i18n.changeLanguage('en')
    renderWithProviders(<SalesPage />)
    await waitFor(() => expect(screen.getByText('Dana Cohen')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /Edit Dana Cohen/ }))
    dialog = screen.getByRole('dialog')
    select = within(dialog).getByLabelText('Payment method')
    expect(within(select).getByRole('option', { name: 'Credit card' })).toBeInTheDocument()
    expect(within(select).getByRole('option', { name: 'Cash' })).toBeInTheDocument()
    expect(within(select).getByRole('option', { name: 'Other' })).toBeInTheDocument()
  })
})
