import type { BadgeTone } from '../components/ui'
import type { BillingInterval, BillingOverview, BillingPlan } from '../services/billingService'
import { intlLocale } from './format'

/** Days before the trial ends when reminders to add a payment method start. */
export const TRIAL_REMINDER_DAYS = 7

/**
 * One display state per situation the owner can be in. Every screen (sidebar,
 * banner, billing page, lock screen) derives from this so they never disagree.
 */
export type BillingState =
  | 'plan_required'
  | 'trialing'
  | 'trial_ending'
  | 'payment_processing'
  | 'active'
  | 'canceling'
  | 'renewal_processing'
  | 'past_due'
  | 'trial_expired'
  | 'trial_unavailable'
  | 'canceled'

export function billingState(overview: BillingOverview): BillingState {
  const { subscription: sub, access } = overview
  if (!sub) return 'plan_required'
  switch (access.reason) {
    case 'trialing': {
      const days = sub.trial_days_remaining ?? 0
      return days <= TRIAL_REMINDER_DAYS && !sub.payment_method_on_file ? 'trial_ending' : 'trialing'
    }
    case 'payment_processing':
    case 'renewal_processing':
    case 'past_due':
    case 'trial_expired':
    case 'canceled':
      return access.reason
    case 'subscription_required':
      return 'trial_unavailable'
    case 'active':
      return sub.cancel_at_period_end ? 'canceling' : 'active'
    default:
      return 'plan_required'
  }
}

export const STATE_TONE: Record<BillingState, BadgeTone> = {
  plan_required: 'neutral',
  trialing: 'brand',
  trial_ending: 'warning',
  payment_processing: 'info',
  active: 'success',
  canceling: 'warning',
  renewal_processing: 'info',
  past_due: 'danger',
  trial_expired: 'danger',
  trial_unavailable: 'danger',
  canceled: 'neutral',
}

/** Whether the product is (or would be) locked for this business. */
export function isLocked(overview: BillingOverview): boolean {
  return !overview.access.allowed && overview.access.reason !== 'plan_required'
}

export function planByCode(plans: BillingPlan[], code: string | null | undefined): BillingPlan | undefined {
  return plans.find((plan) => plan.code === code)
}

export function priceFor(plan: BillingPlan, interval: BillingInterval): number | null {
  return plan.prices[interval] ?? null
}

/** Agorot → a whole-shekel amount when exact ("₪119"), otherwise two decimals. */
export function formatPlanPrice(minor: number, language: string, currency = 'ILS'): string {
  const amount = minor / 100
  const whole = Number.isInteger(amount)
  return new Intl.NumberFormat(intlLocale(language), {
    style: 'currency',
    currency,
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(amount)
}

/** The same amount split so the currency sign can be set smaller than the figure. */
export function planPriceParts(minor: number, language: string, currency = 'ILS'): { text: string; currency: boolean }[] {
  const amount = minor / 100
  const whole = Number.isInteger(amount)
  const parts = new Intl.NumberFormat(intlLocale(language), {
    style: 'currency', currency, minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: whole ? 0 : 2,
  }).formatToParts(amount)
  return parts
    .filter((part) => part.type !== 'literal' || part.value.trim() !== '')
    .map((part) => ({ text: part.value.replace(/[\u200e\u200f]/g, ''), currency: part.type === 'currency' }))
}

/** The amount including VAT, for the small print only. The server's price excludes VAT. */
export function withVat(minor: number, vatRate: string | number = '0.18'): number {
  return Math.round(minor * (1 + Number(vatRate)))
}

/** Months a yearly price saves against paying monthly for twelve months (e.g. 2). */
export function yearlySavingsMonths(plan: BillingPlan): number | null {
  const month = plan.prices.month
  const year = plan.prices.year
  if (!month || !year || year >= month * 12) return null
  const saved = (month * 12 - year) / month
  return Number.isInteger(saved) ? saved : null
}

/** The saving to advertise on the yearly toggle, only when every plan offers the same one. */
export function catalogSavingsMonths(plans: BillingPlan[]): number | null {
  const values = plans.map(yearlySavingsMonths)
  return values.length > 0 && values.every((value) => value !== null && value === values[0]) ? values[0] : null
}

/** Server timestamps are naive-UTC ISO strings ending in Z. */
export function parseBillingDate(iso: string): Date {
  return new Date(iso)
}

/** "26 באוקטובר 2026", in the business's timezone (not the viewer's). */
export function formatBillingDate(iso: string, timeZone: string, language: string): string {
  const options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long', year: 'numeric', timeZone }
  try {
    return new Intl.DateTimeFormat(intlLocale(language), options).format(parseBillingDate(iso))
  } catch {
    return new Intl.DateTimeFormat(intlLocale(language), { ...options, timeZone: 'Asia/Jerusalem' }).format(parseBillingDate(iso))
  }
}

export function formatCount(value: number, language: string): string {
  return new Intl.NumberFormat(intlLocale(language)).format(value)
}

export function newIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}
