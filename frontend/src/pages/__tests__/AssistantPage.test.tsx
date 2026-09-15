import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'
import userEvent from '@testing-library/user-event'

import { AssistantPage } from '../AssistantPage'
import { server } from '../../test/msw/server'
import { renderWithProviders, screen, waitFor, within } from '../../test/test-utils'

const CHAT_URL = 'http://localhost:8000/api/assistant/chat'
const CONVERSATIONS_URL = 'http://localhost:8000/api/assistant/conversations'

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

  describe('deleting a conversation', () => {
    const conversationOne = { id: 'chat-1', title: 'שיחה ראשונה', created_at: '2026-09-13T10:00:00', updated_at: '2026-09-13T10:01:00' }
    const conversationTwo = { id: 'chat-2', title: 'שיחה שנייה', created_at: '2026-09-13T11:00:00', updated_at: '2026-09-13T11:01:00' }

    function mockConversations(list: (typeof conversationOne)[]) {
      server.use(
        http.get(CONVERSATIONS_URL, () => HttpResponse.json(list)),
        http.get(`${CONVERSATIONS_URL}/chat-1`, () =>
          HttpResponse.json({
            ...conversationOne,
            messages: [{ id: 'm1', role: 'user', content: 'כמה הכנסתי?', created_at: conversationOne.created_at }],
          }),
        ),
        http.get(`${CONVERSATIONS_URL}/chat-2`, () => HttpResponse.json({ ...conversationTwo, messages: [] })),
      )
    }

    it('opens a custom confirmation modal instead of the browser-native confirm', async () => {
      const confirmSpy = vi.spyOn(window, 'confirm')
      mockConversations([conversationOne, conversationTwo])
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'מחיקת שיחה: שיחה ראשונה' }))

      const dialog = await screen.findByRole('dialog')
      expect(within(dialog).getByText('מחיקת שיחה')).toBeInTheDocument()
      expect(within(dialog).getByText('האם למחוק את השיחה הזאת? לא ניתן לבטל את הפעולה.')).toBeInTheDocument()
      expect(within(dialog).getByRole('button', { name: 'ביטול' })).toBeInTheDocument()
      expect(within(dialog).getByRole('button', { name: 'מחיקת השיחה' })).toBeInTheDocument()
      expect(confirmSpy).not.toHaveBeenCalled()
      confirmSpy.mockRestore()
    })

    it('cancelling leaves the conversation untouched and restores focus to the delete button', async () => {
      mockConversations([conversationOne, conversationTwo])
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      const deleteButton = await screen.findByRole('button', { name: 'מחיקת שיחה: שיחה ראשונה' })
      await user.click(deleteButton)
      const dialog = await screen.findByRole('dialog')

      await user.click(within(dialog).getByRole('button', { name: 'ביטול' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(screen.getByText('שיחה ראשונה')).toBeInTheDocument()
      await waitFor(() => expect(document.activeElement).toBe(deleteButton))
    })

    it('pressing Escape closes the modal without deleting', async () => {
      mockConversations([conversationOne, conversationTwo])
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'מחיקת שיחה: שיחה ראשונה' }))
      await screen.findByRole('dialog')

      await user.keyboard('{Escape}')

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(screen.getByText('שיחה ראשונה')).toBeInTheDocument()
    })

    it('confirming deletion calls the API and removes the conversation from the sidebar immediately', async () => {
      mockConversations([conversationOne, conversationTwo])
      let deleteCalls = 0
      server.use(
        http.delete(`${CONVERSATIONS_URL}/chat-2`, () => {
          deleteCalls += 1
          return new HttpResponse(null, { status: 204 })
        }),
      )
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'מחיקת שיחה: שיחה שנייה' }))
      const dialog = await screen.findByRole('dialog')
      await user.click(within(dialog).getByRole('button', { name: 'מחיקת השיחה' }))

      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(screen.queryByText('שיחה שנייה')).not.toBeInTheDocument()
      expect(deleteCalls).toBe(1)
      // The still-open first conversation's own messages are unaffected.
      expect(screen.getByText('כמה הכנסתי?')).toBeInTheDocument()
    })

    it('shows a loading state, disables both buttons, and prevents a duplicate delete request', async () => {
      mockConversations([conversationOne, conversationTwo])
      let deleteCalls = 0
      let resolveDelete: () => void = () => {}
      const deleteGate = new Promise<void>((resolve) => {
        resolveDelete = resolve
      })
      server.use(
        http.delete(`${CONVERSATIONS_URL}/chat-2`, async () => {
          deleteCalls += 1
          await deleteGate
          return new HttpResponse(null, { status: 204 })
        }),
      )
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'מחיקת שיחה: שיחה שנייה' }))
      const dialog = await screen.findByRole('dialog')
      const confirmButton = within(dialog).getByRole('button', { name: 'מחיקת השיחה' })
      const cancelButton = within(dialog).getByRole('button', { name: 'ביטול' })

      await user.click(confirmButton)

      await waitFor(() => expect(within(dialog).getByRole('button', { name: 'מוחק...' })).toBeDisabled())
      expect(cancelButton).toBeDisabled()

      // A second click while disabled must not fire another request.
      await user.click(within(dialog).getByRole('button', { name: 'מוחק...' }))
      expect(deleteCalls).toBe(1)

      resolveDelete()
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(deleteCalls).toBe(1)
    })

    it('shows a Hebrew error message and keeps the modal open on failure, then succeeds on retry', async () => {
      mockConversations([conversationOne, conversationTwo])
      let attempt = 0
      server.use(
        http.delete(`${CONVERSATIONS_URL}/chat-2`, () => {
          attempt += 1
          if (attempt === 1) return HttpResponse.json({ detail: 'server error' }, { status: 500 })
          return new HttpResponse(null, { status: 204 })
        }),
      )
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'מחיקת שיחה: שיחה שנייה' }))
      const dialog = await screen.findByRole('dialog')
      await user.click(within(dialog).getByRole('button', { name: 'מחיקת השיחה' }))

      await waitFor(() =>
        expect(within(dialog).getByText('לא הצלחנו למחוק את השיחה. נסו שוב.')).toBeInTheDocument(),
      )
      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(screen.getByText('שיחה שנייה')).toBeInTheDocument()

      await user.click(within(dialog).getByRole('button', { name: 'מחיקת השיחה' }))

      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(screen.queryByText('שיחה שנייה')).not.toBeInTheDocument()
    })

    it('deleting the currently open conversation navigates to a clean new conversation state', async () => {
      mockConversations([conversationOne])
      server.use(http.delete(`${CONVERSATIONS_URL}/chat-1`, () => new HttpResponse(null, { status: 204 })))
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      expect(await screen.findByText('כמה הכנסתי?')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'מחיקת שיחה: שיחה ראשונה' }))
      const dialog = await screen.findByRole('dialog')
      await user.click(within(dialog).getByRole('button', { name: 'מחיקת השיחה' }))

      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(screen.queryByText('כמה הכנסתי?')).not.toBeInTheDocument()
      expect(screen.getByText('שאל אותי משהו על העסק שלך')).toBeInTheDocument()
    })
  })
})
