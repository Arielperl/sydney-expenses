import type { BillingOverview, BillingPlan, PlanCatalog } from '../../services/billingService'

// Mirrors GET /api/billing/plans for tests only; the app itself always reads the server's catalog.
const plans: BillingPlan[] = [
  {
    code: 'starter', name: 'Starter', tagline: 'לעסק קטן שרוצה לראות ולנהל את ההכנסות במקום אחד', recommended: true,
    prices: { month: 6_900, year: 69_000 }, max_connections: 1, max_members: 1, ai_questions_per_month: 300,
    features: ['לוח בקרה של הכנסות, מע״מ, עמלות וזיכויים', 'פירוט המכירות ופרטי הלקוחות במקום אחד', 'זיהוי עסקאות שנכשלו או שחסר בהן מידע', 'עוזר עסקי שעונה על שאלות לפי נתוני המכירות'],
  },
  {
    code: 'business', name: 'Business', tagline: 'לעסק שמקבל תשלומים מכמה מקומות', recommended: false,
    prices: { month: 11_900, year: 119_000 }, max_connections: 3, max_members: 5, ai_questions_per_month: 1_500,
    features: ['כל מה שיש ב־Starter', 'תמונה מאוחדת מכמה מקורות מכירה'],
  },
  {
    code: 'pro', name: 'Pro', tagline: 'לעסק עם פעילות רחבה ומספר מערכות מכירה', recommended: false,
    prices: { month: 24_900, year: 249_000 }, max_connections: 10, max_members: 15, ai_questions_per_month: 5_000,
    features: ['כל מה שיש ב־Business', 'מתאים לעסקים עם כמה מקורות מכירה'],
  },
]

export const planCatalog: PlanCatalog = {
  plans, trial_days: 30, currency: 'ILS', vat_rate: '0.18', prices_exclude_vat: true, member_limits_available: false,
}

export const noPlanOverview: BillingOverview = {
  business_timezone: 'Asia/Jerusalem',
  can_manage: true,
  billing_available: false,
  enforcement_enabled: false,
  trial_days: 30,
  plans,
  subscription: null,
  access: { allowed: false, reason: 'plan_required' },
  usage: null,
}

export const activeTrialOverview: BillingOverview = {
  ...noPlanOverview,
  subscription: {
    plan_code: 'business', billing_interval: 'month', status: 'trialing',
    trial_started_at: '2026-09-20T09:00:00Z', trial_ends_at: '2026-10-20T09:00:00Z', trial_days_remaining: 24,
    current_period_start: null, current_period_end: null, cancel_at_period_end: false, canceled_at: null, ended_at: null,
    pending_plan_code: null, payment_method_on_file: false, checkout_pending: false,
  },
  access: { allowed: true, reason: 'trialing' },
  usage: {
    ai_questions: { used: 212, limit: 1_500, period_start: '2026-09-20T09:00:00Z', period_end: '2026-10-20T09:00:00Z' },
    connections: { used: 2, limit: 3 },
    members: { used: 1, limit: 5 },
  },
}

export function overviewWith(patch: Partial<Omit<BillingOverview, 'subscription'>> & { subscription?: Partial<NonNullable<BillingOverview['subscription']>> | null }): BillingOverview {
  const { subscription, ...rest } = patch
  return {
    ...activeTrialOverview,
    ...rest,
    subscription: subscription === null ? null : { ...activeTrialOverview.subscription!, ...subscription },
  }
}
