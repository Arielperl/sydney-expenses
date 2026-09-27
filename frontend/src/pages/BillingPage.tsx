import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, CircleAlert, CreditCard, Info, Loader2, Lock, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { ChangePlanDialog } from '../components/billing/ChangePlanDialog'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorState } from '../components/StatusStates'
import { Badge, Card, CardHeader, DetailRow, PageHeader, Skeleton } from '../components/ui'
import { buttonClasses, cx } from '../components/ui-classes'
import { useBillingOverview } from '../hooks/useBillingOverview'
import {
  billingState,
  formatBillingDate,
  formatCount,
  formatPlanPrice,
  newIdempotencyKey,
  planByCode,
  priceFor,
  STATE_TONE,
  type BillingState,
} from '../lib/billing'
import {
  BILLING_QUERY_KEY,
  cancelRenewal,
  createCheckout,
  resumeRenewal,
  type BillingOverview,
  type UsageMeter,
} from '../services/billingService'

const CONFIRMATION_WAIT_MS = 60_000

type Notice = { tone: 'pending' | 'success' | 'neutral' | 'danger'; title: string; text?: string }

function NoticeBar({ notice, onDismiss }: { notice: Notice; onDismiss?: () => void }) {
  const { t } = useTranslation()
  const Icon = notice.tone === 'pending' ? Loader2 : notice.tone === 'success' ? CheckCircle2 : notice.tone === 'danger' ? CircleAlert : Info
  return (
    <div
      role={notice.tone === 'danger' ? 'alert' : 'status'}
      className={cx(
        'flex items-start gap-3 rounded-xl border px-4 py-3.5 text-sm sm:px-5',
        notice.tone === 'pending' && 'border-sky-200 bg-sky-50/70 text-sky-950 dark:border-sky-500/25 dark:bg-sky-500/[0.07] dark:text-sky-100',
        notice.tone === 'success' && 'border-success-500/25 bg-success-50 text-success-700 dark:border-success-500/25 dark:bg-success-500/10 dark:text-emerald-200',
        notice.tone === 'neutral' && 'border-zinc-200 bg-white text-zinc-800 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100',
        notice.tone === 'danger' && 'border-danger-600/20 bg-danger-50 text-danger-700 dark:border-danger-500/25 dark:bg-danger-500/10 dark:text-red-200',
      )}
    >
      <Icon className={cx('mt-0.5 h-4 w-4 shrink-0', notice.tone === 'pending' && 'animate-spin motion-reduce:animate-none')} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{notice.title}</p>
        {notice.text && <p className="mt-0.5 leading-relaxed opacity-85">{notice.text}</p>}
      </div>
      {onDismiss && (
        <button type="button" onClick={onDismiss} aria-label={t('billing.checkout.dismiss')} className="-m-1 grid h-7 w-7 shrink-0 place-items-center rounded-md opacity-70 hover:bg-black/5 hover:opacity-100 dark:hover:bg-white/10">
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
    </div>
  )
}

function Meter({ label, meter, hint }: { label: string; meter: UsageMeter; hint?: ReactNode }) {
  const { t, i18n } = useTranslation()
  const ratio = meter.limit > 0 ? Math.min(1, meter.used / meter.limit) : 0
  const full = meter.used >= meter.limit
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="text-zinc-700 dark:text-zinc-300">{label}</span>
        <span className="figure shrink-0 font-medium text-zinc-900 dark:text-zinc-50">
          {t('billing.usage.of', { used: formatCount(meter.used, i18n.language), limit: formatCount(meter.limit, i18n.language) })}
        </span>
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={meter.limit}
        aria-valuenow={meter.used}
        className="mt-2 h-1.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800"
      >
        <div
          className={cx('h-full rounded-full transition-[width] duration-500 ease-out', full ? 'bg-danger-500' : ratio >= 0.8 ? 'bg-amber-500' : 'bg-brand-500')}
          style={{ width: `${Math.max(ratio * 100, meter.used > 0 ? 2 : 0)}%` }}
        />
      </div>
      <p className="mt-1.5 text-xs text-zinc-500 dark:text-zinc-400">{full ? t('billing.usage.atLimit') : hint}</p>
    </div>
  )
}

function TrialProgress({ overview }: { overview: BillingOverview }) {
  const { t } = useTranslation()
  const sub = overview.subscription
  if (!sub?.trial_started_at || !sub.trial_ends_at || sub.trial_days_remaining === null) return null
  const total = overview.trial_days
  const left = Math.max(0, Math.min(total, sub.trial_days_remaining))
  const ending = billingState(overview) === 'trial_ending'
  return (
    <div className="mt-5">
      <div
        role="progressbar"
        aria-label={t('billing.trialProgress')}
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={total - left}
        aria-valuetext={t('billing.daysLeft', { count: left })}
        className="h-1.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800"
      >
        <div className={cx('h-full rounded-full', ending ? 'bg-amber-500' : 'bg-brand-500')} style={{ width: `${((total - left) / total) * 100}%` }} />
      </div>
      <p className={cx('figure mt-2 text-xs font-medium', ending ? 'text-amber-800 dark:text-amber-300' : 'text-zinc-500 dark:text-zinc-400')}>
        {t('billing.daysLeft', { count: left })}
      </p>
    </div>
  )
}

function summaryFor(state: BillingState, overview: BillingOverview, date: (iso: string | null | undefined) => string, t: (key: string, options?: Record<string, unknown>) => string): string {
  const sub = overview.subscription
  if (!sub) return t('billing.ownerOnly')
  switch (state) {
    case 'trialing':
      return sub.payment_method_on_file
        ? t('billing.summary.trialingWithPayment', { date: date(sub.trial_ends_at) })
        : t('billing.summary.trialing', { date: date(sub.trial_ends_at) })
    case 'trial_ending':
    case 'payment_processing':
    case 'trial_expired':
      return t(`billing.summary.${state}`, { date: date(sub.trial_ends_at) })
    case 'active':
    case 'canceling':
      return t(`billing.summary.${state}`, { date: date(sub.current_period_end) })
    default:
      return t(`billing.summary.${state}`)
  }
}

function BillingSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-3" aria-hidden="true">
      <div className="space-y-6 lg:col-span-2">
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-48 rounded-xl" />
      </div>
      <div className="space-y-6">
        <Skeleton className="h-40 rounded-xl" />
        <Skeleton className="h-52 rounded-xl" />
      </div>
    </div>
  )
}

export function BillingPage() {
  const { t, i18n } = useTranslation()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const checkoutReturn = searchParams.get('checkout')
  const [returnedAt] = useState(() => Date.now())
  const [waitedLong, setWaitedLong] = useState(false)
  const awaitingConfirmation = checkoutReturn === 'success' && !waitedLong
  const overview = useBillingOverview({ poll: awaitingConfirmation ? 3_000 : false })
  const [showChangePlan, setShowChangePlan] = useState(false)
  const [showCancel, setShowCancel] = useState(false)
  const idempotencyKey = useRef<string>(newIdempotencyKey())
  const refresh = () => queryClient.invalidateQueries({ queryKey: BILLING_QUERY_KEY })

  useEffect(() => {
    if (checkoutReturn !== 'success') return
    const timer = window.setTimeout(() => setWaitedLong(true), Math.max(0, CONFIRMATION_WAIT_MS - (Date.now() - returnedAt)))
    return () => window.clearTimeout(timer)
  }, [checkoutReturn, returnedAt])

  const checkout = useMutation({
    mutationFn: ({ plan, interval }: { plan: string; interval: 'month' | 'year' }) => createCheckout(plan, interval, idempotencyKey.current),
    onSuccess: ({ checkout_url }) => window.location.assign(checkout_url),
    onError: () => { idempotencyKey.current = newIdempotencyKey() },
  })
  const cancel = useMutation({ mutationFn: cancelRenewal, onSuccess: async () => { await refresh(); setShowCancel(false) } })
  const resume = useMutation({ mutationFn: resumeRenewal, onSuccess: refresh })

  const dismissReturn = () => setSearchParams({}, { replace: true })

  if (overview.isPending) {
    return (
      <div className="space-y-8" role="status" aria-label={t('billing.loading')}>
        <PageHeader title={t('billing.title')} description={t('billing.description')} />
        <BillingSkeleton />
      </div>
    )
  }
  if (overview.isError) {
    return (
      <div className="space-y-8">
        <PageHeader title={t('billing.title')} description={t('billing.description')} />
        <ErrorState message={t('billing.loadError')} onRetry={() => void overview.refetch()} />
      </div>
    )
  }

  const data = overview.data
  const sub = data.subscription
  const state = billingState(data)
  const plan = planByCode(data.plans, sub?.plan_code)
  const pendingPlan = planByCode(data.plans, sub?.pending_plan_code)
  const date = (iso: string | null | undefined) => (iso ? formatBillingDate(iso, data.business_timezone, i18n.language) : t('billing.dates.none'))
  const price = plan && sub ? priceFor(plan, sub.billing_interval) : null
  const confirmed = Boolean(sub && (sub.payment_method_on_file || state === 'active'))

  let notice: Notice | null = null
  if (checkoutReturn === 'canceled') notice = { tone: 'neutral', title: t('billing.checkout.canceledTitle'), text: t('billing.checkout.canceledText') }
  else if (checkoutReturn === 'success' && confirmed) notice = { tone: 'success', title: t('billing.checkout.successTitle'), text: t('billing.checkout.successText') }
  else if (checkoutReturn === 'success' && waitedLong) notice = { tone: 'neutral', title: t('billing.checkout.slowTitle'), text: t('billing.checkout.slowText') }
  else if (checkoutReturn === 'success') notice = { tone: 'pending', title: t('billing.checkout.pendingTitle'), text: t('billing.checkout.pendingText') }
  if (checkout.isError) notice = { tone: 'danger', title: t('billing.checkout.failedTitle'), text: checkout.error.message }

  const payAction: string | null =
    state === 'trialing' && !sub?.payment_method_on_file ? 'addPayment'
      : state === 'trial_ending' ? 'addPayment'
        : state === 'past_due' ? 'updatePayment'
          : ['trial_expired', 'trial_unavailable', 'canceled'].includes(state) ? 'pay'
            : null
  const renewing = sub && ['trialing', 'active', 'past_due'].includes(sub.status)
  const canCancel = Boolean(renewing && !sub?.cancel_at_period_end && (sub?.payment_method_on_file || sub?.status !== 'trialing'))
  const canResume = Boolean(renewing && sub?.cancel_at_period_end)
  const cancelDate = sub?.status === 'trialing' ? sub?.trial_ends_at : sub?.current_period_end
  const summaryTone = STATE_TONE[state]

  return (
    <div className="space-y-8">
      <PageHeader title={t('billing.title')} description={t('billing.description')} />
      {notice && <NoticeBar notice={notice} onDismiss={notice.tone === 'pending' ? undefined : checkout.isError ? () => checkout.reset() : dismissReturn} />}

      <div className="grid items-start gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card aria-labelledby="billing-plan-heading" className="p-6 sm:p-7">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p id="billing-plan-heading" className="text-sm font-medium text-zinc-500 dark:text-zinc-400">{t('billing.currentPlan')}</p>
              <Badge tone={summaryTone}>{t(`billing.state.${state}`)}</Badge>
            </div>
            <div className="mt-3 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
              <h2 className="text-2xl font-semibold tracking-[-0.01em] text-zinc-900 dark:text-zinc-50"><bdi>{plan?.name ?? "—"}</bdi></h2>
              {price !== null && sub && (
                <p className="flex items-baseline gap-1.5">
                  <bdi className="figure text-2xl font-medium text-zinc-900 dark:text-zinc-50">{formatPlanPrice(price, i18n.language)}</bdi>
                  <span className="text-sm text-zinc-500 dark:text-zinc-400">
                    {t(sub.billing_interval === 'month' ? 'billing.perMonth' : 'billing.perYear')} · {t('billing.excludingVat')}
                  </span>
                </p>
              )}
            </div>
            {plan && <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400" dir="auto">{plan.tagline}</p>}

            <div
              className={cx(
                'mt-6 rounded-xl px-4 py-3.5 text-[0.9375rem] leading-relaxed',
                summaryTone === 'danger' && 'bg-danger-50 text-danger-700 dark:bg-danger-500/10 dark:text-red-200',
                summaryTone === 'warning' && 'bg-amber-50 text-amber-950 dark:bg-amber-500/[0.08] dark:text-amber-100',
                !['danger', 'warning'].includes(summaryTone) && 'bg-zinc-50 text-zinc-800 dark:bg-zinc-950/40 dark:text-zinc-200',
              )}
            >
              {summaryFor(state, data, date, t)}
              {pendingPlan && sub && <span className="mt-1 block text-sm opacity-80">{t('billing.summary.pendingPlan', { plan: pendingPlan.name, date: date(sub.current_period_end) })}</span>}
            </div>
            {(state === 'trialing' || state === 'trial_ending') && <TrialProgress overview={data} />}

            {data.can_manage ? (
              <div className="mt-7 flex flex-col gap-3 border-t border-zinc-100 pt-6 sm:flex-row sm:flex-wrap sm:items-center dark:border-zinc-800">
                {payAction && sub && (
                  <button
                    type="button"
                    className={buttonClasses('primary', 'md')}
                    disabled={!data.billing_available || checkout.isPending}
                    aria-describedby={!data.billing_available ? 'billing-unavailable' : undefined}
                    onClick={() => checkout.mutate({ plan: sub.plan_code, interval: sub.billing_interval })}
                  >
                    <CreditCard className="h-4 w-4" aria-hidden="true" />
                    {checkout.isPending ? t('billing.actions.redirecting') : t(`billing.actions.${payAction}`)}
                  </button>
                )}
                <button type="button" className={buttonClasses('secondary', 'md')} onClick={() => setShowChangePlan(true)}>
                  {t('billing.actions.changePlan')}
                </button>
                {canResume && (
                  <button type="button" className={buttonClasses('subtle', 'md')} disabled={resume.isPending} onClick={() => resume.mutate()}>
                    {t('billing.actions.resumeRenewal')}
                  </button>
                )}
                {canCancel && (
                  <button type="button" className={buttonClasses('ghost', 'md', 'sm:ms-auto')} onClick={() => setShowCancel(true)}>
                    {t('billing.actions.cancelRenewal')}
                  </button>
                )}
              </div>
            ) : (
              <p className="mt-7 flex items-center gap-2 border-t border-zinc-100 pt-6 text-sm text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
                <Lock className="h-4 w-4 shrink-0" aria-hidden="true" />
                {t('billing.ownerOnly')}
              </p>
            )}
            {resume.isError && <p role="alert" className="mt-3 text-sm text-danger-700 dark:text-danger-500">{t('billing.resumeError')}</p>}
            {data.can_manage && payAction && !data.billing_available && (
              <div id="billing-unavailable" className="mt-4 flex items-start gap-3 rounded-xl border border-dashed border-zinc-300 px-4 py-3 text-sm dark:border-zinc-700">
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-zinc-400" aria-hidden="true" />
                <div>
                  <p className="font-medium text-zinc-800 dark:text-zinc-100">{t('billing.paymentUnavailable.title')}</p>
                  <p className="mt-0.5 leading-relaxed text-zinc-500 dark:text-zinc-400">{t('billing.paymentUnavailable.text')}</p>
                </div>
              </div>
            )}
          </Card>

          {sub && (
            <Card aria-labelledby="billing-dates-heading">
              <CardHeader id="billing-dates-heading" title={t('billing.dates.title')} />
              <dl className="divide-y divide-zinc-100 px-5 pb-2 dark:divide-zinc-800">
                {sub.trial_started_at && <DetailRow label={t('billing.dates.trialStart')}><bdi className="figure">{date(sub.trial_started_at)}</bdi></DetailRow>}
                {sub.trial_ends_at && <DetailRow label={t('billing.dates.trialEnd')}><bdi className="figure font-medium">{date(sub.trial_ends_at)}</bdi></DetailRow>}
                <DetailRow label={t('billing.dates.interval')}>{t(`billing.interval.${sub.billing_interval}`)}</DetailRow>
                {sub.current_period_start && <DetailRow label={t('billing.dates.periodStart')}><bdi className="figure">{date(sub.current_period_start)}</bdi></DetailRow>}
                {sub.current_period_end && (
                  <DetailRow label={t(sub.cancel_at_period_end || sub.status !== 'active' ? 'billing.dates.periodEnd' : 'billing.dates.nextRenewal')}>
                    <bdi className="figure font-medium">{date(sub.current_period_end)}</bdi>
                  </DetailRow>
                )}
              </dl>
              <p className="border-t border-zinc-100 px-5 py-3 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
                {t('billing.dates.timezone', { zone: data.business_timezone === 'Asia/Jerusalem' ? (i18n.language === 'he' ? 'ישראל' : 'Israel') : data.business_timezone })}
              </p>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          {sub && (
            <Card aria-labelledby="billing-payment-heading" className="p-5">
              <h2 id="billing-payment-heading" className="text-[0.9375rem] font-semibold text-zinc-900 dark:text-zinc-50">{t('billing.payment.title')}</h2>
              <div className="mt-4 flex items-center gap-3">
                <span className={cx('grid h-10 w-10 shrink-0 place-items-center rounded-lg ring-1 ring-inset', sub.payment_method_on_file ? 'bg-brand-50 text-brand-700 ring-brand-100 dark:bg-brand-500/10 dark:text-brand-300 dark:ring-brand-500/20' : 'bg-zinc-50 text-zinc-500 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:ring-zinc-700')} aria-hidden="true">
                  <CreditCard className="h-4 w-4" />
                </span>
                <p className="text-sm font-medium text-zinc-800 dark:text-zinc-100">
                  {sub.payment_method_on_file ? t('billing.payment.onFile') : sub.checkout_pending ? t('billing.payment.pending') : t('billing.payment.none')}
                </p>
              </div>
              <p className="mt-4 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">{t('billing.payment.note')}</p>
            </Card>
          )}

          {data.usage && (
            <Card aria-labelledby="billing-usage-heading" className="p-5">
              <h2 id="billing-usage-heading" className="text-[0.9375rem] font-semibold text-zinc-900 dark:text-zinc-50">{t('billing.usage.title')}</h2>
              <div className="mt-5 space-y-6">
                <Meter
                  label={t('billing.usage.aiQuestions')}
                  meter={data.usage.ai_questions}
                  hint={data.usage.ai_questions.period_end ? t('billing.usage.resets', { date: date(data.usage.ai_questions.period_end) }) : undefined}
                />
                <Meter label={t('billing.usage.connections')} meter={data.usage.connections} />
              </div>
            </Card>
          )}
        </div>
      </div>

      {showChangePlan && <ChangePlanDialog overview={data} onClose={() => setShowChangePlan(false)} />}
      {showCancel && (
        <ConfirmDialog
          title={t('billing.cancel.title')}
          description={t('billing.cancel.description', { date: date(cancelDate) })}
          confirmLabel={t('billing.cancel.confirm')}
          isLoading={cancel.isPending}
          error={cancel.isError ? (cancel.error.message || t('billing.cancel.error')) : null}
          onConfirm={() => cancel.mutate()}
          onClose={() => setShowCancel(false)}
        />
      )}
    </div>
  )
}
