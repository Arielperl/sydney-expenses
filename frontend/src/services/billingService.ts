import { apiClient, toApiError } from './apiClient'

export type BillingInterval = 'month' | 'year'
export type SubscriptionStatus = 'trialing' | 'active' | 'past_due' | 'canceled' | 'expired'
export type AccessReason =
  | 'plan_required'
  | 'trialing'
  | 'payment_processing'
  | 'active'
  | 'renewal_processing'
  | 'past_due'
  | 'trial_expired'
  | 'subscription_required'
  | 'canceled'

/** A plan exactly as the server defines it. Prices are in agorot and exclude VAT. */
export type BillingPlan = {
  code: string
  name: string
  tagline: string
  recommended: boolean
  prices: Partial<Record<BillingInterval, number>>
  max_connections: number
  max_members: number
  ai_questions_per_month: number
  features: string[]
}

export type PlanCatalog = {
  plans: BillingPlan[]
  trial_days: number
  currency: string
  vat_rate: string
  prices_exclude_vat: boolean
  member_limits_available: boolean
}

export type UsageMeter = { used: number; limit: number; period_start?: string; period_end?: string }

export type BusinessSubscription = {
  plan_code: string
  billing_interval: BillingInterval
  status: SubscriptionStatus
  trial_started_at: string | null
  trial_ends_at: string | null
  trial_days_remaining: number | null
  current_period_start: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
  canceled_at: string | null
  ended_at: string | null
  pending_plan_code: string | null
  payment_method_on_file: boolean
  checkout_pending: boolean
}

export type BillingOverview = {
  business_timezone: string
  can_manage: boolean
  billing_available: boolean
  enforcement_enabled: boolean
  trial_days: number
  plans: BillingPlan[]
  subscription: BusinessSubscription | null
  access: { allowed: boolean; reason: AccessReason }
  usage: { ai_questions: UsageMeter; connections: UsageMeter; members: UsageMeter } | null
}

export type SubscriptionSummary = Pick<BusinessSubscription, 'status' | 'plan_code' | 'billing_interval' | 'cancel_at_period_end' | 'pending_plan_code'>

export const BILLING_QUERY_KEY = ['billing', 'subscription'] as const
export const PLAN_CATALOG_QUERY_KEY = ['billing', 'plans'] as const

async function call<T>(request: () => Promise<{ data: T }>): Promise<T> {
  try {
    return (await request()).data
  } catch (error) {
    throw toApiError(error)
  }
}

export const getPlanCatalog = () => call(() => apiClient.get<PlanCatalog>('/billing/plans'))
export const getBillingOverview = () => call(() => apiClient.get<BillingOverview>('/billing/subscription'))

export const startTrial = (plan_code: string, interval: BillingInterval) =>
  call(() => apiClient.post<SubscriptionSummary>('/billing/trial', { plan_code, interval }))

export const changePlan = (plan_code: string, interval: BillingInterval) =>
  call(() => apiClient.post<SubscriptionSummary>('/billing/plan', { plan_code, interval }))

/**
 * Asks the server for a hosted-checkout link. The idempotency key belongs to one
 * click: a retried request returns the same session instead of opening another.
 */
export const createCheckout = (plan_code: string, interval: BillingInterval, idempotencyKey: string) =>
  call(() => apiClient.post<{ checkout_url: string; status: string }>(
    '/billing/checkout',
    { plan_code, interval },
    { headers: { 'Idempotency-Key': idempotencyKey } },
  ))

export const cancelRenewal = () => call(() => apiClient.post<SubscriptionSummary>('/billing/cancel'))
export const resumeRenewal = () => call(() => apiClient.post<SubscriptionSummary>('/billing/resume'))

// ---------------------------------------------------------------- staff
export type StaffSubscriptionRow = {
  business_id: string
  business_name: string
  plan_code: string | null
  status: SubscriptionStatus | null
  effective_status: SubscriptionStatus | null
  trial_ends_at: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
  payment_method_on_file: boolean
  access_allowed: boolean
}

export type SubscriptionEventRow = {
  sequence: number
  event_type: string
  from_status: string | null
  to_status: string | null
  from_plan: string | null
  to_plan: string | null
  source: 'owner' | 'provider' | 'system' | 'admin'
  actor_user_id: string | null
  reason: string | null
  details: Record<string, unknown> | null
  created_at: string
}

export type OverrideAction = 'extend_trial' | 'change_plan' | 'grant_access' | 'end_now'
export type OverrideRequest = { action: OverrideAction; reason: string; days?: number; plan_code?: string; until?: string }

export const listStaffSubscriptions = () => call(() => apiClient.get<StaffSubscriptionRow[]>('/support/staff/billing/subscriptions'))
export const listSubscriptionEvents = (businessId: string) =>
  call(() => apiClient.get<SubscriptionEventRow[]>(`/support/staff/billing/subscriptions/${encodeURIComponent(businessId)}/events`))
export const applySubscriptionOverride = (businessId: string, body: OverrideRequest) =>
  call(() => apiClient.post<SubscriptionSummary>(`/support/staff/billing/subscriptions/${encodeURIComponent(businessId)}/overrides`, body))
