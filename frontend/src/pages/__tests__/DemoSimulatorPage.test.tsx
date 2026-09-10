import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { DemoSimulatorPage } from '../DemoSimulatorPage'
import { server } from '../../test/msw/server'
import { makeSale } from '../../test/msw/handlers'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

const CAPABILITIES_URL = 'http://localhost:8000/api/system/capabilities'
const SIMULATE_URL = 'http://localhost:8000/api/demo/simulate'
const RESET_PREVIEW_URL = 'http://localhost:8000/api/demo/reset-preview'
const RESET_URL = 'http://localhost:8000/api/demo/reset'

function capabilitiesResponse(demoEnabled: boolean) {
  return {
    receipt_extraction_provider: 'mock',
    receipt_extraction_mode: 'demo',
    real_ai_enabled: false,
    ollama_available: null,
    tesseract_available: null,
    demo_simulator_enabled: demoEnabled,
  }
}

describe('DemoSimulatorPage', () => {
  it('shows a disabled message when the demo simulator is not available (production)', async () => {
    server.use(http.get(CAPABILITIES_URL, () => HttpResponse.json(capabilitiesResponse(false))))
    renderWithProviders(<DemoSimulatorPage />)

    await waitFor(() => expect(screen.getByText('מדמה ההדגמה אינו זמין')).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'הפעלת התרחיש' })).not.toBeInTheDocument()
  })

  it('runs a scenario and shows a success message linking to Sales', async () => {
    server.use(
      http.get(CAPABILITIES_URL, () => HttpResponse.json(capabilitiesResponse(true))),
      http.post(SIMULATE_URL, () =>
        HttpResponse.json({ sale: makeSale({ source: 'demo' }), scenario: 'succeeded' }, { status: 201 }),
      ),
    )
    const user = userEvent.setup()
    renderWithProviders(<DemoSimulatorPage />)

    await waitFor(() => expect(screen.getByRole('button', { name: 'הפעלת התרחיש' })).toBeInTheDocument())
    await user.type(screen.getByLabelText(/שם הלקוח/), 'דנה כהן')
    await user.type(screen.getByLabelText(/מוצר או שירות/), 'ייעוץ עסקי')
    await user.click(screen.getByRole('button', { name: 'הפעלת התרחיש' }))

    await waitFor(() => expect(screen.getByText('מכירת הדגמה נוצרה.')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: 'צפייה במכירות' })).toHaveAttribute('href', '/sales')
  })

  it('shows the demo-sale count before confirming reset, and reports the deleted count after', async () => {
    server.use(
      http.get(CAPABILITIES_URL, () => HttpResponse.json(capabilitiesResponse(true))),
      http.get(RESET_PREVIEW_URL, () => HttpResponse.json({ demo_sales_count: 3 })),
      http.post(RESET_URL, () => HttpResponse.json({ deleted_sales_count: 3, deleted_events_count: 7 })),
    )
    const user = userEvent.setup()
    renderWithProviders(<DemoSimulatorPage />)

    await waitFor(() => expect(screen.getByRole('button', { name: /איפוס נתוני הדגמה/ })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /איפוס נתוני הדגמה/ }))

    await waitFor(() =>
      expect(screen.getByText('פעולה זו תמחק לצמיתות 3 מכירות הדגמה ואת היסטוריית האירועים שלהן.')).toBeInTheDocument(),
    )
    await user.click(screen.getByRole('button', { name: 'מחיקת נתוני הדגמה' }))

    await waitFor(() => expect(screen.getByText('נמחקו 3 מכירות הדגמה.')).toBeInTheDocument())
  })

  it('closes the reset dialog on cancel without calling reset', async () => {
    let resetCalled = false
    server.use(
      http.get(CAPABILITIES_URL, () => HttpResponse.json(capabilitiesResponse(true))),
      http.get(RESET_PREVIEW_URL, () => HttpResponse.json({ demo_sales_count: 1 })),
      http.post(RESET_URL, () => {
        resetCalled = true
        return HttpResponse.json({ deleted_sales_count: 1, deleted_events_count: 1 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<DemoSimulatorPage />)

    await waitFor(() => expect(screen.getByRole('button', { name: /איפוס נתוני הדגמה/ })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /איפוס נתוני הדגמה/ }))
    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'ביטול' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(resetCalled).toBe(false)
  })
})
