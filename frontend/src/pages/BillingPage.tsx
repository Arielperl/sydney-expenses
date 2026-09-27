import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, CircleAlert, Clock, CreditCard, Info, LifeBuoy, Loader2, Lock, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { PriceFigure, IntervalToggle } from '../components/billing/PlanCards'
import { PlanChooser } from '../components/billing/PlanChooser'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ErrorState } from '../components/StatusStates'
import { Badge, PageHeader, Skeleton } from '../components/ui'
import { buttonClasses, cardClasses, cx } from '../components/ui-classes'
import { useBillingOverview } from '../hooks/useBillingOverview'
import {
  billingState,
  catalogSavingsMonths,
  formatBillingDate,
  formatCount,
  newIdempotencyKey,
  nextPlanWithMoreConnections,
  planByCode,
  planChangeImpact,
  priceFor,
  STATE_TONE,
  type BillingState,
} from '../lib/billing'
import {
  BILLING_QUERY_KEY,
  cancelRenewal,
  changePlan,
  createCheckout,
  resumeRenewal,
  type BillingInterval,
  type BillingOverview,
  type BillingPlan,
  type UsageMeter,
} from '../services/billingService'

const CONFIRMATION_WAIT_MS = 60_000

type Tone = 'neutral' | 'info' | 'warning' | 'danger' | 'success'
const TONE_SURFACE: Record<Tone, string> = {
  neutral: 'border-zinc-200 bg-zinc-50 text-zinc-800 dark:border-zinc-800 dark:bg-zinc-800/40 dark:text-zinc-100',
  info: 'border-sky-200 bg-sky-50/70 text-sky-950 dark:border-sky-500/25 dark:bg-sky-500/[0.07] dark:text-sky-100',
  warning: 'border-amber-200 bg-amber-50/80 text-amber-950 dark:border-amber-500/25 dark:bg-amber-500/[0.08] dark:text-amber-100',
  danger: 'border-danger-600/20 bg-danger-50 text-danger-700 dark:border-danger-500/25 dark:bg-danger-500/10 dark:text-red-200',
  success: 'border-success-500/25 bg-success-50 text-success-700 dark:border-success-500/25 dark:bg-success-500/10 dark:text-emerald-200',
}
const TONE_ICON = { neutral: Info, info: Clock, warning: Clock, danger: CircleAlert, success: CheckCircle2 } as const

/** States that need a line of explanation above everything else; the tone always matches the status chip. */
const BANDED: BillingState[] = ['trial_ending', 'payment_processing', 'renewal_processing', 'past_due', 'trial_expired', 'trial_unavailable', 'canceled', 'canceling']
const BAND_TONE: Record<string, Tone> = { warning: 'warning', danger: 'danger', info: 'info', neutral: 'neutral', success: 'success', brand: 'neutral' }

type Notice = { tone: 'pending' | 'success' | 'neutral' | 'danger'; title: string; text?: string }

function NoticeBar({ notice, onDismiss }: { notice: Notice; onDismiss?: () => void }) {
  const { t } = useTranslation()
  const tone: Tone = notice.tone === 'pending' ? 'info' : notice.tone
  const Icon = notice.tone === 'pending' ? Loader2 : TONE_ICON[tone]
  return (
    <div role={notice.tone === 'danger' ? 'alert' : 'status'} className={cx('flex items-start gap-3 rounded-xl border px-4 py-3.5 text-sm sm:px-5', TONE_SURFACE[tone])}>
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

function Fact({ label, children, className }: { label: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div className={cx('min-w-0 bg-zinc-50 px-6 py-4 sm:px-8 dark:bg-zinc-900', className)}>
      <dt className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{label}</dt>
      <dd className="mt-1.5 text-sm text-zinc-900 dark:text-zinc-100">{children}</dd>
    </div>
  )
}

function Bar({ ratio, tone, label, valueText, max, now }: { ratio: number; tone: 'brand' | 'warning'; label: string; valueText: string; max: number; now: number }) {
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={now}
      aria-valuetext={valueText}
      className="h-1.5 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800"
    >
      <div
        className={cx('h-full rounded-full transition-[width] duration-500 ease-out', tone === 'warning' ? 'bg-amber-500' : 'bg-brand-500')}
        style={{ width: `${Math.max(Math.min(ratio, 1) * 100, now > 0 ? 2 : 0)}%` }}
      />
    </div>
  )
}

function UsageItem({ label, meter, helper, warn, className }: { label: string; meter: UsageMeter; helper: string; warn: boolean; className?: string }) {
  const { t, i18n } = useTranslation()
  const valueText = t('billing.page.usage.of', { used: formatCount(meter.used, i18n.language), limit: formatCount(meter.limit, i18n.language) })
  return (
    <div className={cx('min-w-0 px-5 py-5 sm:px-6', className)}>
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="text-sm text-zinc-600 dark:text-zinc-300">{label}</h3>
        <p className="figure shrink-0 text-base font-medium text-zinc-900 dark:text-zinc-50">{valueText}</p>
      </div>
      {meter.limit > 0 && (
        <div className="mt-3">
          <Bar ratio={meter.used / meter.limit} tone={warn ? 'warning' : 'brand'} label={label} valueText={valueText} max={meter.limit} now={meter.used} />
        </div>
      )}
      <p className={cx('mt-2.5 text-xs leading-relaxed', warn ? 'text-amber-800 dark:text-amber-300' : 'text-zinc-500 dark:text-zinc-400')}>{helper}</p>
    </div>
  )
}

function BillingSkeleton() {
  return (
    <div className="space-y-8" aria-hidden="true">
      <div className={cx(cardClasses, 'grid overflow-hidden lg:grid-cols-[minmax(0,1fr)_19rem]')}>
        <div className="space-y-4 p-6 sm:p-8">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-7 w-40" />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="mt-6 h-10 w-48" />
        </div>
        <div className="space-y-4 border-t border-zinc-100 bg-zinc-50/70 p-6 lg:border-t-0 lg:border-s dark:border-zinc-800 dark:bg-zinc-950/30">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-2/3" />
        </div>
      </div>
      <Skeleton className="h-32 rounded-xl" />
      <Skeleton className="h-72 rounded-xl" />
    </div>
  )
}

type NextStep = { text: string; primary?: 'addPayment' | 'updatePayment' | 'pay' | 'resume'; support?: boolean }

function nextStepFor(state: BillingState, data: BillingOverview, date: (iso: string | null | undefined) => string, t: (key: string, options?: Record<string, unknown>) => string): NextStep {
  const sub = data.subscription
  const online = data.billing_available
  if (!sub) return { text: t('billing.page.noPlan') }
  switch (state) {
    case 'trialing':
      if (sub.payment_method_on_file) return { text: t('billing.page.next.trialingWithPayment', { date: date(sub.trial_ends_at) }) }
      return online ? { text: t('billing.page.next.trialing'), primary: 'addPayment' } : { text: t('billing.page.next.trialingUnavailable') }
    case 'trial_ending':
      return online ? { text: t('billing.page.next.trial_ending'), primary: 'addPayment' } : { text: t('billing.page.next.trial_endingUnavailable') }
    case 'payment_processing':
    case 'renewal_processing':
      return { text: t(`billing.page.next.${state}`) }
    case 'active':
      return { text: t('billing.page.next.active', { date: date(sub.current_period_end) }) }
    case 'canceling':
      return { text: t('billing.page.next.canceling'), primary: 'resume' }
    case 'past_due':
      return online ? { text: t('billing.page.next.past_due'), primary: 'updatePayment' } : { text: t('billing.page.next.past_dueUnavailable'), support: true }
    case 'trial_expired':
    case 'trial_unavailable':
    case 'canceled':
      return online ? { text: t('billing.page.next.locked'), primary: 'pay' } : { text: t('billing.page.next.lockedUnavailable'), support: true }
    default:
      return { text: t('billing.page.noPlan') }
  }
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
  const [chosenInterval, setChosenInterval] = useState<BillingInterval | null>(null)
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<BillingPlan | null>(null)
  const [showCancel, setShowCancel] = useState(false)
  const idempotencyKey = useRef<string>(newIdempotencyKey())
  const refresh = () => queryClient.invalidateQueries({ queryKey: BILLING_QUERY_KEY })

  useEffect(() => {
    if (checkoutReturn !== 'success') return
    const timer = window.setTimeout(() => setWaitedLong(true), Math.max(0, CONFIRMATION_WAIT_MS - (Date.now() - returnedAt)))
    return () => window.clearTimeout(timer)
  }, [checkoutReturn, returnedAt])

  const checkout = useMutation({
    mutationFn: ({ plan, interval }: { plan: string; interval: BillingInterval }) => createCheckout(plan, interval, idempotencyKey.current),
    onSuccess: ({ checkout_url }) => window.location.assign(checkout_url),
    onError: () => { idempotencyKey.current = newIdempotencyKey() },
  })
  const cancel = useMutation({ mutationFn: cancelRenewal, onSuccess: async () => { await refresh(); setShowCancel(false) } })
  const resume = useMutation({ mutationFn: resumeRenewal, onSuccess: refresh })
  const change = useMutation({
    mutationFn: ({ plan, interval }: { plan: string; interval: BillingInterval }) => changePlan(plan, interval),
    onSuccess: async () => {
      await refresh()
      setConfirming(null)
      setSelectedPlan(null)
    },
  })

  const header = <PageHeader title={t('billing.title')} description={t('billing.page.description')} />
  if (overview.isPending) {
    return (
      <div className="space-y-8" role="status" aria-label={t('billing.loading')}>
        {header}
        <BillingSkeleton />
      </div>
    )
  }
  if (overview.isError) {
    return (
      <div className="space-y-8">
        {header}
        <ErrorState message={t('billing.loadError')} onRetry={() => void overview.refetch()} />
      </div>
    )
  }

  const data = overview.data
  const sub = data.subscription
  const state = billingState(data)
  const plan = planByCode(data.plans, sub?.plan_code)
  const pendingPlan = planByCode(data.plans, sub?.pending_plan_code)
  const date = (iso: string | null | undefined) => (iso ? formatBillingDate(iso, data.business_timezone, i18n.language) : '')
  const interval: BillingInterval = chosenInterval ?? sub?.billing_interval ?? 'month'
  const price = plan && sub ? priceFor(plan, sub.billing_interval) : null
  const confirmed = Boolean(sub && (sub.payment_method_on_file || state === 'active'))
  const next = nextStepFor(state, data, date, t)
  const band: Tone | undefined = BANDED.includes(state) ? BAND_TONE[STATE_TONE[state]] : undefined
  const zone = data.business_timezone === 'Asia/Jerusalem' ? (i18n.language === 'he' ? 'ישראל' : 'Israel') : data.business_timezone

  let notice: Notice | null = null
  if (checkoutReturn === 'canceled') notice = { tone: 'neutral', title: t('billing.checkout.canceledTitle'), text: t('billing.checkout.canceledText') }
  else if (checkoutReturn === 'success' && confirmed) notice = { tone: 'success', title: t('billing.checkout.successTitle'), text: t('billing.checkout.successText') }
  else if (checkoutReturn === 'success' && waitedLong) notice = { tone: 'neutral', title: t('billing.checkout.slowTitle'), text: t('billing.checkout.slowText') }
  else if (checkoutReturn === 'success') notice = { tone: 'pending', title: t('billing.checkout.pendingTitle'), text: t('billing.checkout.pendingText') }
  if (checkout.isError) notice = { tone: 'danger', title: t('billing.checkout.failedTitle'), text: checkout.error.message }

  const renewing = sub && ['trialing', 'active', 'past_due'].includes(sub.status)
  const canCancel = Boolean(data.can_manage && renewing && !sub?.cancel_at_period_end && (sub?.payment_method_on_file || sub?.status !== 'trialing'))
  const cancelDate = sub?.status === 'trialing' ? sub?.trial_ends_at : sub?.current_period_end
  const trialing = state === 'trialing' || state === 'trial_ending'
  const trialLeft = sub?.trial_days_remaining ?? null

  // One date that matters now, never a list of every timestamp.
  const dateFact: { label: string; iso: string; trial?: boolean } | null = sub
    ? sub.trial_ends_at && (trialing || state === 'payment_processing' || state === 'trial_expired')
      ? { label: 'billing.page.facts.trialEnds', iso: sub.trial_ends_at, trial: true }
      : sub.ended_at
        ? { label: 'billing.page.facts.ended', iso: sub.ended_at }
        : sub.current_period_end
          ? { label: sub.cancel_at_period_end ? 'billing.page.facts.endsOn' : sub.status === 'active' ? 'billing.page.facts.renews' : 'billing.page.facts.periodEnd', iso: sub.current_period_end }
          : null
    : null
  const facts = (price !== null ? 1 : 0) + (dateFact ? 1 : 0) + (pendingPlan && sub?.current_period_end ? 1 : 0) + 1

  const usage = data.usage
  const upgradeForConnections = nextPlanWithMoreConnections(data.plans, sub?.plan_code)
  const ai = usage?.ai_questions
  const aiFull = Boolean(ai && ai.limit > 0 && ai.used >= ai.limit)
  const aiNear = Boolean(ai && ai.limit > 0 && !aiFull && ai.used / ai.limit >= 0.8)
  const connections = usage?.connections

  const confirmImpact = confirming ? planChangeImpact(data, confirming, interval) : null
  const confirmSameplan = confirming && confirming.code === sub?.plan_code

  return (
    <div className="space-y-10">
      {header}
      {notice && <NoticeBar notice={notice} onDismiss={notice.tone === 'pending' ? undefined : checkout.isError ? () => checkout.reset() : () => setSearchParams({}, { replace: true })} />}

      {/* ------------------------------------------------ current subscription */}
      <section aria-labelledby="billing-current-heading" className={cx(cardClasses, 'overflow-hidden')}>
        {band && (
          <p className={cx('flex items-start gap-2.5 border-b px-6 py-3 text-sm font-medium sm:px-8', TONE_SURFACE[band], 'rounded-none border-x-0 border-t-0')}>
            {(() => { const Icon = TONE_ICON[band]; return <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" /> })()}
            <span>
              {t(`billing.page.band.${state}`, {
                date: date(state === 'canceling' ? sub?.current_period_end : sub?.trial_ends_at),
              })}
            </span>
          </p>
        )}
        <div className="min-w-0 p-6 sm:p-8">
          <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{t('billing.page.yourPlan')}</p>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
            <h2 id="billing-current-heading" className="text-[1.625rem] leading-tight font-semibold tracking-[-0.015em] text-zinc-900 dark:text-zinc-50">
              <bdi>{plan?.name ?? t('billing.state.plan_required')}</bdi>
            </h2>
            {sub && <Badge tone={STATE_TONE[state]}>{t(`billing.state.${state}`)}</Badge>}
          </div>
          {plan && <p className="mt-1.5 text-sm text-zinc-500 dark:text-zinc-400" dir="auto">{plan.tagline}</p>}

          <p className="mt-5 max-w-2xl text-[0.9375rem] leading-relaxed text-zinc-700 dark:text-zinc-200">{next.text}</p>

          {data.can_manage ? (
            <div className="mt-6 flex flex-col gap-2.5 sm:flex-row sm:flex-wrap sm:items-center">
              {next.primary === 'resume' && (
                <button type="button" className={buttonClasses('primary', 'md')} disabled={resume.isPending} onClick={() => resume.mutate()}>
                  {t('billing.actions.resumeRenewal')}
                </button>
              )}
              {next.primary && next.primary !== 'resume' && sub && (
                <button
                  type="button"
                  className={buttonClasses('primary', 'md')}
                  disabled={checkout.isPending}
                  onClick={() => checkout.mutate({ plan: sub.plan_code, interval: sub.billing_interval })}
                >
                  <CreditCard className="h-4 w-4" aria-hidden="true" />
                  {checkout.isPending ? t('billing.actions.redirecting') : t(`billing.actions.${next.primary}`)}
                </button>
              )}
              {next.support && (
                <Link to="/support/request" className={buttonClasses('secondary', 'md')}>
                  <LifeBuoy className="h-4 w-4" aria-hidden="true" />
                  {t('billing.page.contactSupport')}
                </Link>
              )}
              {sub && (
                <a href="#billing-plans" className={buttonClasses(next.primary || next.support ? 'ghost' : 'secondary', 'md')}>
                  {t('billing.page.comparePlans')}
                </a>
              )}
              {canCancel && (
                <button type="button" className={buttonClasses('ghost', 'md', 'text-zinc-600 sm:ms-auto dark:text-zinc-400')} onClick={() => setShowCancel(true)}>
                  {t('billing.actions.cancelRenewal')}
                </button>
              )}
            </div>
          ) : (
            <p className="mt-6 flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
              <Lock className="h-4 w-4 shrink-0" aria-hidden="true" />
              {t('billing.page.next.memberOnly')}
            </p>
          )}
          {resume.isError && <p role="alert" className="mt-3 text-sm text-danger-700 dark:text-danger-500">{t('billing.resumeError')}</p>}
        </div>

        {sub && (
          <dl aria-label={t('billing.page.facts.label')} className={cx('grid gap-px border-t border-zinc-200/80 bg-zinc-200/80 dark:border-zinc-800 dark:bg-zinc-800', facts === 4 ? 'grid-cols-2 lg:grid-cols-4' : 'grid-cols-2 sm:grid-cols-3')}>
            {price !== null && (
              <Fact label={t('billing.page.facts.price')}>
                <span className="flex flex-wrap items-baseline gap-x-1.5">
                  <PriceFigure minor={price} language={i18n.language} className="text-lg text-zinc-900 dark:text-zinc-50" currencyClassName="text-sm text-zinc-500 dark:text-zinc-400" />
                  <span className="text-xs text-zinc-500 dark:text-zinc-400">{t(sub.billing_interval === 'month' ? 'billing.perMonth' : 'billing.perYear')}</span>
                </span>
                <span className="mt-1 block text-xs text-zinc-500 dark:text-zinc-400">
                  {t(`billing.interval.${sub.billing_interval}`)} · {t('billing.excludingVat')}
                </span>
              </Fact>
            )}
            {dateFact && (
              <Fact label={t(dateFact.label)}>
                <span className="figure text-[0.9375rem] font-medium">{date(dateFact.iso)}</span>
                {trialing && trialLeft !== null && dateFact.trial && (
                  <span className="mt-2 block max-w-[12rem]">
                    <Bar
                      ratio={(data.trial_days - trialLeft) / data.trial_days}
                      tone={state === 'trial_ending' ? 'warning' : 'brand'}
                      label={t('billing.trialProgress')}
                      valueText={t('billing.daysLeft', { count: trialLeft })}
                      max={data.trial_days}
                      now={data.trial_days - trialLeft}
                    />
                    <span className={cx('figure mt-1.5 block text-xs', state === 'trial_ending' ? 'text-amber-800 dark:text-amber-300' : 'text-zinc-500 dark:text-zinc-400')}>
                      {t('billing.daysLeft', { count: trialLeft })}
                    </span>
                  </span>
                )}
              </Fact>
            )}
            {pendingPlan && sub.current_period_end && (
              <Fact label={t('billing.page.facts.scheduled')}>
                {t('billing.page.facts.scheduledValue', { plan: pendingPlan.name, date: date(sub.current_period_end) })}
              </Fact>
            )}
            <Fact label={t('billing.page.facts.payment')} className={facts % 2 === 1 ? 'col-span-2 sm:col-span-1' : undefined}>
              <span className="inline-flex items-center gap-1.5">
                {sub.payment_method_on_file && <CheckCircle2 className="h-3.5 w-3.5 text-brand-600 dark:text-brand-400" aria-hidden="true" />}
                {sub.payment_method_on_file
                  ? t('billing.page.payment.onFile')
                  : sub.checkout_pending
                    ? t('billing.page.payment.pending')
                    : data.billing_available
                      ? t('billing.page.payment.none')
                      : t('billing.page.payment.unavailable')}
              </span>
            </Fact>
          </dl>
        )}
      </section>

      {/* ------------------------------------------------ usage */}
      {usage && connections && ai && (
        <section aria-labelledby="billing-usage-heading">
          <h2 id="billing-usage-heading" className="text-[0.9375rem] font-semibold text-zinc-900 dark:text-zinc-50">{t('billing.page.usage.title')}</h2>
          <div className={cx(cardClasses, 'mt-3 grid sm:grid-cols-2')}>
            <UsageItem
              label={t('billing.page.usage.connections')}
              meter={connections}
              warn={false}
              helper={connections.used < connections.limit
                ? t('billing.page.usage.connectionsRoom', { count: connections.limit - connections.used })
                : upgradeForConnections
                  ? t('billing.page.usage.connectionsFullUpgrade', { plan: upgradeForConnections.name })
                  : t('billing.page.usage.connectionsFull')}
            />
            <UsageItem
              className="border-t border-zinc-100 sm:border-t-0 sm:border-s dark:border-zinc-800"
              label={t('billing.page.usage.ai')}
              meter={ai}
              warn={aiFull || aiNear}
              helper={aiFull
                ? t('billing.page.usage.aiFull', { date: date(ai.period_end) })
                : aiNear
                  ? t('billing.page.usage.aiNearLimit', { count: ai.limit - ai.used, date: date(ai.period_end) })
                  : t('billing.page.usage.aiResets', { date: date(ai.period_end) })}
            />
          </div>
        </section>
      )}

      {/* ------------------------------------------------ plans */}
      {sub && (
        <section aria-labelledby="billing-plans-heading" id="billing-plans" className="scroll-mt-24">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div className="min-w-0">
              <h2 id="billing-plans-heading" className="text-[0.9375rem] font-semibold text-zinc-900 dark:text-zinc-50">{t('billing.page.plans.title')}</h2>
              <p className="mt-1 max-w-2xl text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">{t('billing.page.plans.description')}</p>
            </div>
            <IntervalToggle surface="app" value={interval} onChange={(value) => { setChosenInterval(value); setSelectedPlan(null) }} savingsMonths={catalogSavingsMonths(data.plans)} />
          </div>
          <div className="mt-4">
            <PlanChooser
              overview={data}
              interval={interval}
              selected={selectedPlan}
              onSelect={setSelectedPlan}
              onConfirm={(target) => { change.reset(); setConfirming(target) }}
              busy={change.isPending}
            />
          </div>
          <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
            {t('billing.page.plans.vatNote')}
            {!data.can_manage && <> {t('billing.page.plans.readOnly')}</>}
          </p>
        </section>
      )}

      <p className="border-t border-zinc-200/80 pt-5 text-xs leading-relaxed text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
        {t('billing.page.footnote', { zone })}
      </p>

      {confirming && (
        <ConfirmDialog
          tone="primary"
          title={confirmSameplan
            ? t('billing.page.confirmPlan.titleInterval', { interval: t(`billing.interval.${interval}`) })
            : t('billing.page.confirmPlan.title', { plan: confirming.name })}
          description={
            confirmImpact === 'trial' ? t('billing.page.plans.impactTrial')
              : confirmImpact === 'upgrade' ? t('billing.page.plans.impactUpgrade')
                : confirmImpact === 'downgrade' ? t('billing.page.plans.impactDowngrade', { date: date(sub?.current_period_end) })
                  : t('billing.page.plans.impactImmediate')
          }
          confirmLabel={t('billing.page.confirmPlan.confirm')}
          loadingLabel={t('billing.page.confirmPlan.saving')}
          isLoading={change.isPending}
          error={change.isError ? (change.error.message || t('billing.changePlan.error')) : null}
          onConfirm={() => change.mutate({ plan: confirming.code, interval })}
          onClose={() => setConfirming(null)}
        />
      )}
      {showCancel && (
        <ConfirmDialog
          title={t('billing.cancel.title')}
          description={t('billing.cancel.description', { date: date(cancelDate) })}
          confirmLabel={t('billing.cancel.confirm')}
          loadingLabel={t('billing.page.cancelSaving')}
          isLoading={cancel.isPending}
          error={cancel.isError ? (cancel.error.message || t('billing.cancel.error')) : null}
          onConfirm={() => cancel.mutate()}
          onClose={() => setShowCancel(false)}
        />
      )}
    </div>
  )
}
