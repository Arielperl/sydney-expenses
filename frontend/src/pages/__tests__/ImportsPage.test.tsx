import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { ImportsPage } from '../ImportsPage'
import { server } from '../../test/msw/server'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const PREVIEW_URL = 'http://localhost:8000/api/imports/csv/preview'
const CONFIRM_URL = 'http://localhost:8000/api/imports/csv/confirm'

function fakeCsvFile() {
  return new File(['date,description,merchant,amount,currency\n2026-09-01,Lunch,Demo Cafe,45.50,ILS\n'], 'statement.csv', {
    type: 'text/csv',
  })
}

async function selectFile(user: ReturnType<typeof userEvent.setup>) {
  const fileInput = screen.getByLabelText('בחירת קובץ CSV', { selector: 'input' })
  await user.upload(fileInput, fakeCsvFile())
}

const previewResponse = {
  file_hash: 'hash-1',
  filename: 'statement.csv',
  valid_rows: [
    {
      row_number: 1,
      expense_date: '2026-09-01',
      description: 'Lunch',
      merchant: 'Demo Cafe',
      amount: '45.50',
      currency: 'ILS',
      external_id: 'csv:hash-1:1',
    },
  ],
  errors: [],
  is_repeat_file: false,
}

describe('ImportsPage', () => {
  it('renders the webhook demo instructions', () => {
    renderWithProviders(<ImportsPage />)
    expect(screen.getByText('חיבור וובהוק (הדגמה)')).toBeInTheDocument()
    expect(screen.getByText(/demo_webhook_request/)).toBeInTheDocument()
  })

  it('previews a CSV file and shows the parsed rows', async () => {
    server.use(http.post(PREVIEW_URL, () => HttpResponse.json(previewResponse)))
    const user = userEvent.setup()
    renderWithProviders(<ImportsPage />)

    await selectFile(user)

    await waitFor(() => expect(screen.getByText('Demo Cafe')).toBeInTheDocument())
    expect(screen.getByText('1 שורות תקינות')).toBeInTheDocument()
  })

  it('confirming the import shows a success summary', async () => {
    server.use(
      http.post(PREVIEW_URL, () => HttpResponse.json(previewResponse)),
      http.post(CONFIRM_URL, () =>
        HttpResponse.json({ import_batch_id: 'batch-1', created_count: 1, duplicate_count: 0, error_count: 0 }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<ImportsPage />)

    await selectFile(user)
    await waitFor(() => expect(screen.getByRole('button', { name: 'אישור הייבוא' })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'אישור הייבוא' }))

    await waitFor(() => expect(screen.getByText('הייבוא הושלם')).toBeInTheDocument())
    expect(screen.getByText('1 עסקאות חדשות נוצרו')).toBeInTheDocument()
  })

  it('shows an error message when preview fails', async () => {
    server.use(http.post(PREVIEW_URL, () => HttpResponse.json({ detail: 'bad file' }, { status: 422 })))
    const user = userEvent.setup()
    renderWithProviders(<ImportsPage />)

    await selectFile(user)

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
