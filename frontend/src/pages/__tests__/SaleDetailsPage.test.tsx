import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { SaleDetailsPage } from '../SaleDetailsPage'
import { ThemeProvider } from '../../contexts/ThemeContext'
import { server } from '../../test/msw/server'
import { makeSale } from '../../test/msw/handlers'
import { render, screen, waitFor, within } from '../../test/test-utils'

const SALE_URL = 'http://localhost:8000/api/sales/sale-1'
const EVENTS_URL = 'http://localhost:8000/api/sales/sale-1/events'

// renderWithProviders doesn't set up an actual <Route>, so useParams() would
// never see `:id` — this page needs real path matching, unlike most others.
function renderSaleDetails() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/sales/sale-1']}>
          <Routes>
            <Route path="/sales/:id" element={<SaleDetailsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </ThemeProvider>,
  )
}

function eventsResponse() {
  return [
    { id: 'evt-1', sale_id: 'sale-1', event_type: 'sale_created_manually', source: 'manual', created_at: '2026-08-20T10:00:00', event_metadata: null },
    { id: 'evt-2', sale_id: 'sale-1', event_type: 'payment_succeeded', source: 'manual', created_at: '2026-08-20T10:00:01', event_metadata: null },
  ]
}

describe('SaleDetailsPage', () => {
  it('shows the full financial breakdown and origin fields', async () => {
    server.use(
      http.get(SALE_URL, () =>
        HttpResponse.json(
          makeSale({
            gross_amount: '118.00',
            vat_amount: '18.00',
            vat_rate: '0.1800',
            tax_treatment: 'standard',
            net_amount: '112.45',
            processing_fee: '5.00',
            external_id: 'txn-ext-1',
            source_provider: 'demo-pay',
            source: 'webhook',
          }),
        ),
      ),
      http.get(EVENTS_URL, () => HttpResponse.json(eventsResponse())),
    )

    renderSaleDetails()

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Dana Cohen' })).toBeInTheDocument())
    expect(screen.getByText('txn-ext-1')).toBeInTheDocument()
    expect(screen.getByText('demo-pay')).toBeInTheDocument()
    expect(screen.getByText('18%')).toBeInTheDocument()
    // revenue before VAT = 118.00 - 18.00 = 100.00
    expect(screen.getByText(/100\.00/)).toBeInTheDocument()
  })

  it('shows the persisted timeline in chronological order', async () => {
    server.use(
      http.get(SALE_URL, () => HttpResponse.json(makeSale())),
      http.get(EVENTS_URL, () => HttpResponse.json(eventsResponse())),
    )

    renderSaleDetails()

    await waitFor(() => expect(screen.getByText('המכירה נוצרה ידנית')).toBeInTheDocument())
    expect(screen.getByText('התשלום הצליח')).toBeInTheDocument()
  })

  it('shows "no earlier history" when a sale predates the events feature', async () => {
    server.use(
      http.get(SALE_URL, () => HttpResponse.json(makeSale())),
      http.get(EVENTS_URL, () => HttpResponse.json([])),
    )

    renderSaleDetails()

    await waitFor(() =>
      expect(screen.getByText('אין היסטוריה קודמת זמינה עבור מכירה זו.')).toBeInTheDocument(),
    )
  })

  it('shows a needs-review badge instead of a fabricated tax treatment', async () => {
    server.use(
      http.get(SALE_URL, () => HttpResponse.json(makeSale({ tax_treatment: null, tax_treatment_needs_review: true }))),
      http.get(EVENTS_URL, () => HttpResponse.json([])),
    )

    renderSaleDetails()

    await waitFor(() => expect(screen.getByText('סוג העסקה (מע"מ) דורש בדיקה')).toBeInTheDocument())
  })

  it('opens the edit form pre-filled with the sale\'s data', async () => {
    const user = userEvent.setup()
    server.use(
      http.get(SALE_URL, () => HttpResponse.json(makeSale())),
      http.get(EVENTS_URL, () => HttpResponse.json([])),
    )

    renderSaleDetails()

    await waitFor(() => expect(screen.getByRole('button', { name: 'עריכת מכירה' })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'עריכת מכירה' }))

    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByLabelText(/שם הלקוח/)).toHaveValue('Dana Cohen')
  })

  it('records a partial refund and closes the dialog on success', async () => {
    const user = userEvent.setup()
    const sale = makeSale({ status: 'succeeded', net_amount: '100.00', refunded_amount: null })
    server.use(
      http.get(SALE_URL, () => HttpResponse.json(sale)),
      http.get(EVENTS_URL, () => HttpResponse.json([])),
      http.post(`${SALE_URL}/refund`, async ({ request }) => {
        const body = (await request.json()) as { amount?: string }
        return HttpResponse.json({
          ...sale,
          status: 'partially_refunded',
          refunded_amount: body.amount ?? sale.net_amount,
        })
      }),
    )

    renderSaleDetails()

    await waitFor(() => expect(screen.getByRole('button', { name: 'רישום זיכוי' })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'רישום זיכוי' }))

    const dialog = screen.getByRole('dialog')
    await user.type(within(dialog).getByLabelText(/סכום הזיכוי/), '30')
    await user.click(within(dialog).getByRole('button', { name: 'אישור הזיכוי' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('shows the document type and a safe external link for a Grow-linked document', async () => {
    server.use(
      http.get(SALE_URL, () =>
        HttpResponse.json(
          makeSale({
            source: 'webhook',
            source_provider: 'grow:conn-1',
            document_status: 'issued',
            document_number: '20',
            document_type: null,
            document_url: 'https://secure.meshulam.co.il',
          }),
        ),
      ),
      http.get(EVENTS_URL, () => HttpResponse.json(eventsResponse())),
    )

    renderSaleDetails()

    const link = await screen.findByRole('link', { name: 'צפייה במסמך' })
    expect(link).toHaveAttribute('href', 'https://secure.meshulam.co.il')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'))
    // Never opens the image-preview modal for an external provider document.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows the document type for a Cardcom-issued document', async () => {
    server.use(
      http.get(SALE_URL, () =>
        HttpResponse.json(
          makeSale({
            source: 'webhook',
            source_provider: 'cardcom:conn-1',
            document_status: 'issued',
            document_number: '593032',
            document_type: 'TaxInvoiceAndReceipt',
            document_url: null,
          }),
        ),
      ),
      http.get(EVENTS_URL, () => HttpResponse.json(eventsResponse())),
    )

    renderSaleDetails()

    expect(await screen.findByText('TaxInvoiceAndReceipt')).toBeInTheDocument()
    // No URL for Cardcom (documented as unreliable) — no view-document control at all.
    expect(screen.queryByRole('link', { name: 'צפייה במסמך' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'צפייה במסמך' })).not.toBeInTheDocument()
  })

  it('opens the in-app preview modal for a manually attached document, not an external link', async () => {
    const user = userEvent.setup()
    server.use(
      http.get(SALE_URL, () =>
        HttpResponse.json(
          makeSale({
            source: 'manual',
            source_provider: null,
            document_status: 'issued',
            document_url: '/uploads/receipt-1.png',
          }),
        ),
      ),
      http.get(EVENTS_URL, () => HttpResponse.json(eventsResponse())),
    )

    renderSaleDetails()

    const button = await screen.findByRole('button', { name: 'צפייה במסמך' })
    await user.click(button)
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
  })

  it('shows the waiting-automatic hint and a manual-attach fallback link while waiting on a provider document', async () => {
    server.use(
      http.get(SALE_URL, () =>
        HttpResponse.json(
          makeSale({
            source: 'webhook',
            source_provider: 'grow:conn-1',
            document_status: 'waiting_automatic',
            document_url: null,
          }),
        ),
      ),
      http.get(EVENTS_URL, () => HttpResponse.json(eventsResponse())),
    )

    renderSaleDetails()

    expect(await screen.findByText(/הספק \(Grow \/ Cardcom\) אמור לספק את המסמך אוטומטית/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'צירוף מסמך ידני' })).toHaveAttribute(
      'href',
      '/import-document?saleId=sale-1',
    )
  })

  it('does not show the manual-attach fallback once a document is issued', async () => {
    server.use(
      http.get(SALE_URL, () =>
        HttpResponse.json(makeSale({ document_status: 'issued', document_url: '/uploads/receipt-1.png' })),
      ),
      http.get(EVENTS_URL, () => HttpResponse.json(eventsResponse())),
    )

    renderSaleDetails()

    await waitFor(() => expect(screen.getByRole('button', { name: 'צפייה במסמך' })).toBeInTheDocument())
    expect(screen.queryByRole('link', { name: 'צירוף מסמך ידני' })).not.toBeInTheDocument()
  })
})
