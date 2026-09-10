import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { ExceptionCenterPage } from '../ExceptionCenterPage'
import { server } from '../../test/msw/server'
import { makeSale } from '../../test/msw/handlers'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const EXCEPTIONS_URL = 'http://localhost:8000/api/exceptions'

function emptyExceptionCenter() {
  return {
    pending_documents: [],
    document_failures: [],
    refunds_needing_attention: [],
    incomplete_details: [],
  }
}

describe('ExceptionCenterPage', () => {
  it('shows empty-state copy when every section is empty', async () => {
    server.use(http.get(EXCEPTIONS_URL, () => HttpResponse.json(emptyExceptionCenter())))
    renderWithProviders(<ExceptionCenterPage />)

    await waitFor(() => expect(screen.getByText('לכל מכירה מוצלחת יש מסמך')).toBeInTheDocument())
    expect(screen.getByText('אין כשלים בהפקת מסמכים')).toBeInTheDocument()
    expect(screen.getByText('אין זיכויים הדורשים תשומת לב')).toBeInTheDocument()
    expect(screen.getByText('לכל המכירות יש פרטי לקוח מלאים')).toBeInTheDocument()
  })

  it('lists a sale awaiting a document with an import-document link', async () => {
    const sale = makeSale({ id: 'sale-pending', document_status: 'pending', status: 'succeeded' })
    server.use(
      http.get(EXCEPTIONS_URL, () => HttpResponse.json({ ...emptyExceptionCenter(), pending_documents: [sale] })),
    )
    renderWithProviders(<ExceptionCenterPage />)

    await waitFor(() => expect(screen.getByText('Dana Cohen')).toBeInTheDocument())
    const link = screen.getByRole('link', { name: 'ייבוא מסמך' })
    expect(link).toHaveAttribute('href', '/import-document?saleId=sale-pending')
  })

  it('lists a refund needing attention without an action link', async () => {
    const sale = makeSale({ id: 'sale-refund', status: 'refunded' })
    server.use(
      http.get(EXCEPTIONS_URL, () =>
        HttpResponse.json({ ...emptyExceptionCenter(), refunds_needing_attention: [sale] }),
      ),
    )
    renderWithProviders(<ExceptionCenterPage />)

    await waitFor(() => expect(screen.getByText('Dana Cohen')).toBeInTheDocument())
    expect(screen.queryByRole('link', { name: 'ייבוא מסמך' })).not.toBeInTheDocument()
  })

  it('lists a sale with incomplete details and an edit-in-sales link', async () => {
    const sale = makeSale({ id: 'sale-incomplete', customer_contact: null })
    server.use(
      http.get(EXCEPTIONS_URL, () => HttpResponse.json({ ...emptyExceptionCenter(), incomplete_details: [sale] })),
    )
    renderWithProviders(<ExceptionCenterPage />)

    await waitFor(() => expect(screen.getByText('Dana Cohen')).toBeInTheDocument())
    const link = screen.getByRole('link', { name: 'עריכה במכירות' })
    expect(link).toHaveAttribute('href', '/sales')
  })
})
