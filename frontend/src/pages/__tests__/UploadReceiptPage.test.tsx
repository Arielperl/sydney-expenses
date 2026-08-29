import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { UploadReceiptPage } from '../UploadReceiptPage'
import { server } from '../../test/msw/server'
import { renderWithProviders, screen, waitFor, waitForElementToBeRemoved } from '../../test/test-utils'

const UPLOAD_URL = 'http://localhost:8000/api/receipts/upload'
const CONFIRM_URL = 'http://localhost:8000/api/receipts/confirm'

function fakeReceiptFile() {
  return new File(['fake-image-bytes'], 'receipt.png', { type: 'image/png' })
}

async function selectFile(user: ReturnType<typeof userEvent.setup>) {
  const fileInput = screen.getByLabelText('בחירת תמונה', { selector: 'input' })
  await user.upload(fileInput, fakeReceiptFile())
}

const successfulExtraction = {
  upload_id: 'upload-1',
  receipt_image_url: '/uploads/upload-1.png',
  extraction_succeeded: true,
  extracted_data: {
    business_name: 'Paz Gas Station',
    receipt_number: '80513',
    date: '2026-08-22',
    total: '60.13',
    vat: '8.74',
    currency: 'ILS',
    category: 'transport',
    confidence: 0.82,
    warnings: [],
  },
  error_message: null,
}

describe('UploadReceiptPage', () => {
  it('shows a loading state while analyzing, then the confirmation form', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(UPLOAD_URL, async () => {
        await delay(30)
        return HttpResponse.json(successfulExtraction)
      }),
    )

    renderWithProviders(<UploadReceiptPage />)
    await selectFile(user)

    expect(await screen.findByText('מנתח את הקבלה...')).toBeInTheDocument()
    await waitForElementToBeRemoved(() => screen.queryByText('מנתח את הקבלה...'))

    expect(screen.getByText('סקירה ואישור')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Paz Gas Station')).toBeInTheDocument()
  })

  it('shows a clear error state when the upload fails', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(UPLOAD_URL, () =>
        HttpResponse.json({ detail: 'Unsupported file type' }, { status: 422 }),
      ),
    )

    renderWithProviders(<UploadReceiptPage />)
    await selectFile(user)

    expect(await screen.findByText('ההעלאה נכשלה')).toBeInTheDocument()
  })

  it('lets the user confirm the extracted data and save it', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(UPLOAD_URL, () => HttpResponse.json(successfulExtraction)),
      http.post(CONFIRM_URL, () =>
        HttpResponse.json({
          id: 'expense-9',
          business_name: 'Paz Gas Station',
          receipt_number: '80513',
          amount: '60.13',
          vat_amount: '8.74',
          currency: 'ILS',
          category: 'transport',
          expense_date: '2026-08-22',
          payment_method: null,
          notes: null,
          receipt_image_url: '/uploads/upload-1.png',
          extraction_confidence: 0.82,
          extraction_status: 'confirmed',
          created_at: '2026-08-22T10:00:00',
          updated_at: '2026-08-22T10:00:00',
        }),
      ),
    )

    renderWithProviders(<UploadReceiptPage />)
    await selectFile(user)

    await screen.findByText('סקירה ואישור')
    await user.click(screen.getByRole('button', { name: 'אישור ושמירה' }))

    expect(await screen.findByText('ההוצאה נשמרה. מעביר אתכם לרשימת ההוצאות...')).toBeInTheDocument()
  })

  it('shows a clear message when the receipt was already confirmed', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(UPLOAD_URL, () => HttpResponse.json(successfulExtraction)),
      http.post(CONFIRM_URL, () =>
        HttpResponse.json({ detail: 'This receipt has already been confirmed' }, { status: 409 }),
      ),
    )

    renderWithProviders(<UploadReceiptPage />)
    await selectFile(user)

    await screen.findByText('סקירה ואישור')
    await user.click(screen.getByRole('button', { name: 'אישור ושמירה' }))

    await waitFor(() => {
      expect(screen.getByText('הקבלה הזו כבר אושרה ונשמרה בעבר.')).toBeInTheDocument()
    })
  })
})
