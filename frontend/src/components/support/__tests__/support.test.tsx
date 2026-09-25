import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { sortTickets } from '../../../lib/support'
import { formatRelativeTime, parseServerTimestamp } from '../../../lib/supportTime'
import { SupportInbox } from '../../../pages/support-portal/SupportInbox'
import { SupportRequestPage } from '../../../pages/SupportRequestPage'
import type { SupportMessage, SupportRequest } from '../../../services/supportService'
import { server } from '../../../test/msw/server'
import { renderWithProviders, screen, waitFor, within } from '../../../test/test-utils'
import { SupportConversationDialog } from '../../SupportConversationDialog'

const API = 'http://localhost:8000/api'

function ticket(overrides: Partial<SupportRequest>): SupportRequest {
  return {
    id: 't1', business_id: 'b1', business_name: 'סטודיו נועה', requester_email: 'noa@example.com',
    subject: 'Grow לא קולט עסקאות', message: 'מאז יום שלישי חלק מהעסקאות לא מופיעות.', provider: 'grow',
    status: 'open', created_at: '2026-09-20T10:00:00', updated_at: '2026-09-20T10:00:00', ...overrides,
  }
}

describe('support timestamps', () => {
  it('reads naive server timestamps as UTC', () => {
    expect(parseServerTimestamp('2026-09-20T10:00:00').toISOString()).toBe('2026-09-20T10:00:00.000Z')
    expect(parseServerTimestamp('2026-09-20T10:00:00.123456').toISOString()).toBe('2026-09-20T10:00:00.123Z')
    expect(parseServerTimestamp('2026-09-20T10:00:00+03:00').toISOString()).toBe('2026-09-20T07:00:00.000Z')
  })

  it('formats recent times relatively', () => {
    const now = new Date('2026-09-20T12:00:00Z')
    expect(formatRelativeTime(new Date('2026-09-20T11:55:00Z'), 'en', now)).toBe('5 minutes ago')
    expect(formatRelativeTime(new Date('2026-09-19T12:00:00Z'), 'en', now)).toBe('yesterday')
  })

  it('orders open tickets first, then by last update', () => {
    const sorted = sortTickets([
      ticket({ id: 'old-open', updated_at: '2026-09-01T10:00:00' }),
      ticket({ id: 'new-resolved', status: 'resolved', updated_at: '2026-09-25T10:00:00' }),
      ticket({ id: 'new-open', updated_at: '2026-09-24T10:00:00' }),
    ])
    expect(sorted.map((item) => item.id)).toEqual(['new-open', 'old-open', 'new-resolved'])
  })
})

describe('SupportRequestPage', () => {
  it('shows an empty state with a way to open the first request', async () => {
    server.use(http.get(`${API}/support/requests`, () => HttpResponse.json([])))
    renderWithProviders(<SupportRequestPage />)
    expect(await screen.findByText('עדיין אין פניות')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'פתיחת פנייה ראשונה' })).toBeInTheDocument()
  })

  it('lists requests with a textual status and filters them', async () => {
    const user = userEvent.setup()
    server.use(http.get(`${API}/support/requests`, () => HttpResponse.json([
      ticket({ id: 'a', subject: 'בקשה פתוחה', business_name: null, requester_email: null }),
      ticket({ id: 'b', subject: 'בקשה שטופלה', status: 'resolved', provider: null, business_name: null, requester_email: null }),
    ])))
    renderWithProviders(<SupportRequestPage />)
    const openRow = (await screen.findByText('בקשה פתוחה')).closest('li') as HTMLElement
    expect(within(openRow).getByText('פתוחה')).toBeInTheDocument()
    expect(within(openRow).getByText('Grow')).toBeInTheDocument()
    expect(screen.getByText('פנייה פתוחה אחת · 2 בסך הכול')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^טופלו/ }))
    expect(screen.queryByText('בקשה פתוחה')).not.toBeInTheDocument()
    expect(screen.getByText('בקשה שטופלה')).toBeInTheDocument()
  })

  it('opens the new-request dialog focused on the subject', async () => {
    const user = userEvent.setup()
    server.use(http.get(`${API}/support/requests`, () => HttpResponse.json([])))
    renderWithProviders(<SupportRequestPage />)
    await user.click(screen.getAllByRole('button', { name: /פנייה חדשה/ })[0])
    expect(screen.getByRole('dialog', { name: 'פנייה חדשה' })).toBeInTheDocument()
    expect(screen.getByLabelText('נושא')).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('SupportInbox', () => {
  const tickets = [
    ticket({ id: 'a', subject: 'Grow sync', business_name: 'Alpha', requester_email: 'a@example.com', provider: 'grow' }),
    ticket({ id: 'b', subject: 'Cardcom duplicates', business_name: 'Beta', requester_email: 'b@example.com', provider: 'cardcom' }),
    ticket({ id: 'c', subject: 'Export question', business_name: 'Gamma', requester_email: 'c@example.com', provider: null, status: 'resolved' }),
  ]

  it('defaults to open tickets and searches business, email, subject and provider', async () => {
    const user = userEvent.setup()
    server.use(http.get(`${API}/support/staff/requests`, () => HttpResponse.json(tickets)))
    renderWithProviders(<SupportInbox />)
    expect(await screen.findByText('Grow sync')).toBeInTheDocument()
    expect(screen.getByText('2 פניות פתוחות')).toBeInTheDocument()
    expect(screen.queryByText('Export question')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /^הכול/ }))
    const search = screen.getByRole('searchbox', { name: 'חיפוש פניות' })
    for (const [term, expected] of [['Beta', 'Cardcom duplicates'], ['c@example', 'Export question'], ['cardcom', 'Cardcom duplicates'], ['grow sync', 'Grow sync']]) {
      await user.clear(search)
      await user.type(search, term)
      expect(screen.getAllByRole('listitem')).toHaveLength(1)
      expect(screen.getByText(expected)).toBeInTheDocument()
    }
  })

  it('marks a ticket as resolved from its row', async () => {
    const user = userEvent.setup()
    let patched: unknown = null
    server.use(
      http.get(`${API}/support/staff/requests`, () => HttpResponse.json(tickets)),
      http.patch(`${API}/support/staff/requests/a`, async ({ request }) => {
        patched = await request.json()
        return HttpResponse.json({ ...tickets[0], status: 'resolved' })
      }),
    )
    renderWithProviders(<SupportInbox />)
    await user.click(await screen.findByRole('button', { name: 'סימון כטופלה: Grow sync' }))
    await waitFor(() => expect(patched).toEqual({ status: 'resolved' }))
  })
})

describe('SupportConversationDialog', () => {
  const messages: SupportMessage[] = [
    { id: 'initial-t1', author_type: 'customer', author_name: 'נועה', body: 'שלום', created_at: '2026-09-20T10:00:00' },
    { id: 'm1', author_type: 'staff', author_name: 'דנה מהתמיכה', body: 'היי, בודקת', created_at: '2026-09-20T10:05:00' },
  ]

  it('never shows individual staff names to customers', async () => {
    server.use(http.get(`${API}/support/requests/t1/messages`, () => HttpResponse.json(messages)))
    renderWithProviders(<SupportConversationDialog request={ticket({})} staff={false} onClose={() => {}} />)
    expect(await screen.findByText('היי, בודקת')).toBeInTheDocument()
    expect(screen.getByText('צוות Sydney')).toBeInTheDocument()
    expect(screen.queryByText('דנה מהתמיכה')).not.toBeInTheDocument()
  })

  it('sends on Enter and keeps Shift+Enter as a new line', async () => {
    const user = userEvent.setup()
    let sent: unknown = null
    server.use(
      http.get(`${API}/support/requests/t1/messages`, () => HttpResponse.json(messages)),
      http.post(`${API}/support/requests/t1/messages`, async ({ request }) => {
        sent = await request.json()
        return HttpResponse.json({ id: 'm2', author_type: 'customer', author_name: 'נועה', body: 'x', created_at: '2026-09-20T10:06:00' }, { status: 201 })
      }),
    )
    renderWithProviders(<SupportConversationDialog request={ticket({})} staff={false} onClose={() => {}} />)
    const composer = await screen.findByRole('textbox', { name: 'כתיבת הודעה' })
    await user.type(composer, 'שורה אחת{Shift>}{Enter}{/Shift}שורה שתיים')
    expect(composer).toHaveValue('שורה אחת\nשורה שתיים')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(sent).toEqual({ body: 'שורה אחת\nשורה שתיים' }))
    await waitFor(() => expect(composer).toHaveValue(''))
  })

  it('explains that replying reopens a resolved request', async () => {
    server.use(http.get(`${API}/support/requests/t1/messages`, () => HttpResponse.json(messages)))
    renderWithProviders(<SupportConversationDialog request={ticket({ status: 'resolved' })} staff={false} onClose={() => {}} />)
    expect(await screen.findByText('הפנייה סומנה כטופלה. הודעה חדשה תפתח אותה מחדש.')).toBeInTheDocument()
  })
})
