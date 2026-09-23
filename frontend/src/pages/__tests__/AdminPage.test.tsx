import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it, vi } from 'vitest'

import { AdminPage } from '../AdminPage'
import { server } from '../../test/msw/server'
import { renderWithProviders, screen, waitFor } from '../../test/test-utils'

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ user: { id: 'admin-user', email: 'admin@example.com', system_role: 'admin' } }),
}))

const BUSINESSES_URL = 'http://localhost:8000/api/admin/businesses'

describe('AdminPage', () => {
  it('confirms provider removal and refreshes the business provider list', async () => {
    let providerRemoved = false
    let deleteCalled = false
    server.use(
      http.get(BUSINESSES_URL, () => HttpResponse.json([{
        id: 'business-1',
        name: 'מסעדת הבדיקה',
        business_number: null,
        created_at: '2026-09-23T10:00:00',
        owner_emails: ['owner@example.com'],
        payment_providers: providerRemoved ? [] : ['cardcom'],
        member_count: 1,
        sale_count: 3,
        connection_count: 1,
      }])),
      http.delete(`${BUSINESSES_URL}/business-1/payment-providers/cardcom`, () => {
        deleteCalled = true
        providerRemoved = true
        return HttpResponse.json({ provider: 'cardcom', removed: true, disabled_connections: 1 })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<AdminPage />, { route: '/admin' })

    await user.click(await screen.findByRole('button', { name: 'הסרת Cardcom מהעסק מסעדת הבדיקה' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('כל החיבורים הקיימים שלה יושבתו מיד')
    await user.click(screen.getByRole('button', { name: 'הסרת החברה' }))

    await waitFor(() => expect(deleteCalled).toBe(true))
    expect(await screen.findByRole('button', { name: 'הוספת Cardcom' })).toBeInTheDocument()
  })
})
