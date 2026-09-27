import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CreditCard, History, Search, ShieldAlert, SlidersHorizontal } from 'lucide-react'
import { useId, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { inputClasses } from '../../components/FormField'
import { Modal } from '../../components/Modal'
import { EmptyState, ErrorState, LoadingState } from '../../components/StatusStates'
import { Badge, Card, type BadgeTone } from '../../components/ui'
import { buttonClasses, cx } from '../../components/ui-classes'
import { formatBillingDate, planByCode } from '../../lib/billing'
import {
  applySubscriptionOverride,
  getPlanCatalog,
  listStaffSubscriptions,
  listSubscriptionEvents,
  PLAN_CATALOG_QUERY_KEY,
  type BillingPlan,
  type OverrideAction,
  type StaffSubscriptionRow,
  type SubscriptionStatus,
} from '../../services/billingService'

const TZ = 'Asia/Jerusalem'
const STATUS_TONE: Record<SubscriptionStatus, BadgeTone> = {
  trialing: 'brand', active: 'success', past_due: 'danger', canceled: 'neutral', expired: 'warning',
}
const ACTIONS: OverrideAction[] = ['extend_trial', 'change_plan', 'grant_access', 'end_now']

function EventsDialog({ row, onClose }: { row: StaffSubscriptionRow; onClose: () => void }) {
  const { t, i18n } = useTranslation()
  const events = useQuery({ queryKey: ['staff-subscription-events', row.business_id], queryFn: () => listSubscriptionEvents(row.business_id) })
  return (
    <Modal title={t('supportPortal.subscriptions.historyTitle', { business: row.business_name })} onClose={onClose}>
      {events.isPending && <LoadingState label={t('supportPortal.subscriptions.loading')} />}
      {events.isError && <ErrorState message={t('supportPortal.subscriptions.loadError')} onRetry={() => void events.refetch()} />}
      {events.data && events.data.length === 0 && <p className="text-sm text-zinc-500">{t('supportPortal.subscriptions.noEvents')}</p>}
      {events.data && events.data.length > 0 && (
        <ol className="relative space-y-5 border-s border-zinc-200 ps-5 dark:border-zinc-800">
          {[...events.data].reverse().map((event) => (
            <li key={event.sequence} className="relative">
              <span className={cx('absolute -start-[25px] top-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-white dark:ring-zinc-900', event.source === 'admin' ? 'bg-amber-500' : 'bg-brand-500')} aria-hidden="true" />
              <p className="text-sm font-medium text-zinc-900 dark:text-zinc-50">
                <span dir="ltr" className="font-mono text-[13px]">{event.event_type}</span>
                {event.to_status && <span className="text-zinc-500 dark:text-zinc-400"> · {event.from_status ?? '—'} → {event.to_status}</span>}
              </p>
              <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">
                <bdi className="figure">{new Intl.DateTimeFormat(i18n.language === 'he' ? 'he-IL' : 'en-US', { dateStyle: 'medium', timeStyle: 'short', timeZone: TZ }).format(new Date(event.created_at))}</bdi>
                {' · '}{t(`supportPortal.subscriptions.source.${event.source}`)}
              </p>
              {event.reason && <p className="mt-1.5 rounded-lg bg-zinc-50 px-3 py-2 text-sm text-zinc-700 dark:bg-zinc-800/60 dark:text-zinc-200" dir="auto">{event.reason}</p>}
            </li>
          ))}
        </ol>
      )}
    </Modal>
  )
}

function OverrideDialog({ row, plans, onClose }: { row: StaffSubscriptionRow; plans: BillingPlan[]; onClose: () => void }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const reasonId = useId()
  const [action, setAction] = useState<OverrideAction | null>(null)
  const [days, setDays] = useState('14')
  const [planCode, setPlanCode] = useState(row.plan_code ?? '')
  const [until, setUntil] = useState('')
  const [reason, setReason] = useState('')
  const mutation = useMutation({
    mutationFn: () => applySubscriptionOverride(row.business_id, {
      action: action as OverrideAction,
      reason: reason.trim(),
      ...(action === 'extend_trial' ? { days: Number(days) } : {}),
      ...(action === 'change_plan' ? { plan_code: planCode } : {}),
      ...(action === 'grant_access' ? { until: `${until}T20:59:59Z` } : {}),
    }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['staff-subscriptions'] })
      await queryClient.invalidateQueries({ queryKey: ['staff-subscription-events', row.business_id] })
      onClose()
    },
  })
  const daysValid = Number.isInteger(Number(days)) && Number(days) >= 1 && Number(days) <= 90
  const valid = action !== null && reason.trim().length >= 5
    && (action !== 'extend_trial' || daysValid)
    && (action !== 'change_plan' || Boolean(planCode))
    && (action !== 'grant_access' || Boolean(until))

  return (
    <Modal title={t('supportPortal.subscriptions.overrideTitle', { business: row.business_name })} onClose={mutation.isPending ? () => {} : onClose}>
      <form className="space-y-5" onSubmit={(event) => { event.preventDefault(); if (valid) mutation.mutate() }}>
        <p className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2.5 text-sm text-amber-950 dark:bg-amber-500/10 dark:text-amber-100">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          {t('supportPortal.subscriptions.auditNotice')}
        </p>
        <fieldset>
          <legend className="text-sm font-medium text-zinc-800 dark:text-zinc-100">{t('supportPortal.subscriptions.actionLabel')}</legend>
          <div className="mt-2 grid gap-2">
            {ACTIONS.map((item) => (
              <label key={item} className={cx('flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2.5 text-sm transition-colors', action === item ? 'border-brand-500 bg-brand-50/60 dark:border-brand-400 dark:bg-brand-500/10' : 'border-zinc-200 hover:border-zinc-300 dark:border-zinc-700 dark:hover:border-zinc-600')}>
                <input type="radio" name="override-action" value={item} checked={action === item} onChange={() => setAction(item)} className="mt-1 accent-brand-600" />
                <span>
                  <span className="block font-medium text-zinc-900 dark:text-zinc-50">{t(`supportPortal.subscriptions.actions.${item}`)}</span>
                  <span className="block text-xs text-zinc-500 dark:text-zinc-400">{t(`supportPortal.subscriptions.actionHints.${item}`)}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>
        {action === 'extend_trial' && (
          <label className="block text-sm font-medium text-zinc-800 dark:text-zinc-100">
            {t('supportPortal.subscriptions.days')}
            <input type="number" min={1} max={90} value={days} onChange={(event) => setDays(event.target.value)} className={cx(inputClasses, 'mt-1.5 w-32')} />
          </label>
        )}
        {action === 'change_plan' && (
          <label className="block text-sm font-medium text-zinc-800 dark:text-zinc-100">
            {t('supportPortal.subscriptions.plan')}
            <select value={planCode} onChange={(event) => setPlanCode(event.target.value)} className={cx(inputClasses, 'mt-1.5')}>
              {plans.map((plan) => <option key={plan.code} value={plan.code}>{plan.name}</option>)}
            </select>
          </label>
        )}
        {action === 'grant_access' && (
          <label className="block text-sm font-medium text-zinc-800 dark:text-zinc-100">
            {t('supportPortal.subscriptions.until')}
            <input type="date" value={until} onChange={(event) => setUntil(event.target.value)} className={cx(inputClasses, 'mt-1.5')} />
          </label>
        )}
        <div>
          <label htmlFor={reasonId} className="block text-sm font-medium text-zinc-800 dark:text-zinc-100">{t('supportPortal.subscriptions.reason')}</label>
          <textarea id={reasonId} required minLength={5} maxLength={500} rows={3} value={reason} onChange={(event) => setReason(event.target.value)} className={cx(inputClasses, 'mt-1.5 h-auto py-2')} placeholder={t('supportPortal.subscriptions.reasonPlaceholder')} />
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{t('supportPortal.subscriptions.reasonHint')}</p>
        </div>
        {mutation.isError && <p role="alert" className="text-sm text-danger-700 dark:text-danger-500">{mutation.error.message}</p>}
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" className={buttonClasses('ghost')} onClick={onClose} disabled={mutation.isPending}>{t('common.cancel')}</button>
          <button type="submit" className={buttonClasses(action === 'end_now' ? 'danger' : 'primary')} disabled={!valid || mutation.isPending}>
            {mutation.isPending ? t('supportPortal.subscriptions.applying') : t('supportPortal.subscriptions.apply')}
          </button>
        </div>
      </form>
    </Modal>
  )
}

export function SubscriptionsPanel({ canOverride }: { canOverride: boolean }) {
  const { t, i18n } = useTranslation()
  const [search, setSearch] = useState('')
  const [history, setHistory] = useState<StaffSubscriptionRow | null>(null)
  const [override, setOverride] = useState<StaffSubscriptionRow | null>(null)
  const rows = useQuery({ queryKey: ['staff-subscriptions'], queryFn: listStaffSubscriptions })
  const catalog = useQuery({ queryKey: PLAN_CATALOG_QUERY_KEY, queryFn: getPlanCatalog, staleTime: 5 * 60_000 })
  const plans = catalog.data?.plans ?? []
  const query = search.trim().toLocaleLowerCase()
  const shown = rows.data?.filter((row) => row.business_name.toLocaleLowerCase().includes(query)) ?? []
  const date = (iso: string | null) => (iso ? formatBillingDate(iso, TZ, i18n.language) : '—')

  return (
    <section aria-labelledby="subscriptions-heading" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 id="subscriptions-heading" className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t('supportPortal.subscriptions.title')}</h2>
          <p className="mt-0.5 max-w-2xl text-sm text-zinc-500 dark:text-zinc-400">
            {canOverride ? t('supportPortal.subscriptions.descriptionSuperadmin') : t('supportPortal.subscriptions.description')}
          </p>
        </div>
        <div className="relative w-full sm:w-80">
          <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" aria-hidden="true" />
          <label htmlFor="support-subscription-search" className="sr-only">{t('supportPortal.subscriptions.searchLabel')}</label>
          <input id="support-subscription-search" type="search" className={cx(inputClasses, 'ps-9')} placeholder={t('supportPortal.subscriptions.searchPlaceholder')} value={search} onChange={(event) => setSearch(event.target.value)} />
        </div>
      </div>

      {rows.isPending && <LoadingState label={t('supportPortal.subscriptions.loading')} />}
      {rows.isError && <ErrorState message={t('supportPortal.subscriptions.loadError')} onRetry={() => void rows.refetch()} />}
      {rows.data && shown.length === 0 && <EmptyState title={t('supportPortal.subscriptions.empty')} icon={<CreditCard className="h-5 w-5" />} />}

      {shown.length > 0 && (
        <Card as="div" className="overflow-hidden">
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
            {shown.map((row) => {
              const status = row.effective_status
              const plan = planByCode(plans, row.plan_code)
              const until = status === 'trialing' || status === 'expired' ? row.trial_ends_at : row.current_period_end
              return (
                <li key={row.business_id} className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:gap-5 sm:px-5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-zinc-900 dark:text-zinc-50" title={row.business_name}>{row.business_name}</p>
                    <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-zinc-500 dark:text-zinc-400">
                      <span dir="ltr">{plan?.name ?? row.plan_code ?? t('supportPortal.subscriptions.noPlan')}</span>
                      {until && <span>{t(status === 'trialing' || status === 'expired' ? 'supportPortal.subscriptions.trialEnds' : 'supportPortal.subscriptions.periodEnds', { date: date(until) })}</span>}
                      {row.plan_code && <span>{row.payment_method_on_file ? t('supportPortal.subscriptions.paymentOnFile') : t('supportPortal.subscriptions.noPayment')}</span>}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {status ? <Badge tone={STATUS_TONE[status]}>{t(`supportPortal.subscriptions.status.${status}`)}</Badge> : <Badge tone="neutral">{t('supportPortal.subscriptions.noPlan')}</Badge>}
                    {row.cancel_at_period_end && <Badge tone="warning" dot={false}>{t('supportPortal.subscriptions.cancelScheduled')}</Badge>}
                    {row.plan_code && (
                      <button type="button" className={buttonClasses('ghost', 'sm')} onClick={() => setHistory(row)}>
                        <History className="h-3.5 w-3.5" aria-hidden="true" />{t('supportPortal.subscriptions.history')}
                      </button>
                    )}
                    {canOverride && row.plan_code && (
                      <button type="button" className={buttonClasses('secondary', 'sm')} onClick={() => setOverride(row)}>
                        <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden="true" />{t('supportPortal.subscriptions.override')}
                      </button>
                    )}
                  </div>
                </li>
              )
            })}
          </ul>
        </Card>
      )}

      {history && <EventsDialog row={history} onClose={() => setHistory(null)} />}
      {override && <OverrideDialog row={override} plans={plans} onClose={() => setOverride(null)} />}
    </section>
  )
}
