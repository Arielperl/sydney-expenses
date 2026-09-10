import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { ReconciliationInboxPage } from '../ReconciliationInboxPage'
import { server } from '../../test/msw/server'
import { makeExpense, makeUnassignedDocument } from '../../test/msw/handlers'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const API_BASE = 'http://localhost:8000/api'
const INBOX_URL = `${API_BASE}/reconciliation/inbox`

function emptyInbox() {
  return {
    missing_documents: [],
    suggested_matches: [],
    documents_without_transactions: [],
    needs_review: [],
    recently_completed: [],
  }
}

describe('ReconciliationInboxPage', () => {
  it('shows empty-state copy when every section is empty', async () => {
    server.use(http.get(INBOX_URL, () => HttpResponse.json(emptyInbox())))
    renderWithProviders(<ReconciliationInboxPage />)

    await waitFor(() => {
      expect(screen.getByText('אין עסקאות שחסר להן מסמך')).toBeInTheDocument()
    })
    expect(screen.getByText('אין התאמות שממתינות לאישור')).toBeInTheDocument()
    expect(screen.getByText('כל הקבלות משויכות לעסקה')).toBeInTheDocument()
    expect(screen.getByText('עדיין לא הושלמו התאמות')).toBeInTheDocument()
  })

  it('lists a missing-document transaction with an attach-receipt link', async () => {
    const missing = makeExpense({ id: 'missing-1', document_status: 'missing' })
    server.use(http.get(INBOX_URL, () => HttpResponse.json({ ...emptyInbox(), missing_documents: [missing] })))

    renderWithProviders(<ReconciliationInboxPage />)

    await waitFor(() => expect(screen.getByText('Shufersal')).toBeInTheDocument())
    expect(screen.getByText('חסר מסמך')).toBeInTheDocument()
    const attachLink = screen.getByRole('link', { name: 'צרפו קבלה' })
    expect(attachLink).toHaveAttribute('href', '/upload-receipt?expenseId=missing-1')
  })

  it('shows both the transaction and the receipt side of a suggested match', async () => {
    const suggested = makeExpense({
      id: 'suggested-1',
      document_status: 'suggested',
      reconciliation_confidence: 0.7,
      reconciliation_reasons: ['same_amount', 'date_same_day'],
    })
    const document = makeUnassignedDocument({ id: 'doc-1', extracted_business_name: 'Cofix' })
    server.use(
      http.get(INBOX_URL, () =>
        HttpResponse.json({ ...emptyInbox(), suggested_matches: [{ expense: suggested, document }] }),
      ),
    )

    renderWithProviders(<ReconciliationInboxPage />)

    await waitFor(() => expect(screen.getByText('70% התאמה')).toBeInTheDocument())
    expect(screen.getByText('Shufersal')).toBeInTheDocument()
    expect(screen.getByText('Cofix')).toBeInTheDocument()
  })

  it('approving a suggested match calls the approve endpoint and refreshes the inbox', async () => {
    const suggested = makeExpense({
      id: 'suggested-1',
      document_status: 'suggested',
      reconciliation_confidence: 0.7,
      reconciliation_reasons: ['same_amount', 'date_same_day'],
    })
    let approveCalled = false
    server.use(
      http.get(INBOX_URL, () =>
        HttpResponse.json({ ...emptyInbox(), suggested_matches: [{ expense: suggested, document: null }] }),
      ),
      http.post(`${API_BASE}/reconciliation/matches/suggested-1/approve`, () => {
        approveCalled = true
        return HttpResponse.json({ expense: { ...suggested, document_status: 'attached' } })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<ReconciliationInboxPage />)

    await waitFor(() => expect(screen.getByText('70% התאמה')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'אישור ההתאמה' }))

    await waitFor(() => expect(approveCalled).toBe(true))
  })

  it('rejecting a suggested match calls the reject endpoint', async () => {
    const suggested = makeExpense({ id: 'suggested-2', document_status: 'suggested', reconciliation_confidence: 0.6 })
    let rejectCalled = false
    server.use(
      http.get(INBOX_URL, () =>
        HttpResponse.json({ ...emptyInbox(), suggested_matches: [{ expense: suggested, document: null }] }),
      ),
      http.post(`${API_BASE}/reconciliation/matches/suggested-2/reject`, () => {
        rejectCalled = true
        return HttpResponse.json({ expense: { ...suggested, document_status: 'missing' } })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<ReconciliationInboxPage />)

    await waitFor(() => expect(screen.getByRole('button', { name: 'דחיית ההתאמה' })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'דחיית ההתאמה' }))

    await waitFor(() => expect(rejectCalled).toBe(true))
  })

  it('renders an unassigned document with its preview/extracted fields and all four actions', async () => {
    const document = makeUnassignedDocument()
    server.use(
      http.get(INBOX_URL, () =>
        HttpResponse.json({ ...emptyInbox(), documents_without_transactions: [document] }),
      ),
    )

    renderWithProviders(<ReconciliationInboxPage />)

    await waitFor(() => expect(screen.getByText('Cofix')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'חיפוש התאמות מחדש' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'בחירת עסקה ידנית' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'קליטת מסמך' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'מחיקת המסמך' })).toBeInTheDocument()
  })

  it('rejecting a suggested match makes its receipt reappear in the unassigned-documents section without a page reload', async () => {
    const suggested = makeExpense({ id: 'suggested-3', document_status: 'suggested', reconciliation_confidence: 0.6 })
    const document = makeUnassignedDocument({ id: 'doc-3', extracted_business_name: 'Cofix' })
    let rejected = false
    server.use(
      http.get(INBOX_URL, () => {
        if (!rejected) {
          return HttpResponse.json({ ...emptyInbox(), suggested_matches: [{ expense: suggested, document }] })
        }
        return HttpResponse.json({ ...emptyInbox(), documents_without_transactions: [document] })
      }),
      http.post(`${API_BASE}/reconciliation/matches/suggested-3/reject`, () => {
        rejected = true
        return HttpResponse.json({ expense: { ...suggested, document_status: 'missing' } })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<ReconciliationInboxPage />)

    await waitFor(() => expect(screen.getByRole('button', { name: 'דחיית ההתאמה' })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'דחיית ההתאמה' }))

    await waitFor(() => expect(screen.getByRole('button', { name: 'חיפוש התאמות מחדש' })).toBeInTheDocument())
  })

  it('discarding an unassigned document requires confirmation', async () => {
    const document = makeUnassignedDocument()
    let discardCalled = false
    server.use(
      http.get(INBOX_URL, () =>
        HttpResponse.json({ ...emptyInbox(), documents_without_transactions: [document] }),
      ),
      http.post(`${API_BASE}/reconciliation/documents/upload-1/discard`, () => {
        discardCalled = true
        return new HttpResponse(null, { status: 204 })
      }),
    )

    const user = userEvent.setup()
    renderWithProviders(<ReconciliationInboxPage />)

    await waitFor(() => expect(screen.getByText('Cofix')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'מחיקת המסמך' }))

    expect(screen.getByText('למחוק את המסמך הזה?')).toBeInTheDocument()
    expect(discardCalled).toBe(false)

    await user.click(screen.getByRole('button', { name: 'מחיקה' }))
    await waitFor(() => expect(discardCalled).toBe(true))
  })

  it('the manual match picker shows only eligible expenses and a conflict warning where relevant', async () => {
    const document = makeUnassignedDocument()
    const eligibleExpense = makeExpense({ id: 'eligible-1', document_status: 'missing' })
    server.use(
      http.get(INBOX_URL, () =>
        HttpResponse.json({ ...emptyInbox(), documents_without_transactions: [document] }),
      ),
      http.get(`${API_BASE}/reconciliation/documents/upload-1/eligible-expenses`, () =>
        HttpResponse.json([{ expense: eligibleExpense, score: 0.4, reasons: [], has_conflict: true }]),
      ),
    )

    const user = userEvent.setup()
    renderWithProviders(<ReconciliationInboxPage />)

    await waitFor(() => expect(screen.getByText('Cofix')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'בחירת עסקה ידנית' }))

    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    expect(screen.getByText('בחירת עסקה')).toBeInTheDocument()
    expect(screen.getAllByText('Shufersal')).toHaveLength(1)
    expect(screen.getByText(/חלק מהפרטים לא תואמים/)).toBeInTheDocument()
  })
})
