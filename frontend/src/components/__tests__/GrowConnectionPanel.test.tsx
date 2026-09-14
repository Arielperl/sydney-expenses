import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../../contexts/AuthContext'
import { server } from '../../test/msw/server'
import { renderWithProviders, screen, waitFor, within } from '../../test/test-utils'
import { GrowConnectionPanel } from '../GrowConnectionPanel'
import type { WebhookEventListResponse } from '../../types/connections'

const API_BASE = 'http://localhost:8000/api'
const SESSION_URL = `${API_BASE}/auth/session`
const CONNECTIONS_URL = `${API_BASE}/connections`

function mockSession(role: 'owner' | 'manager' | 'viewer') {
  server.use(
    http.get(SESSION_URL, () =>
      HttpResponse.json({
        user: { id: 'user-1', email: 'user@example.com', name: 'User', has_workspace: true, role },
      }),
    ),
  )
}

function renderPanel() {
  return renderWithProviders(
    <AuthProvider>
      <GrowConnectionPanel />
    </AuthProvider>,
  )
}

const waitingConnection = {
  id: 'conn-1',
  provider: 'grow',
  name: 'קופה ראשית',
  enabled: true,
  webhook_path: '/api/webhooks/connections/tok_abc123',
  has_received_event: false,
  last_event_at: null,
  created_at: '2026-09-01T00:00:00',
  event_counts: { received: 0, processed: 0, duplicate: 0, failed: 0 },
}

const activeConnection = {
  ...waitingConnection,
  id: 'conn-2',
  has_received_event: true,
  last_event_at: '2026-09-10T12:00:00',
  event_counts: { received: 0, processed: 3, duplicate: 1, failed: 0 },
}

function stubClipboard() {
  const mockWriteText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { value: { writeText: mockWriteText }, configurable: true })
  return mockWriteText
}

describe('GrowConnectionPanel', () => {
  it('shows the empty state and create form for an owner', async () => {
    mockSession('owner')
    server.use(http.get(CONNECTIONS_URL, () => HttpResponse.json([])))
    renderPanel()

    await waitFor(() => expect(screen.getByText('עדיין אין חיבורי Grow. הוסיפו אחד למטה כדי להתחיל.')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'הוספת חיבור' })).toBeInTheDocument()
  })

  it('shows a waiting-for-first-transaction state, never claiming verified', async () => {
    mockSession('owner')
    server.use(http.get(CONNECTIONS_URL, () => HttpResponse.json([waitingConnection])))
    renderPanel()

    await waitFor(() => expect(screen.getByText('ממתין לעסקה ראשונה')).toBeInTheDocument())
    expect(screen.queryByText('פעיל')).not.toBeInTheDocument()
  })

  it('shows an active state with the last event time once a real event arrived', async () => {
    mockSession('owner')
    server.use(http.get(CONNECTIONS_URL, () => HttpResponse.json([activeConnection])))
    renderPanel()

    await waitFor(() => expect(screen.getByText('פעיל')).toBeInTheDocument())
    expect(screen.getByText(/עסקה אחרונה/)).toBeInTheDocument()
  })

  it('lets the owner copy the webhook URL', async () => {
    mockSession('owner')
    server.use(http.get(CONNECTIONS_URL, () => HttpResponse.json([waitingConnection])))
    renderPanel()
    const user = userEvent.setup()
    const mockWriteText = stubClipboard()

    await waitFor(() => expect(screen.getByText('קופה ראשית')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'העתקת כתובת Webhook' }))

    expect(mockWriteText).toHaveBeenCalledWith(expect.stringContaining('/api/webhooks/connections/tok_abc123'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'הועתק!' })).toBeInTheDocument())
  })

  it('creates a new connection', async () => {
    mockSession('owner')
    let connections: (typeof waitingConnection)[] = []
    server.use(
      http.get(CONNECTIONS_URL, () => HttpResponse.json(connections)),
      http.post(CONNECTIONS_URL, () => {
        const created = { ...waitingConnection, id: 'conn-new', name: 'קופה חדשה' }
        connections = [...connections, created]
        return HttpResponse.json({ ...created, signing_secret: null }, { status: 201 })
      }),
    )
    renderPanel()
    const user = userEvent.setup()

    await waitFor(() => expect(screen.getByPlaceholderText('שם החיבור, למשל קופה ראשית')).toBeInTheDocument())
    await user.type(screen.getByPlaceholderText('שם החיבור, למשל קופה ראשית'), 'קופה חדשה')
    await user.click(screen.getByRole('button', { name: 'הוספת חיבור' }))

    await waitFor(() => expect(screen.getByText('קופה חדשה')).toBeInTheDocument())
  })

  it('hides management controls from a manager and shows the owner-only note', async () => {
    mockSession('manager')
    server.use(http.get(CONNECTIONS_URL, () => HttpResponse.json([waitingConnection])))
    renderPanel()

    await waitFor(() => expect(screen.getByText('קופה ראשית')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'מחיקה' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'הוספת חיבור' })).not.toBeInTheDocument()
    expect(screen.getByText('רק בעל/ת העסק יכול/ה להוסיף או לנהל חיבורי Grow.')).toBeInTheDocument()
  })

  it('hides management controls from a viewer', async () => {
    mockSession('viewer')
    server.use(http.get(CONNECTIONS_URL, () => HttpResponse.json([waitingConnection])))
    renderPanel()

    await waitFor(() => expect(screen.getByText('קופה ראשית')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'השבתה' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'סבב כתובת' })).not.toBeInTheDocument()
  })

  it('asks for confirmation before deleting, and shows a clear warning before rotating', async () => {
    mockSession('owner')
    server.use(http.get(CONNECTIONS_URL, () => HttpResponse.json([waitingConnection])))
    renderPanel()
    const user = userEvent.setup()

    await waitFor(() => expect(screen.getByText('קופה ראשית')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'מחיקה' }))
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByText(/פעולה זו מוחקת לצמיתות/)).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'ביטול' }))

    await user.click(screen.getByRole('button', { name: 'סבב כתובת' }))
    const rotateDialog = await screen.findByRole('dialog')
    expect(within(rotateDialog).getByText(/יוצרת מיד כתובת Webhook חדשה/)).toBeInTheDocument()
  })

  it('shows the connection activity counts and lets a reprocessable failure be retried', async () => {
    mockSession('owner')
    let eventsBody: WebhookEventListResponse = {
      counts: { received: 0, processed: 3, duplicate: 1, failed: 1, rejected: 0 },
      events: [
        {
          id: 'evt-1',
          status: 'failed',
          received_at: '2026-09-10T12:00:00',
          processed_at: '2026-09-10T12:00:01',
          failure_category: 'processing_error',
          failure_message: 'RuntimeError during sale creation',
          sale_id: null,
          can_reprocess: true,
        },
      ],
    }
    server.use(
      http.get(CONNECTIONS_URL, () => HttpResponse.json([activeConnection])),
      http.get(`${CONNECTIONS_URL}/${activeConnection.id}/events`, () => HttpResponse.json(eventsBody)),
      http.post(`${CONNECTIONS_URL}/${activeConnection.id}/events/evt-1/reprocess`, () => {
        eventsBody = {
          counts: { received: 0, processed: 4, duplicate: 1, failed: 0, rejected: 0 },
          events: [
            {
              id: 'evt-1',
              status: 'processed',
              received_at: '2026-09-10T12:00:00',
              processed_at: '2026-09-10T12:00:02',
              failure_category: null,
              failure_message: null,
              sale_id: 'sale-1',
              can_reprocess: false,
            },
          ],
        }
        return HttpResponse.json(eventsBody.events[0])
      }),
    )
    renderPanel()
    const user = userEvent.setup()

    await waitFor(() => expect(screen.getByText('קופה ראשית')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'הצגת פעילות' }))

    await waitFor(() => expect(screen.getByText('RuntimeError during sale creation')).toBeInTheDocument())
    expect(screen.getByText('3 עובדו')).toBeInTheDocument()
    expect(screen.getByText('1 כפולות')).toBeInTheDocument()
    expect(screen.getByText('1 נכשלו')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'ניסיון חוזר' }))
    await waitFor(() => expect(screen.queryByText('RuntimeError during sale creation')).not.toBeInTheDocument())
  })

  it('never uses demo/test/simulator wording anywhere in the panel', async () => {
    mockSession('owner')
    server.use(http.get(CONNECTIONS_URL, () => HttpResponse.json([waitingConnection])))
    const { container } = renderPanel()

    await waitFor(() => expect(screen.getByText('קופה ראשית')).toBeInTheDocument())
    const text = container.textContent ?? ''
    for (const forbidden of ['demo', 'דמו', 'הדגמה', 'simulator', 'מדמה', 'test provider', 'demo-pay', 'mock']) {
      expect(text.toLowerCase()).not.toContain(forbidden.toLowerCase())
    }
  })

  it('always shows the manual refund/cancellation note and CSV fallback note', async () => {
    mockSession('owner')
    server.use(http.get(CONNECTIONS_URL, () => HttpResponse.json([])))
    renderPanel()

    await waitFor(() =>
      expect(
        screen.getByText('Grow אינה שולחת כרגע עדכוני זיכוי או ביטול דרך חיבור זה — יש לרשום אותם ידנית על המכירה.'),
      ).toBeInTheDocument(),
    )
    expect(screen.getByText(/ייבוא CSV/)).toBeInTheDocument()
  })
})
