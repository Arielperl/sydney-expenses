import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { ImportDocumentPage } from '../ImportDocumentPage'
import { server } from '../../test/msw/server'
import { makeSale } from '../../test/msw/handlers'
import { renderWithProviders, screen } from '../../test/test-utils'

const API_BASE = 'http://localhost:8000/api'

function fakeReceiptFile() {
  return new File(['fake-image-bytes'], 'receipt.png', { type: 'image/png' })
}

async function selectFile(user: ReturnType<typeof userEvent.setup>) {
  const fileInput = screen.getByLabelText('בחירת תמונה', { selector: 'input' })
  await user.upload(fileInput, fakeReceiptFile())
}

describe('ImportDocumentPage', () => {
  it('shows an empty state when no sale is targeted', () => {
    renderWithProviders(<ImportDocumentPage />, { route: '/import-document' })
    expect(screen.getByText('לא נבחרה מכירה')).toBeInTheDocument()
  })

  it('fetches and displays the target sale', async () => {
    server.use(
      http.get(`${API_BASE}/sales/sale-1`, () => HttpResponse.json(makeSale({ id: 'sale-1' }))),
    )

    renderWithProviders(<ImportDocumentPage />, { route: '/import-document?saleId=sale-1' })

    expect(await screen.findByText('Dana Cohen')).toBeInTheDocument()
    expect(screen.getByText('מצרפים אל')).toBeInTheDocument()
  })

  it('imports a document and shows the attached confirmation', async () => {
    const user = userEvent.setup()
    server.use(
      http.get(`${API_BASE}/sales/sale-1`, () => HttpResponse.json(makeSale({ id: 'sale-1' }))),
      http.post(`${API_BASE}/documents/import`, () =>
        HttpResponse.json({
          sale_id: 'sale-1',
          document_url: '/uploads/doc-1.png',
          extraction_succeeded: true,
          extracted_data: {
            business_name: 'Cofix',
            receipt_number: 'R-1',
            date: '2026-01-01',
            total: '42.00',
            vat: '6.00',
            currency: 'ILS',
            category: 'dining',
            confidence: 0.8,
            warnings: [],
          },
          error_message: null,
          document_status: 'issued',
          document_number: 'R-1',
        }),
      ),
    )

    renderWithProviders(<ImportDocumentPage />, { route: '/import-document?saleId=sale-1' })
    await screen.findByText('Dana Cohen')
    await selectFile(user)

    expect(await screen.findByText('המסמך צורף')).toBeInTheDocument()
  })

  it('shows an extraction-failed note but still confirms the document was attached', async () => {
    const user = userEvent.setup()
    server.use(
      http.get(`${API_BASE}/sales/sale-1`, () => HttpResponse.json(makeSale({ id: 'sale-1' }))),
      http.post(`${API_BASE}/documents/import`, () =>
        HttpResponse.json({
          sale_id: 'sale-1',
          document_url: '/uploads/doc-1.png',
          extraction_succeeded: false,
          extracted_data: null,
          error_message: 'Document extraction failed: provider unavailable',
          document_status: 'issued',
          document_number: null,
        }),
      ),
    )

    renderWithProviders(<ImportDocumentPage />, { route: '/import-document?saleId=sale-1' })
    await screen.findByText('Dana Cohen')
    await selectFile(user)

    expect(await screen.findByText('המסמך צורף')).toBeInTheDocument()
    expect(
      screen.getByText('לא הצלחנו לקרוא אוטומטית את פרטי המסמך, אך התמונה עצמה נשמרה וצורפה.'),
    ).toBeInTheDocument()
  })
})
