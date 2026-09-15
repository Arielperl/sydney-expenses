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

  describe('renaming a conversation', () => {
    const conversationOne = { id: 'chat-1', title: 'שיחה ראשונה', created_at: '2026-09-13T10:00:00', updated_at: '2026-09-13T10:01:00' }
    const conversationTwo = { id: 'chat-2', title: 'שיחה שנייה', created_at: '2026-09-13T11:00:00', updated_at: '2026-09-13T11:01:00' }
    const longTitle = 'שיחה עם כותרת ארוכה מאוד שאמורה להיחתך בשלוש נקודות בסוף השורה כי היא לא נכנסת ברוחב הזמין של העמודה'
    const conversationLong = { id: 'chat-3', title: longTitle, created_at: '2026-09-13T12:00:00', updated_at: '2026-09-13T12:01:00' }

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
        http.get(`${CONVERSATIONS_URL}/chat-3`, () => HttpResponse.json({ ...conversationLong, messages: [] })),
      )
    }

    it('renders a pencil button next to the trash button without breaking the row layout', async () => {
      mockConversations([conversationOne])
      renderWithProviders(<AssistantPage />)

      expect(await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'מחיקת שיחה: שיחה ראשונה' })).toBeInTheDocument()
      // The title itself is still a working, clickable button.
      expect(screen.getByRole('button', { name: /^שיחה ראשונה$/ })).toBeInTheDocument()
    })

    it('places the pencil button immediately before the trash button in DOM order, so RTL renders it to the right of trash', async () => {
      mockConversations([conversationOne])
      renderWithProviders(<AssistantPage />)

      const renameButton = await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' })
      const deleteButton = screen.getByRole('button', { name: 'מחיקת שיחה: שיחה ראשונה' })
      const row = renameButton.parentElement
      expect(row).not.toBeNull()
      const buttonsInRow = Array.from(row!.querySelectorAll<HTMLElement>('button'))
      const renameIndex = buttonsInRow.indexOf(renameButton)
      const deleteIndex = buttonsInRow.indexOf(deleteButton)
      // Title button (index 0), then pencil, then trash — under dir="rtl" the
      // first DOM child renders rightmost, so this DOM order puts the pencil
      // visually immediately to the right of the trash icon.
      expect(renameIndex).toBeGreaterThan(0)
      expect(deleteIndex).toBe(renameIndex + 1)
    })

    it('keeps a long conversation title CSS-truncatable (full text in the DOM, truncate class applied)', async () => {
      mockConversations([conversationLong])
      renderWithProviders(<AssistantPage />)

      const titleSpan = await screen.findByText(longTitle)
      expect(titleSpan).toHaveClass('truncate')
      // Both action icons still render at full size next to a very long title.
      expect(screen.getByRole('button', { name: `שינוי שם השיחה: ${longTitle}` })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: `מחיקת שיחה: ${longTitle}` })).toBeInTheDocument()
    })

    it('opens the rename dialog prefilled with the current title, focused and selected', async () => {
      mockConversations([conversationOne])
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' }))

      const dialog = await screen.findByRole('dialog')
      expect(within(dialog).getByRole('heading', { name: 'שינוי שם השיחה' })).toBeInTheDocument()
      const input = within(dialog).getByDisplayValue('שיחה ראשונה') as HTMLInputElement
      expect(document.activeElement).toBe(input)
      expect(input.selectionStart).toBe(0)
      expect(input.selectionEnd).toBe('שיחה ראשונה'.length)
      expect(within(dialog).getByRole('button', { name: 'ביטול' })).toBeInTheDocument()
      expect(within(dialog).getByRole('button', { name: 'שמירת השם' })).toBeInTheDocument()
    })

    it('cancelling leaves the title unchanged and restores focus to the pencil button', async () => {
      mockConversations([conversationOne])
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      const renameButton = await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' })
      await user.click(renameButton)
      const dialog = await screen.findByRole('dialog')
      await user.clear(within(dialog).getByDisplayValue('שיחה ראשונה'))
      await user.type(within(dialog).getByRole('textbox'), 'שם שלא יישמר')

      await user.click(within(dialog).getByRole('button', { name: 'ביטול' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(screen.getByText('שיחה ראשונה')).toBeInTheDocument()
      expect(screen.queryByText('שם שלא יישמר')).not.toBeInTheDocument()
      await waitFor(() => expect(document.activeElement).toBe(renameButton))
    })

    it('pressing Escape leaves the title unchanged', async () => {
      mockConversations([conversationOne])
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' }))
      const dialog = await screen.findByRole('dialog')
      await user.clear(within(dialog).getByRole('textbox'))
      await user.type(within(dialog).getByRole('textbox'), 'שם שלא יישמר')

      await user.keyboard('{Escape}')

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(screen.getByText('שיחה ראשונה')).toBeInTheDocument()
    })

    it('clicking the backdrop leaves the title unchanged', async () => {
      mockConversations([conversationOne])
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' }))
      await screen.findByRole('dialog')

      await user.click(screen.getByRole('button', { name: 'סגירת חלון' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(screen.getByText('שיחה ראשונה')).toBeInTheDocument()
    })

    it('submits a valid title by pressing Enter', async () => {
      mockConversations([conversationOne])
      let capturedBody: unknown = null
      server.use(
        http.patch(`${CONVERSATIONS_URL}/chat-1`, async ({ request }) => {
          capturedBody = await request.json()
          return HttpResponse.json({ ...conversationOne, title: 'שם חדש בלחיצת Enter' })
        }),
      )
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' }))
      const dialog = await screen.findByRole('dialog')
      const input = within(dialog).getByRole('textbox')
      await user.clear(input)
      await user.type(input, 'שם חדש בלחיצת Enter{Enter}')

      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(capturedBody).toEqual({ title: 'שם חדש בלחיצת Enter' })
      expect(screen.getByText('שם חדש בלחיצת Enter')).toBeInTheDocument()
    })

    it('cannot submit an empty or whitespace-only title', async () => {
      mockConversations([conversationOne])
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' }))
      const dialog = await screen.findByRole('dialog')
      const input = within(dialog).getByRole('textbox')
      const saveButton = within(dialog).getByRole('button', { name: 'שמירת השם' })

      await user.clear(input)
      expect(saveButton).toBeDisabled()

      await user.type(input, '   ')
      expect(saveButton).toBeDisabled()
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('cannot submit a title longer than 80 characters', async () => {
      mockConversations([conversationOne])
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' }))
      const dialog = await screen.findByRole('dialog')
      const input = within(dialog).getByRole('textbox')
      await user.clear(input)
      await user.type(input, 'א'.repeat(81))

      expect(within(dialog).getByRole('button', { name: 'שמירת השם' })).toBeDisabled()
      expect(within(dialog).getByText(/80/)).toBeInTheDocument()
    })

    it('closes without sending a request when the trimmed title is unchanged', async () => {
      mockConversations([conversationOne])
      let patchCalls = 0
      server.use(
        http.patch(`${CONVERSATIONS_URL}/chat-1`, () => {
          patchCalls += 1
          return HttpResponse.json(conversationOne)
        }),
      )
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' }))
      const dialog = await screen.findByRole('dialog')
      const input = within(dialog).getByRole('textbox')
      // Retype the same title padded with leading/trailing whitespace —
      // trims back to exactly the original title.
      await user.clear(input)
      await user.type(input, '   שיחה ראשונה   ')
      await user.click(within(dialog).getByRole('button', { name: 'שמירת השם' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(patchCalls).toBe(0)
    })

    it('updates the sidebar immediately on a successful rename, keeping the open conversation and its messages', async () => {
      mockConversations([conversationOne, conversationTwo])
      server.use(
        http.patch(`${CONVERSATIONS_URL}/chat-1`, () =>
          HttpResponse.json({ ...conversationOne, title: 'התקציב הרבעוני' }),
        ),
      )
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      expect(await screen.findByText('כמה הכנסתי?')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' }))
      const dialog = await screen.findByRole('dialog')
      const input = within(dialog).getByRole('textbox')
      await user.clear(input)
      await user.type(input, 'התקציב הרבעוני')
      await user.click(within(dialog).getByRole('button', { name: 'שמירת השם' }))

      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(screen.getByText('התקציב הרבעוני')).toBeInTheDocument()
      expect(screen.queryByText('שיחה ראשונה')).not.toBeInTheDocument()
      // The other conversation's row is untouched.
      expect(screen.getByText('שיחה שנייה')).toBeInTheDocument()
      // Still the same open conversation, same messages, no reload.
      expect(screen.getByText('כמה הכנסתי?')).toBeInTheDocument()
    })

    it('persists the renamed title after a fresh API load', async () => {
      mockConversations([conversationOne])
      let currentTitle = conversationOne.title
      server.use(
        http.get(CONVERSATIONS_URL, () => HttpResponse.json([{ ...conversationOne, title: currentTitle }])),
        http.get(`${CONVERSATIONS_URL}/chat-1`, () =>
          HttpResponse.json({
            ...conversationOne,
            title: currentTitle,
            messages: [{ id: 'm1', role: 'user', content: 'כמה הכנסתי?', created_at: conversationOne.created_at }],
          }),
        ),
        http.patch(`${CONVERSATIONS_URL}/chat-1`, () => {
          currentTitle = 'שם קבוע אחרי רענון'
          return HttpResponse.json({ ...conversationOne, title: currentTitle })
        }),
      )
      const user = userEvent.setup()
      const { unmount } = renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' }))
      const dialog = await screen.findByRole('dialog')
      const input = within(dialog).getByRole('textbox')
      await user.clear(input)
      await user.type(input, 'שם קבוע אחרי רענון')
      await user.click(within(dialog).getByRole('button', { name: 'שמירת השם' }))
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

      // Simulate a fresh page load with a brand-new query cache.
      unmount()
      renderWithProviders(<AssistantPage />)
      expect(await screen.findByText('שם קבוע אחרי רענון')).toBeInTheDocument()
    })

    it('shows a loading state, disables the input and both buttons, and prevents a duplicate rename request', async () => {
      mockConversations([conversationOne])
      let patchCalls = 0
      let resolvePatch: () => void = () => {}
      const patchGate = new Promise<void>((resolve) => {
        resolvePatch = resolve
      })
      server.use(
        http.patch(`${CONVERSATIONS_URL}/chat-1`, async () => {
          patchCalls += 1
          await patchGate
          return HttpResponse.json({ ...conversationOne, title: 'שם חדש' })
        }),
      )
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' }))
      const dialog = await screen.findByRole('dialog')
      const input = within(dialog).getByRole('textbox')
      await user.clear(input)
      await user.type(input, 'שם חדש')
      const saveButton = within(dialog).getByRole('button', { name: 'שמירת השם' })
      await user.click(saveButton)

      await waitFor(() => expect(input).toBeDisabled())
      expect(within(dialog).getByRole('button', { name: 'ביטול' })).toBeDisabled()
      const savingButton = within(dialog).getByRole('button', { name: 'שומר...' })
      expect(savingButton).toBeDisabled()

      await user.click(savingButton)
      expect(patchCalls).toBe(1)

      resolvePatch()
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(patchCalls).toBe(1)
    })

    it('keeps the dialog open with a Hebrew error on failure, preserves the entered title, and allows retry', async () => {
      mockConversations([conversationOne])
      let attempt = 0
      server.use(
        http.patch(`${CONVERSATIONS_URL}/chat-1`, () => {
          attempt += 1
          if (attempt === 1) return HttpResponse.json({ detail: 'server error' }, { status: 500 })
          return HttpResponse.json({ ...conversationOne, title: 'שם אחרי ניסיון חוזר' })
        }),
      )
      const user = userEvent.setup()
      renderWithProviders(<AssistantPage />)

      await user.click(await screen.findByRole('button', { name: 'שינוי שם השיחה: שיחה ראשונה' }))
      const dialog = await screen.findByRole('dialog')
      const input = within(dialog).getByRole('textbox')
      await user.clear(input)
      await user.type(input, 'שם אחרי ניסיון חוזר')
      await user.click(within(dialog).getByRole('button', { name: 'שמירת השם' }))

      await waitFor(() =>
        expect(within(dialog).getByText('לא הצלחנו לשנות את שם השיחה. נסו שוב.')).toBeInTheDocument(),
      )
      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(within(dialog).getByDisplayValue('שם אחרי ניסיון חוזר')).toBeInTheDocument()

      await user.click(within(dialog).getByRole('button', { name: 'שמירת השם' }))

      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(screen.getByText('שם אחרי ניסיון חוזר')).toBeInTheDocument()
    })
  })
})
