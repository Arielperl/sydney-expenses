import { http, HttpResponse } from 'msw'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { ExceptionCenterPage } from '../ExceptionCenterPage'
import { server } from '../../test/msw/server'
import { makeSale } from '../../test/msw/handlers'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const EXCEPTIONS_URL = 'http://localhost:8000/api/exceptions'

function emptyExceptionCenter() {
  return {
    attention_count: 0,
    pending_documents_count: 0,
    document_failures_count: 0,
    refunds_needing_attention_count: 0,
    incomplete_details_count: 0,
    pending_documents: [],
    document_failures: [],
    refunds_needing_attention: [],
    incomplete_details: [],
  }
}

describe('ExceptionCenterPage', () => {
  it('shows one clear empty state instead of four empty sections', async () => {
    server.use(http.get(EXCEPTIONS_URL, () => HttpResponse.json(emptyExceptionCenter())))
    renderWithProviders(<ExceptionCenterPage />)

    expect(await screen.findByText('אין מכירות שממתינות לטיפול בסינון הזה')).toBeInTheDocument()
    expect(screen.getByText('כל מכירה נספרת פעם אחת, גם אם יש בה יותר מבעיה אחת.')).toBeInTheDocument()
  })

  it('does not show missing or failed documents as attention tasks', async () => {
    const sale = makeSale({ id: 'sale-pending', document_status: 'pending', status: 'succeeded' })
    server.use(http.get(EXCEPTIONS_URL, () => HttpResponse.json({
      ...emptyExceptionCenter(), attention_count: 1, pending_documents_count: 1, pending_documents: [sale],
    })))
    renderWithProviders(<ExceptionCenterPage />)

    expect(await screen.findByText('אין מכירות שממתינות לטיפול בסינון הזה')).toBeInTheDocument()
    expect(screen.queryByText('Dana Cohen')).not.toBeInTheDocument()
  })

  it('does not turn an already recorded refund into a permanent task', async () => {
    const sale = makeSale({ id: 'sale-refund', status: 'refunded' })
    server.use(http.get(EXCEPTIONS_URL, () => HttpResponse.json({
      ...emptyExceptionCenter(), refunds_needing_attention: [sale], refunds_needing_attention_count: 1,
    })))
    renderWithProviders(<ExceptionCenterPage />)

    expect(await screen.findByText('אין מכירות שממתינות לטיפול בסינון הזה')).toBeInTheDocument()
    expect(screen.queryByText('Dana Cohen')).not.toBeInTheDocument()
  })

  it('links an ambiguous VAT treatment directly to its sale', async () => {
    const sale = makeSale({ id: 'sale-tax', tax_treatment_needs_review: true })
    server.use(http.get(EXCEPTIONS_URL, () => HttpResponse.json({
      ...emptyExceptionCenter(), attention_count: 1, incomplete_details_count: 1, incomplete_details: [sale],
    })))
    renderWithProviders(<ExceptionCenterPage />)

    expect(await screen.findByText('Dana Cohen')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'פרטי מכירה' })).toHaveAttribute('href', '/sales/sale-tax')
    expect(screen.getByText(/לא ניתן היה לקבוע בבטחה את סוג המע״מ/)).toBeInTheDocument()
  })

  it('loads more results in the selected list', async () => {
    const sales = Array.from({ length: 21 }, (_, index) => makeSale({
      id: `sale-${index}`, customer_name: `Customer ${index}`, tax_treatment_needs_review: true,
    }))
    server.use(http.get(EXCEPTIONS_URL, ({ request }) => {
      const limit = Number(new URL(request.url).searchParams.get('limit') ?? 20)
      return HttpResponse.json({
        ...emptyExceptionCenter(), attention_count: 21, incomplete_details_count: 21,
        incomplete_details: sales.slice(0, limit),
      })
    }))
    renderWithProviders(<ExceptionCenterPage />)

    await waitFor(() => expect(screen.getByText('מוצגות 20 מתוך 21')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: 'הצגת עוד' }))
    await waitFor(() => expect(screen.getByText('מוצגות 21 מתוך 21')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'הצגת עוד' })).not.toBeInTheDocument()
  })
})
