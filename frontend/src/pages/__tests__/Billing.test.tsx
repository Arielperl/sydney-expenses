import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { RequirePlan, SubscriptionGate } from '../../components/billing/BillingGate'
import { apiClient } from '../../services/apiClient'
import type { BillingOverview } from '../../services/billingService'
import { activeTrialOverview, noPlanOverview, overviewWith, planCatalog } from '../../test/msw/billingFixtures'
import { server } from '../../test/msw/server'
import { renderWithProviders, screen, waitFor, within } from '../../test/test-utils'
import { BillingPage } from '../BillingPage'
import { PricingPage } from '../PricingPage'
import { SubscriptionsPanel } from '../support-portal/SubscriptionsPanel'

vi.mock('../../contexts/AuthContext', () => ({ useAuth: () => ({ user: { email: 'owner@example.com' }, logout: vi.fn(), reload: vi.fn() }) }))

const API = 'http://localhost:8000/api'
/** Matches a price's accessible label however Intl lays it out ("119 ₪" in Hebrew, with direction marks). */
const price = (amount: string) => (_: string, element: Element | null) =>
  Boolean(element?.classList.contains('sr-only')) && (element?.textContent ?? '').replace(/[\u200e\u200f\s]/g, '') === `${amount}₪`
const serve = (overview: BillingOverview) => server.use(http.get(`${API}/billing/subscription`, () => HttpResponse.json(overview)))

describe('public pricing page', () => {
  it('renders the server catalog with Business recommended and prices excluding VAT', async () => {
    renderWithProviders(<PricingPage />, { route: '/pricing' })
    expect(await screen.getByRole('heading', { level: 1, name: /30 יום להכיר את Sydney/ })).toBeInTheDocument()
    const business = (await screen.findByRole('heading', { name: 'Business' })).closest('article')!
    expect(within(business).getByText('המומלץ ביותר')).toBeInTheDocument()
    expect(within(business).getByText(price('119'))).toBeInTheDocument()
    expect(within(business).getByText('עד 3 חיבורי מכירות')).toBeInTheDocument()
    expect(screen.getAllByText('המומלץ ביותר')).toHaveLength(1)
    expect(screen.getAllByText(/לפני מע״מ/).length).toBeGreaterThanOrEqual(3)
    expect(screen.getByText('לא נבקש כרטיס אשראי במהלך תקופת הניסיון.', { exact: false })).toBeInTheDocument()
    // Member limits are not advertised while members cannot be invited.
    expect(screen.queryByText(/משתמשים/)).not.toBeInTheDocument()
    for (const link of screen.getAllByRole('link', { name: /מתחילים ניסיון חינם/ })) expect(link).toHaveAttribute('href', '/signup')
  })

  it('switches to yearly prices with the real saving', async () => {
    const user = userEvent.setup()
    renderWithProviders(<PricingPage />)
    await screen.findByRole('heading', { name: 'Pro' })
    await user.click(screen.getByRole('radio', { name: /שנתי/ }))
    expect(screen.getByRole('radio', { name: /שנתי/ })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText(price('1,190'))).toBeInTheDocument()
    expect(screen.getByText(/חודשיים במתנה/)).toBeInTheDocument()
    expect(screen.getByText(/במקום.*1,428/)).toBeInTheDocument()
  })

  it('offers a retry when the catalog cannot load', async () => {
    server.use(http.get(`${API}/billing/plans`, () => HttpResponse.json({ detail: 'x' }, { status: 500 })))
    renderWithProviders(<PricingPage />)
    expect(await screen.findByRole('alert')).toHaveTextContent('לא הצלחנו לטעון את המסלולים')
  })
})

describe('onboarding plan step', () => {
  function renderGate() {
    return renderWithProviders(
      <Routes><Route element={<RequirePlan />}><Route path="/app" element={<p>inside the app</p>} /></Route></Routes>,
      { route: '/app' },
    )
  }

  it('asks the owner to choose, with nothing preselected, then starts the trial', async () => {
    let body: unknown = null
    let overview = noPlanOverview
    server.use(
      http.get(`${API}/billing/subscription`, () => HttpResponse.json(overview)),
      http.post(`${API}/billing/trial`, async ({ request }) => {
        body = await request.json()
        overview = activeTrialOverview
        return HttpResponse.json({ status: 'trialing', plan_code: 'business' }, { status: 201 })
      }),
    )
    const user = userEvent.setup()
    renderGate()
    const group = await screen.findByRole('radiogroup', { name: 'בחירת מסלול לתקופת הניסיון' })
    expect(within(group).getAllByRole('radio').every((radio) => !(radio as HTMLInputElement).checked)).toBe(true)
    const submit = screen.getByRole('button', { name: 'התחלת תקופת הניסיון' })
    expect(submit).toBeDisabled()
    await user.click(within(group).getByRole('radio', { name: 'Business' }))
    expect(screen.getByText(/תקופת ניסיון עד/)).toBeInTheDocument()
    await user.click(submit)
    await waitFor(() => expect(body).toEqual({ plan_code: 'business', interval: 'month' }))
    expect(await screen.findByText('inside the app')).toBeInTheDocument()
  })

  it('shows the server reason when a plan cannot hold the business', async () => {
    serve(noPlanOverview)
    server.use(http.post(`${API}/billing/trial`, () => HttpResponse.json(
      { detail: { message: 'במסלול Starter אפשר עד 1 חיבורי מכירות. כרגע יש 2.', limit: 'connections', allowed: 1, current: 2 } }, { status: 403 })))
    const user = userEvent.setup()
    renderGate()
    await user.click(await screen.findByRole('radio', { name: 'Starter' }))
    await user.click(screen.getByRole('button', { name: 'התחלת תקופת הניסיון' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('במסלול Starter אפשר עד 1 חיבורי מכירות')
  })

  it('never blocks the app when billing cannot be read', async () => {
    server.use(http.get(`${API}/billing/subscription`, () => HttpResponse.json({ detail: 'down' }, { status: 500 })))
    renderGate()
    expect(await screen.findByText('inside the app', {}, { timeout: 4000 })).toBeInTheDocument()
  })
})

describe('subscription gate', () => {
  function renderProduct(route = '/app') {
    return renderWithProviders(
      <Routes><Route element={<SubscriptionGate />}><Route path="/app" element={<p>dashboard data</p>} /><Route path="/sales" element={<p>sales data</p>} /></Route></Routes>,
      { route },
    )
  }

  it('shows the trial end date on the dashboard only while the trial is far from ending', async () => {
    serve(activeTrialOverview)
    renderProduct('/app')
    expect(await screen.findByText(/תקופת הניסיון שלך פעילה עד 20 באוקטובר 2026/)).toBeInTheDocument()
    expect(screen.getByText(/נותרו 24 ימים/)).toBeInTheDocument()
  })

  it('reminds on every screen in the last week', async () => {
    serve(overviewWith({ subscription: { trial_days_remaining: 5 } }))
    renderProduct('/sales')
    expect(await screen.findByRole('alert')).toHaveTextContent('הוסיפו אמצעי תשלום')
    expect(screen.getByText('sales data')).toBeInTheDocument()
  })

  it('locks the product only when the server enforces it, and keeps data messaging honest', async () => {
    serve(overviewWith({ enforcement_enabled: true, subscription: { status: 'expired' }, access: { allowed: false, reason: 'trial_expired' } }))
    renderProduct('/app')
    expect(await screen.findByRole('heading', { name: 'תקופת הניסיון הסתיימה' })).toBeInTheDocument()
    expect(screen.getByText('הנתונים שלך שמורים. כדי להמשיך להשתמש במערכת, יש לבחור מסלול ולהשלים את התשלום.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'בחירת מסלול' })).toHaveAttribute('href', '/billing')
    expect(screen.getByRole('link', { name: /פנייה לתמיכה/ })).toHaveAttribute('href', '/support/request')
    expect(screen.queryByText('dashboard data')).not.toBeInTheDocument()
  })

  it('does not lock anyone out while enforcement is off', async () => {
    serve(overviewWith({ enforcement_enabled: false, subscription: { status: 'expired' }, access: { allowed: false, reason: 'trial_expired' } }))
    renderProduct('/app')
    expect(await screen.findByRole('alert')).toHaveTextContent('תקופת הניסיון הסתיימה')
    expect(screen.getByText('dashboard data')).toBeInTheDocument()
  })

  it('re-reads the subscription when any API call answers 402', async () => {
    let calls = 0
    server.use(
      http.get(`${API}/billing/subscription`, () => { calls += 1; return HttpResponse.json(activeTrialOverview) }),
      http.get(`${API}/sales`, () => HttpResponse.json({ detail: 'x', code: 'subscription_required', reason: 'trial_expired' }, { status: 402 })),
    )
    renderProduct('/app')
    await waitFor(() => expect(calls).toBe(1))
    await apiClient.get('/sales').catch(() => undefined)
    await waitFor(() => expect(calls).toBe(2))
  })
})

describe('billing page', () => {
  it('presents the trial, dates in the business timezone, usage and an honest payment state', async () => {
    serve(activeTrialOverview)
    renderWithProviders(<BillingPage />, { route: '/billing' })
    expect(await screen.findByText('תקופת הניסיון שלך פעילה עד 20 באוקטובר 2026')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'מנוי וחיוב' })).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'התקדמות תקופת הניסיון' })).toHaveAttribute('aria-valuetext', 'נותרו 24 ימים')
    expect(screen.getByRole('progressbar', { name: 'שאלות לעוזר ה־AI החודש' })).toHaveAttribute('aria-valuenow', '212')
    expect(screen.getByText('לא נוסף אמצעי תשלום')).toBeInTheDocument()
    // No provider yet: the button is visibly unavailable and explains why, instead of failing on click.
    expect(screen.getByRole('button', { name: /הוספת אמצעי תשלום/ })).toBeDisabled()
    expect(screen.getByText('תשלום מקוון יתאפשר בקרוב')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'ביטול החידוש' })).not.toBeInTheDocument()
  })

  it('opens hosted checkout with an idempotency key when a provider is available', async () => {
    serve(overviewWith({ billing_available: true }))
    let key: string | null = null
    server.use(http.post(`${API}/billing/checkout`, ({ request }) => {
      key = request.headers.get('Idempotency-Key')
      return HttpResponse.json({ detail: 'ספק החיוב אינו זמין כרגע. לא בוצע חיוב. נסו שוב בעוד מספר דקות.' }, { status: 502 })
    }))
    const user = userEvent.setup()
    renderWithProviders(<BillingPage />)
    await user.click(await screen.findByRole('button', { name: /הוספת אמצעי תשלום/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('לא בוצע חיוב')
    expect(key).toMatch(/.{16,}/)
  })

  it('waits for the provider to confirm after returning from checkout', async () => {
    serve(activeTrialOverview)
    renderWithProviders(<BillingPage />, { route: '/billing?checkout=success' })
    expect(await screen.findByText('מאשרים את התשלום מול ספק החיוב')).toBeInTheDocument()
  })

  it('confirms once the payment method is recorded', async () => {
    serve(overviewWith({ subscription: { payment_method_on_file: true } }))
    renderWithProviders(<BillingPage />, { route: '/billing?checkout=success' })
    expect(await screen.findByText('התשלום אושר')).toBeInTheDocument()
  })

  it('says plainly that nothing was charged when checkout was abandoned', async () => {
    serve(activeTrialOverview)
    renderWithProviders(<BillingPage />, { route: '/billing?checkout=canceled' })
    expect(await screen.findByText('לא בוצע חיוב. אפשר לנסות שוב בכל עת.')).toBeInTheDocument()
  })

  it('shows a failed renewal as past due with a way to fix it', async () => {
    serve(overviewWith({
      billing_available: true,
      subscription: { status: 'past_due', trial_days_remaining: null, current_period_end: '2026-10-20T09:00:00Z', payment_method_on_file: true },
      access: { allowed: true, reason: 'past_due' },
    }))
    renderWithProviders(<BillingPage />)
    expect(await screen.findByText('התשלום נכשל')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /עדכון אמצעי תשלום/ })).toBeEnabled()
  })

  it('cancels renewal at the end of the paid period, after confirmation', async () => {
    let active = overviewWith({
      subscription: { status: 'active', trial_days_remaining: null, current_period_start: '2026-09-20T09:00:00Z', current_period_end: '2026-10-20T09:00:00Z', payment_method_on_file: true },
      access: { allowed: true, reason: 'active' },
    })
    let cancelled = false
    server.use(
      http.get(`${API}/billing/subscription`, () => HttpResponse.json(active)),
      http.post(`${API}/billing/cancel`, () => {
        cancelled = true
        active = { ...active, subscription: { ...active.subscription!, cancel_at_period_end: true } }
        return HttpResponse.json({ status: 'active', cancel_at_period_end: true })
      }),
    )
    const user = userEvent.setup()
    renderWithProviders(<BillingPage />)
    await user.click(await screen.findByRole('button', { name: 'ביטול החידוש' }))
    const dialog = screen.getByRole('dialog')
    expect(dialog).toHaveTextContent('המנוי ימשיך לפעול עד 20 באוקטובר 2026')
    await user.click(within(dialog).getByRole('button', { name: 'ביטול החידוש' }))
    await waitFor(() => expect(cancelled).toBe(true))
    expect(await screen.findByText(/החידוש בוטל. המנוי ימשיך לפעול עד 20 באוקטובר 2026/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'חידוש המנוי' })).toBeInTheDocument()
  })

  it('changes plan through a dialog with no plan preselected', async () => {
    serve(activeTrialOverview)
    let body: unknown = null
    server.use(http.post(`${API}/billing/plan`, async ({ request }) => { body = await request.json(); return HttpResponse.json({ status: 'trialing', plan_code: 'pro' }) }))
    const user = userEvent.setup()
    renderWithProviders(<BillingPage />)
    await user.click(await screen.findByRole('button', { name: 'החלפת מסלול' }))
    const dialog = screen.getByRole('dialog', { name: 'החלפת מסלול' })
    expect(within(dialog).getByText('המסלול הנוכחי')).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: 'בחרו מסלול' })).toBeDisabled()
    await user.click(within(dialog).getByRole('radio', { name: 'Pro' }))
    await user.click(within(dialog).getByRole('button', { name: 'מעבר למסלול Pro' }))
    await waitFor(() => expect(body).toEqual({ plan_code: 'pro', interval: 'month' }))
  })

  it('lets members see the plan but only owners manage it', async () => {
    serve(overviewWith({ can_manage: false }))
    renderWithProviders(<BillingPage />)
    expect(await screen.findByText(/רק בעלי העסק יכולים לנהל את המנוי/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'החלפת מסלול' })).not.toBeInTheDocument()
  })
})

describe('staff subscriptions panel', () => {
  const rows = [{
    business_id: 'b1', business_name: 'Studio Noa', plan_code: 'business', status: 'trialing', effective_status: 'trialing',
    trial_ends_at: '2026-10-20T09:00:00Z', current_period_end: null, cancel_at_period_end: false, payment_method_on_file: false, access_allowed: true,
  }]

  it('is read-only for support staff', async () => {
    server.use(http.get(`${API}/support/staff/billing/subscriptions`, () => HttpResponse.json(rows)))
    renderWithProviders(<SubscriptionsPanel canOverride={false} />)
    expect(await screen.findByText('Studio Noa')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /שינוי ידני/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /היסטוריה/ })).toBeInTheDocument()
  })

  it('requires a reason for every superadmin override', async () => {
    let body: unknown = null
    server.use(
      http.get(`${API}/support/staff/billing/subscriptions`, () => HttpResponse.json(rows)),
      http.post(`${API}/support/staff/billing/subscriptions/b1/overrides`, async ({ request }) => { body = await request.json(); return HttpResponse.json({ status: 'trialing' }) }),
    )
    const user = userEvent.setup()
    renderWithProviders(<SubscriptionsPanel canOverride />)
    await user.click(await screen.findByRole('button', { name: /שינוי ידני/ }))
    const dialog = screen.getByRole('dialog')
    await user.click(within(dialog).getByRole('radio', { name: /הארכת תקופת הניסיון/ }))
    const apply = within(dialog).getByRole('button', { name: 'החלת השינוי' })
    expect(apply).toBeDisabled()
    await user.type(within(dialog).getByLabelText('סיבה'), 'תקלה בחיבור Grow')
    await user.click(apply)
    await waitFor(() => expect(body).toEqual({ action: 'extend_trial', reason: 'תקלה בחיבור Grow', days: 14 }))
  })
})

describe('plan catalog fixture', () => {
  it('matches the server contract shape used by the UI', () => {
    expect(planCatalog.plans.map((plan) => plan.code)).toEqual(['starter', 'business', 'pro'])
  })
})
