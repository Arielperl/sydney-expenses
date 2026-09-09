import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import userEvent from '@testing-library/user-event'

import { AssistantPage } from '../AssistantPage'
import { server } from '../../test/msw/server'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const CHAT_URL = 'http://localhost:8000/api/assistant/chat'

describe('AssistantPage', () => {
  it('shows example questions in the empty state', () => {
    renderWithProviders(<AssistantPage />)
    expect(screen.getByText('כמה מכרתי החודש?')).toBeInTheDocument()
  })

  it('sends a message and shows the reply', async () => {
    server.use(
      http.post(CHAT_URL, () => HttpResponse.json({ reply: 'מכרת 100 ש"ח החודש.' })),
    )
    const user = userEvent.setup()
    renderWithProviders(<AssistantPage />)

    await user.type(screen.getByPlaceholderText('שאל שאלה...'), 'כמה מכרתי?')
    await user.click(screen.getByRole('button', { name: 'שלח' }))

    expect(screen.getByText('כמה מכרתי?')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText('מכרת 100 ש"ח החודש.')).toBeInTheDocument()
    })
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
    server.use(http.post(CHAT_URL, () => HttpResponse.json({ reply: 'תשובה' })))
    const user = userEvent.setup()
    renderWithProviders(<AssistantPage />)

    await user.click(screen.getByText('כמה מכרתי החודש?'))

    await waitFor(() => {
      expect(screen.getByText('תשובה')).toBeInTheDocument()
    })
  })
})
