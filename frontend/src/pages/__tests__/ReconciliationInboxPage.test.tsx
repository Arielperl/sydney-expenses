import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { ReconciliationInboxPage } from '../ReconciliationInboxPage'
import { server } from '../../test/msw/server'
import { makeExpense } from '../../test/msw/handlers'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const INBOX_URL = 'http://localhost:8000/api/reconciliation/inbox'

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

  it('lists a missing-document transaction', async () => {
    const missing = makeExpense({ id: 'missing-1', document_status: 'missing' })
    server.use(http.get(INBOX_URL, () => HttpResponse.json({ ...emptyInbox(), missing_documents: [missing] })))

    renderWithProviders(<ReconciliationInboxPage />)

    await waitFor(() => expect(screen.getByText('Shufersal')).toBeInTheDocument())
    expect(screen.getByText('חסר מסמך')).toBeInTheDocument()
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
      http.get(INBOX_URL, () => HttpResponse.json({ ...emptyInbox(), suggested_matches: [suggested] })),
      http.post('http://localhost:8000/api/reconciliation/matches/suggested-1/approve', () => {
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
      http.get(INBOX_URL, () => HttpResponse.json({ ...emptyInbox(), suggested_matches: [suggested] })),
      http.post('http://localhost:8000/api/reconciliation/matches/suggested-2/reject', () => {
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
})
