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

  // Regression test for a real bug: the date-range filter used to sit in a rigid
  // `grid-cols-4` cell whose default `min-width: auto` let two native date inputs
  // (which refuse to shrink below their intrinsic content width) overflow the
  // filters card in RTL. Asserting the class structure here — not exact pixel
  // sizes, which jsdom can't measure — makes that regression hard to reintroduce
  // without this test failing.
  it('keeps the filter fields on a shrink-safe, non-fixed-width responsive layout', async () => {
    server.use(http.get(EXPENSES_URL, () => HttpResponse.json([])))
    renderWithProviders(<ExpensesPage />)
    await waitFor(() => expect(screen.getByText('לא נמצאו הוצאות')).toBeInTheDocument())

    const dateFromInput = screen.getByLabelText('מתאריך')
    const dateToInput = screen.getByLabelText('עד תאריך')
    const dateGroup = dateFromInput.parentElement
    expect(dateGroup).not.toBeNull()

    // The two date inputs and their shared wrapper must be able to shrink (the
    // actual fix) instead of keeping their native intrinsic width.
    for (const element of [dateFromInput, dateToInput, dateGroup as HTMLElement]) {
      expect(element.className).toContain('min-w-0')
    }
    // Each date input shares the row evenly rather than claiming full width.
    expect(dateFromInput.className).toContain('flex-1')
    expect(dateToInput.className).toContain('flex-1')

    // No field in the filter bar may use a fixed pixel width/min-width, which is
    // exactly what caused the original overflow (an unshrinkable intrinsic size).
    const filterCard = dateGroup!.parentElement
    expect(filterCard).not.toBeNull()
    for (const field of Array.from(filterCard!.children)) {
      expect(field.className).not.toMatch(/\bw-\[\d/)
      expect(field.className).not.toMatch(/\bmin-w-\[\d/)
    }

    // The card itself wraps onto multiple rows rather than forcing a fixed
    // column count that squeezes any one field.
    expect(filterCard!.className).toContain('flex-wrap')
  })

  it('shows a "view receipt" action only when the expense has a receipt image', async () => {
    const withReceipt = makeExpense({ id: 'expense-1', receipt_image_url: 'https://fake.supabase.co/signed?token=x' })

    server.use(http.get(EXPENSES_URL, () => HttpResponse.json([withReceipt])))
    renderWithProviders(<ExpensesPage />)

    await waitFor(() => expect(screen.getByText('Shufersal')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /צפייה בקבלה/ })).toBeInTheDocument()
  })

  it('does not show a "view receipt" action when the expense has no receipt image', async () => {
    const withoutReceipt = makeExpense({ id: 'expense-1', receipt_image_url: null })

    server.use(http.get(EXPENSES_URL, () => HttpResponse.json([withoutReceipt])))
    renderWithProviders(<ExpensesPage />)

    await waitFor(() => expect(screen.getByText('Shufersal')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /צפייה בקבלה/ })).not.toBeInTheDocument()
  })

  it('opens the receipt image in a modal, and falls back gracefully if the signed URL is broken', async () => {
    const user = userEvent.setup()
    const withReceipt = makeExpense({ id: 'expense-1', receipt_image_url: 'https://fake.supabase.co/signed?token=expired' })

    server.use(http.get(EXPENSES_URL, () => HttpResponse.json([withReceipt])))
    renderWithProviders(<ExpensesPage />)

    await waitFor(() => expect(screen.getByText('Shufersal')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /צפייה בקבלה/ }))

    const dialog = screen.getByRole('dialog')
    const image = within(dialog).getByRole('img')
    expect(image).toHaveAttribute('src', withReceipt.receipt_image_url)

    // Simulate an expired/broken signed URL: the browser fires onError, and the
    // page must show a text fallback instead of a broken image icon.
    image.dispatchEvent(new Event('error'))

    await waitFor(() =>
      expect(within(dialog).getByText(/לא ניתן היה לטעון את תמונת הקבלה/)).toBeInTheDocument(),
    )
    expect(within(dialog).queryByRole('img')).not.toBeInTheDocument()
  })
})
