import { ArrowLeft, CalendarClock, CircleAlert, LifeBuoy, ShieldCheck } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, Outlet, useLocation } from 'react-router-dom'

import { useBillingOverview } from '../../hooks/useBillingOverview'
import { billingState, formatBillingDate, isLocked, planByCode, type BillingState } from '../../lib/billing'
import type { BillingOverview } from '../../services/billingService'
import { PlanSelectionStep } from '../../pages/PlanSelectionStep'
import { buttonClasses, cx } from '../ui-classes'

/**
 * Between sign-in and the app: an owner whose business has no plan yet picks
 * one (onboarding step 2). Billing trouble never blocks the app here: if the
 * overview cannot load, the server remains the one that enforces access.
 */
export function RequirePlan() {
  const overview = useBillingOverview()
  if (overview.isPending) return <div className="auth-state" dir="rtl" role="status">טוענים את סביבת העבודה…</div>
  if (overview.data && !overview.data.subscription && overview.data.can_manage) return <PlanSelectionStep overview={overview.data} />
  return <Outlet />
}

const BANNER_ICON: Partial<Record<BillingState, typeof CalendarClock>> = {
  trialing: CalendarClock,
  trial_ending: CalendarClock,
  past_due: CircleAlert,
}

function TrialBanner({ overview, pathname }: { overview: BillingOverview; pathname: string }) {
  const { t, i18n } = useTranslation()
  const state = billingState(overview)
  const sub = overview.subscription
  const date = (iso: string | null | undefined) => (iso ? formatBillingDate(iso, overview.business_timezone, i18n.language) : '')
  let tone: 'brand' | 'warning' | 'danger'
  let message: string
  if (isLocked(overview) && !overview.enforcement_enabled) {
    tone = 'warning'
    message = t('billing.banner.notEnforced')
  } else if (state === 'trialing' && sub?.trial_ends_at && pathname === '/app' && !sub.payment_method_on_file) {
    tone = 'brand'
    message = t('billing.banner.trialing', { date: date(sub.trial_ends_at) })
  } else if (state === 'trial_ending' && sub?.trial_ends_at) {
    tone = 'warning'
    message = t('billing.banner.trial_ending', { date: date(sub.trial_ends_at) })
  } else if (state === 'past_due') {
    tone = 'danger'
    message = t('billing.banner.past_due')
  } else {
    return null
  }
  const Icon = BANNER_ICON[state] ?? CircleAlert
  const days = sub?.trial_days_remaining
  return (
    <div
      role={tone === 'brand' ? 'status' : 'alert'}
      className={cx(
        'mb-6 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border px-4 py-3 text-sm sm:px-5',
        tone === 'brand' && 'border-brand-200/80 bg-brand-50/70 text-brand-900 dark:border-brand-500/20 dark:bg-brand-500/[0.07] dark:text-brand-100',
        tone === 'warning' && 'border-amber-200 bg-amber-50/80 text-amber-950 dark:border-amber-500/25 dark:bg-amber-500/[0.08] dark:text-amber-100',
        tone === 'danger' && 'border-danger-600/20 bg-danger-50 text-danger-700 dark:border-danger-500/25 dark:bg-danger-500/10 dark:text-red-200',
      )}
    >
      <Icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden="true" />
      <p className="min-w-0 flex-1 leading-relaxed">
        {message}
        {(state === 'trialing' || state === 'trial_ending') && typeof days === 'number' && (
          <span className="figure ms-2 whitespace-nowrap opacity-75">· {t('billing.daysLeft', { count: days })}</span>
        )}
      </p>
      <Link to="/billing" className="inline-flex shrink-0 items-center gap-1.5 font-semibold underline-offset-4 hover:underline">
        {t('billing.banner.manage')}
        <ArrowLeft className="h-4 w-4 ltr:rotate-180" aria-hidden="true" />
      </Link>
    </div>
  )
}

function SubscriptionRequiredScreen({ overview }: { overview: BillingOverview }) {
  const { t, i18n } = useTranslation()
  const state = billingState(overview)
  const heading = state === 'canceled' ? 'canceled' : state === 'trial_unavailable' ? 'trial_unavailable' : 'trial_expired'
  const sub = overview.subscription
  const plan = planByCode(overview.plans, sub?.plan_code)
  const endedIso = state === 'trial_expired' ? sub?.trial_ends_at : sub?.ended_at ?? sub?.current_period_end
  return (
    <section aria-labelledby="subscription-required-heading" className="mx-auto max-w-xl py-6 sm:py-12">
      <div className="rounded-2xl border border-zinc-200/80 bg-white p-6 shadow-card sm:p-10 dark:border-zinc-800 dark:bg-zinc-900">
        <span className="grid h-12 w-12 place-items-center rounded-xl bg-zinc-100 text-zinc-700 ring-1 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-200 dark:ring-zinc-700" aria-hidden="true">
          <CalendarClock className="h-5 w-5" />
        </span>
        {plan && (
          <p className="mt-6 text-xs font-medium text-zinc-500 dark:text-zinc-400">
            <bdi dir="ltr">{plan.name}</bdi>
            {endedIso && <> · {t('billing.locked.endedOn', { date: formatBillingDate(endedIso, overview.business_timezone, i18n.language) })}</>}
          </p>
        )}
        <h1 id="subscription-required-heading" className={cx('text-[1.625rem] leading-tight font-semibold tracking-[-0.015em] text-zinc-900 dark:text-zinc-50', plan ? 'mt-1.5' : 'mt-6')}>
          {t(`billing.locked.${heading}`)}
        </h1>
        <p className="mt-3 text-[0.9375rem] leading-relaxed text-zinc-600 dark:text-zinc-300">
          {overview.can_manage ? t('billing.locked.text') : t('billing.locked.memberText')}
        </p>
        <div className="mt-6 flex items-start gap-3 rounded-xl bg-zinc-50 px-4 py-3.5 text-sm leading-relaxed text-zinc-700 ring-1 ring-zinc-200/70 ring-inset dark:bg-zinc-950/40 dark:text-zinc-300 dark:ring-zinc-800">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400" aria-hidden="true" />
          <span>{t('billing.locked.kept')}</span>
        </div>
        <div className="mt-8 flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
          {overview.can_manage && (
            <Link to="/billing" className={buttonClasses('primary', 'lg', 'sm:min-w-44')}>
              {t('billing.locked.choosePlan')}
            </Link>
          )}
          <Link to="/support/request" className={buttonClasses('ghost', 'lg')}>
            <LifeBuoy className="h-4 w-4" aria-hidden="true" />
            {t('billing.locked.contactSupport')}
          </Link>
        </div>
      </div>
    </section>
  )
}

/**
 * Wraps the product screens. When the server enforces billing and access has
 * lapsed, the screen explains why and how to continue; data is never hidden
 * behind anything but this notice, and billing and support stay reachable.
 */
export function SubscriptionGate() {
  const { pathname } = useLocation()
  const overview = useBillingOverview()
  const data = overview.data
  // A member (not the owner) of a business with no plan is locked too: only the owner can choose one.
  const locked = data && !data.access.allowed && (isLocked(data) || !data.can_manage)
  if (data && data.enforcement_enabled && locked) return <SubscriptionRequiredScreen overview={data} />
  return (
    <>
      {data && <TrialBanner overview={data} pathname={pathname} />}
      <Outlet />
    </>
  )
}
