import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { ExpensesPage } from '../ExpensesPage'
import { server } from '../../test/msw/server'
import { makeExpense } from '../../test/msw/handlers'
import { renderWithProviders, screen, waitFor, within } from '../../test/test-utils'

const EXPENSES_URL = 'http://localhost:8000/api/expenses'

describe('ExpensesPage', () => {
  it('opens the edit form pre-filled and saves changes', async () => {
    const user = userEvent.setup()
    const expense = makeExpense()

    server.use(
      http.get(EXPENSES_URL, () => HttpResponse.json([expense])),
      http.put(`${EXPENSES_URL}/:id`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json({ ...expense, ...body })
      }),
    )

    renderWithProviders(<ExpensesPage />)

    await waitFor(() => expect(screen.getByText('Shufersal')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /עריכת Shufersal/ }))

    const dialog = screen.getByRole('dialog')
    const businessNameInput = within(dialog).getByLabelText(/שם העסק/)
    expect(businessNameInput).toHaveValue('Shufersal')

    await user.clear(businessNameInput)
    await user.type(businessNameInput, 'Rami Levy')
    await user.click(within(dialog).getByRole('button', { name: 'שמירת שינויים' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('asks for confirmation before deleting and calls the delete API on confirm', async () => {
    const user = userEvent.setup()
    const expense = makeExpense()
    const deleteSpy = vi.fn()

    server.use(
      http.get(EXPENSES_URL, () => HttpResponse.json([expense])),
      http.delete(`${EXPENSES_URL}/:id`, ({ params }) => {
        deleteSpy(params.id)
        return new HttpResponse(null, { status: 204 })
      }),
    )

    renderWithProviders(<ExpensesPage />)

    await waitFor(() => expect(screen.getByText('Shufersal')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /מחיקת Shufersal/ }))

    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(/Shufersal/)).toBeInTheDocument()

    // Deletion must not happen until the user explicitly confirms.
    expect(deleteSpy).not.toHaveBeenCalled()

    await user.click(within(dialog).getByRole('button', { name: 'מחיקה' }))

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith(expense.id))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})
