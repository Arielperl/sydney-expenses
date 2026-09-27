import { Check, PlugZap } from 'lucide-react'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'

import { formatCount, formatPlanPrice, planChangeImpact, priceFor } from '../../lib/billing'
import type { BillingInterval, BillingOverview, BillingPlan } from '../../services/billingService'
import { Badge } from '../ui'
import { buttonClasses, cx } from '../ui-classes'
import { PriceFigure } from './PlanCards'

/**
 * Plans as a quiet comparison list inside the billing page: one row per plan,
 * the number of sales sources as the deciding column, price at the end.
 * Choosing a row opens its consequence and a single action right beneath it,
 * so nothing floats over the content and every action stays in reach.
 */
export function PlanChooser({
  overview,
  interval,
  selected,
  onSelect,
  onConfirm,
  busy,
}: {
  overview: BillingOverview
  interval: BillingInterval
  selected: string | null
  onSelect: (code: string | null) => void
  onConfirm: (plan: BillingPlan) => void
  busy: boolean
}) {
  const { t, i18n } = useTranslation()
  const groupName = useId()
  const sub = overview.subscription
  const manage = overview.can_manage && Boolean(sub)
  const intervalName = t(`billing.interval.${interval}`)
  const periodEnd = sub?.current_period_end
    ? new Intl.DateTimeFormat(i18n.language === 'he' ? 'he-IL' : 'en-US', { day: 'numeric', month: 'long', year: 'numeric', timeZone: overview.business_timezone }).format(new Date(sub.current_period_end))
    : ''

  const rows = overview.plans.map((plan) => {
    const current = sub?.plan_code === plan.code
    const unchanged = current && sub?.billing_interval === interval && !sub?.pending_plan_code
    const isSelected = selected === plan.code && !unchanged
    const price = priceFor(plan, interval)
    const monthly = plan.prices.month
    const inputId = `${groupName}-${plan.code}`
    const detailsId = `${inputId}-action`
    const impact = isSelected ? planChangeImpact(overview, plan, interval) : null

    const content = (
      <>
        {manage && (
          <span
            aria-hidden="true"
            className={cx(
              'mt-1 grid h-[18px] w-[18px] shrink-0 place-items-center rounded-full border transition-colors',
              isSelected ? 'border-brand-600 bg-brand-600 dark:border-brand-400 dark:bg-brand-400' : 'border-zinc-300 bg-white dark:border-zinc-600 dark:bg-zinc-900',
              unchanged && 'opacity-40',
            )}
          >
            {isSelected && <span className="h-1.5 w-1.5 rounded-full bg-white dark:bg-zinc-950" />}
          </span>
        )}
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
            <span id={`${inputId}-name`} className="text-base font-semibold text-zinc-900 dark:text-zinc-50"><bdi>{plan.name}</bdi></span>
            {plan.recommended && <Badge tone="brand" dot={false}>{t('billing.recommended')}</Badge>}
            {current && (
              <Badge tone="neutral">
                {sub && sub.billing_interval !== interval
                  ? t('billing.page.plans.currentInterval', { interval: t(`billing.interval.${sub.billing_interval}`) })
                  : t('billing.page.plans.current')}
              </Badge>
            )}
          </div>
          <p className="mt-1 text-sm leading-relaxed text-zinc-600 dark:text-zinc-400" dir="auto">{plan.tagline}</p>
        </div>
        <div className={cx('flex items-start gap-2 text-sm', manage && 'col-start-2 md:col-start-auto')}>
          <PlugZap className="mt-0.5 h-4 w-4 shrink-0 text-brand-600 dark:text-brand-400" aria-hidden="true" />
          <p className="figure font-medium text-zinc-900 dark:text-zinc-100">{t('billing.page.plans.sources', { count: plan.max_connections })}</p>
        </div>
        <div className={cx('md:text-end', manage && 'col-start-2 md:col-start-auto')}>
          {price !== null && (
            <p className="flex items-baseline gap-1.5 md:justify-end">
              <PriceFigure minor={price} language={i18n.language} className="text-[1.375rem] text-zinc-900 dark:text-zinc-50" currencyClassName="text-sm text-zinc-500 dark:text-zinc-400" />
              <span className="text-xs text-zinc-500 dark:text-zinc-400">{t(interval === 'month' ? 'billing.perMonth' : 'billing.perYear')}</span>
            </p>
          )}
          {interval === 'year' && monthly && (
            <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{t('billing.insteadOf', { amount: formatPlanPrice(monthly * 12, i18n.language) })}</p>
          )}
        </div>
        <ul className={cx('flex flex-wrap gap-x-5 gap-y-1.5 text-[0.8125rem] leading-relaxed text-zinc-600 md:col-span-3 dark:text-zinc-400', manage && 'col-start-2')}>
          {plan.features.map((feature) => (
            <li key={feature} className="flex items-start gap-1.5" dir="auto">
              <Check className="mt-[3px] h-3.5 w-3.5 shrink-0 text-brand-600 dark:text-brand-400" aria-hidden="true" />
              <span>{feature}</span>
            </li>
          ))}
          {/* The assistant allowance is a detail of the plan, not a headline. */}
          <li className="text-zinc-500 dark:text-zinc-400">{t('billing.limits.aiQuestions', { amount: formatCount(plan.ai_questions_per_month, i18n.language) })}</li>
        </ul>
      </>
    )

    const rowGrid = cx(
      'relative grid gap-x-4 gap-y-3 px-5 py-5 sm:px-6',
      manage ? 'grid-cols-[18px_minmax(0,1fr)] md:grid-cols-[18px_minmax(0,1fr)_13rem_10rem]' : 'grid-cols-1 md:grid-cols-[minmax(0,1fr)_13rem_10rem]',
      'md:items-start',
    )

    return (
      <div key={plan.code} role={manage ? undefined : 'listitem'} className={cx('relative', isSelected && 'bg-brand-50/50 dark:bg-brand-500/[0.06]')}>
        {/* Start-edge mark for the chosen row, echoing the navigation's current-page mark. */}
        <span aria-hidden="true" className={cx('absolute inset-y-0 start-0 w-[3px] bg-brand-600 transition-opacity dark:bg-brand-400', isSelected ? 'opacity-100' : 'opacity-0')} />
        {manage ? (
          <label
            htmlFor={inputId}
            className={cx(
              rowGrid,
              unchanged ? 'cursor-default' : 'cursor-pointer hover:bg-zinc-50/80 dark:hover:bg-zinc-800/30',
              'has-[:focus-visible]:outline-2 has-[:focus-visible]:-outline-offset-2 has-[:focus-visible]:outline-brand-500',
            )}
          >
            <input
              id={inputId}
              type="radio"
              name={groupName}
              value={plan.code}
              checked={isSelected}
              disabled={unchanged || busy}
              onChange={() => onSelect(plan.code)}
              aria-labelledby={`${inputId}-name`}
              aria-describedby={isSelected ? detailsId : undefined}
              className="sr-only"
            />
            {content}
          </label>
        ) : (
          <div className={rowGrid}>{content}</div>
        )}
        {isSelected && impact && (
          <div id={detailsId} className="flex animate-fade-in flex-col gap-3 border-t border-brand-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 md:ps-[3.25rem] dark:border-brand-500/15">
            <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">
              {impact === 'trial' && t('billing.page.plans.impactTrial')}
              {impact === 'upgrade' && t('billing.page.plans.impactUpgrade')}
              {impact === 'downgrade' && t('billing.page.plans.impactDowngrade', { date: periodEnd })}
              {impact === 'immediate' && t('billing.page.plans.impactImmediate')}
            </p>
            <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center">
              <button type="button" className={buttonClasses('ghost', 'md')} onClick={() => onSelect(null)} disabled={busy}>
                {t('billing.page.plans.clear')}
              </button>
              <button type="button" className={buttonClasses('primary', 'md')} onClick={() => onConfirm(plan)} disabled={busy}>
                {current
                  ? t('billing.page.plans.switchInterval', { interval: i18n.language === 'he' ? intervalName : intervalName.toLowerCase() })
                  : t('billing.page.plans.switchTo', { plan: plan.name })}
              </button>
            </div>
          </div>
        )}
      </div>
    )
  })

  return (
    <div className="overflow-hidden rounded-xl border border-zinc-200/80 bg-white shadow-card dark:border-zinc-800 dark:bg-zinc-900">
      <div role={manage ? 'radiogroup' : 'list'} aria-label={t('billing.page.plans.listLabel')} className="divide-y divide-zinc-100 dark:divide-zinc-800">
        {rows}
      </div>
    </div>
  )
}
