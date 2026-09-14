import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import userEvent from '@testing-library/user-event'

import { AssistantPage } from '../AssistantPage'
import { server } from '../../test/msw/server'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const CHAT_URL = 'http://localhost:8000/api/assistant/chat'

describe('AssistantPage', () => {
  it('shows example questions in the empty state', async () => {
    renderWithProviders(<AssistantPage />)
    expect(await screen.findByText('כמה הכנסתי החודש?')).toBeInTheDocument()
  })

  it('sends a message and shows the reply', async () => {
    server.use(
      http.post(CHAT_URL, () => HttpResponse.json({ reply: 'הוצאת 100 ש"ח החודש.', conversation_id: 'chat-1' })),
    )
    const user = userEvent.setup()
    renderWithProviders(<AssistantPage />)

    await user.type(screen.getByPlaceholderText('שאל שאלה...'), 'כמה הוצאתי?')
    await user.click(screen.getByRole('button', { name: 'שלח' }))

    expect(screen.getByText('כמה הוצאתי?')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('הוצאת 100 ש"ח החודש.')).toBeInTheDocument()
    })
  })

  it('loads the latest persisted conversation', async () => {
    server.use(
      http.get('http://localhost:8000/api/assistant/conversations', () =>
        HttpResponse.json([
          { id: 'chat-1', title: 'הכנסות החודש', created_at: '2026-09-13T10:00:00', updated_at: '2026-09-13T10:01:00' },
        ]),
      ),
      http.get('http://localhost:8000/api/assistant/conversations/chat-1', () =>
        HttpResponse.json({
          id: 'chat-1',
          title: 'הכנסות החודש',
          created_at: '2026-09-13T10:00:00',
          updated_at: '2026-09-13T10:01:00',
          messages: [
            { id: 'message-1', role: 'user', content: 'כמה הכנסתי?', created_at: '2026-09-13T10:00:00' },
            { id: 'message-2', role: 'assistant', content: 'הכנסת ₪1,269.', created_at: '2026-09-13T10:01:00' },
          ],
        }),
      ),
    )

    renderWithProviders(<AssistantPage />)

    expect(await screen.findByText('כמה הכנסתי?')).toBeInTheDocument()
    expect(screen.getByText('הכנסת ₪1,269.')).toBeInTheDocument()
    expect(screen.getByText('הכנסות החודש')).toBeInTheDocument()
  })

  it('shows an error message when the request fails', async () => {
    server.use(http.post(CHAT_URL, () => HttpResponse.json({ detail: 'unavailable' }, { status: 503 })))
    const user = userEvent.setup()
    renderWithProviders(<AssistantPage />)

    await user.type(screen.getByPlaceholderText('שאל שאלה...'), 'שאלה')
    await user.click(screen.getByRole('button', { name: 'שלח' }))

    await waitFor(() => {
      expect(screen.getByText('לא הצלחתי לענות כרגע, נסה שוב.')).toBeInTheDocument()
    })
  })

  it('clicking an example question sends it', async () => {
    server.use(http.post(CHAT_URL, () => HttpResponse.json({ reply: 'תשובה', conversation_id: 'chat-1' })))
    const user = userEvent.setup()
    renderWithProviders(<AssistantPage />)

    await user.click(await screen.findByText('כמה הכנסתי החודש?'))

    await waitFor(() => {
      expect(screen.getByText('תשובה')).toBeInTheDocument()
    })
  })

  it('shows a thinking indicator while waiting for the reply, then hides it', async () => {
    server.use(
      http.post(CHAT_URL, async () => {
        await new Promise((resolve) => setTimeout(resolve, 50))
        return HttpResponse.json({ reply: 'תשובה סופית', conversation_id: 'chat-1' })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<AssistantPage />)

    await user.type(screen.getByPlaceholderText('שאל שאלה...'), 'כמה הוצאתי?')
    await user.click(screen.getByRole('button', { name: 'שלח' }))

    expect(screen.getByRole('status', { name: 'חושב...' })).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('תשובה סופית')).toBeInTheDocument()
    })
    expect(screen.queryByRole('status', { name: 'חושב...' })).not.toBeInTheDocument()
  })
})
