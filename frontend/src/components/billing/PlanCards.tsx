import { Check } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { formatCount, formatPlanPrice, planPriceParts, priceFor } from '../../lib/billing'
import type { BillingInterval, BillingPlan } from '../../services/billingService'
import { cx } from '../ui-classes'

/**
 * The plan comparison, drawn once for every surface.
 *
 * `public` sits on the marketing site and onboarding, which are light-only;
 * `app` lives inside the product and follows the dark theme. The recommended
 * plan earns attention through position (centre), a brand border and a quiet
 * label: never size, colour floods or motion.
 */
export type PlanSurface = 'public' | 'app'

const dark = (surface: PlanSurface, classes: string) => (surface === 'app' ? classes : '')

export function IntervalToggle({
  value,
  onChange,
  surface,
  savingsMonths,
}: {
  value: BillingInterval
  onChange: (value: BillingInterval) => void
  surface: PlanSurface
  savingsMonths: number | null
}) {
  const { t } = useTranslation(undefined, { lng: surface === 'public' ? 'he' : undefined })
  return (
    <div
      role="radiogroup"
      aria-label={t('billing.intervalLabel')}
      className={cx('inline-flex rounded-xl bg-zinc-100 p-1 text-sm font-medium ring-1 ring-zinc-200/70 ring-inset', dark(surface, 'dark:bg-zinc-800 dark:ring-zinc-700'))}
    >
      {(['month', 'year'] as const).map((interval) => {
        const active = interval === value
        return (
          <button
            key={interval}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(interval)}
            onKeyDown={(event) => {
              if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
                event.preventDefault()
                onChange(interval === 'month' ? 'year' : 'month')
                const sibling = event.currentTarget.parentElement?.querySelector<HTMLButtonElement>(`[data-interval="${interval === 'month' ? 'year' : 'month'}"]`)
                sibling?.focus()
              }
            }}
            tabIndex={active ? 0 : -1}
            data-interval={interval}
            className={cx(
              'inline-flex min-h-9 items-center gap-2 rounded-lg px-4 transition-colors duration-150',
              active
                ? cx('bg-white text-zinc-900 shadow-card', dark(surface, 'dark:bg-zinc-950 dark:text-zinc-50'))
                : cx('text-zinc-600 hover:text-zinc-900', dark(surface, 'dark:text-zinc-400 dark:hover:text-zinc-100')),
            )}
          >
            {t(`billing.interval.${interval}`)}
            {interval === 'year' && savingsMonths && (
              <span className={cx('rounded-full bg-brand-50 px-2 py-0.5 text-[11px] font-semibold text-brand-800', dark(surface, 'dark:bg-brand-500/15 dark:text-brand-200'))}>
                {t('billing.yearlySavings', { count: savingsMonths })}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}

function PlanPrice({ plan, interval, surface }: { plan: BillingPlan; interval: BillingInterval; surface: PlanSurface }) {
  const { t, i18n } = useTranslation(undefined, { lng: surface === 'public' ? 'he' : undefined })
  const language = surface === 'public' ? 'he' : i18n.language
  const minor = priceFor(plan, interval)
  if (minor === null) return null
  const monthly = plan.prices.month
  return (
    <div className="mt-6">
      <p className="flex flex-wrap items-baseline gap-x-1.5">
        <bdi className={cx('figure inline-flex items-baseline gap-1 text-[2.5rem] leading-none font-medium tracking-[-0.02em] text-zinc-900', dark(surface, 'dark:text-zinc-50'))}>
          <span className="sr-only">{formatPlanPrice(minor, language)}</span>
          {planPriceParts(minor, language).map((part, index) => (
            <span
              key={index}
              aria-hidden="true"
              className={part.currency ? cx('text-[1.375rem] font-normal text-zinc-500', dark(surface, 'dark:text-zinc-400')) : undefined}
            >
              {part.text}
            </span>
          ))}
        </bdi>
        <span className={cx('text-sm text-zinc-600', dark(surface, 'dark:text-zinc-400'))}>
          {t(interval === 'month' ? 'billing.perMonth' : 'billing.perYear')}
        </span>
      </p>
      <p className={cx('mt-2 text-xs text-zinc-500', dark(surface, 'dark:text-zinc-400'))}>
        {t('billing.excludingVat')}
        {interval === 'year' && monthly && (
          <> · {t('billing.insteadOf', { amount: formatPlanPrice(monthly * 12, language) })}</>
        )}
      </p>
    </div>
  )
}

function PlanLimits({ plan, surface, showMembers }: { plan: BillingPlan; surface: PlanSurface; showMembers: boolean }) {
  const { t, i18n } = useTranslation(undefined, { lng: surface === 'public' ? 'he' : undefined })
  const language = surface === 'public' ? 'he' : i18n.language
  const limits = [
    t('billing.limits.connections', { count: plan.max_connections }),
    t('billing.limits.aiQuestions', { amount: formatCount(plan.ai_questions_per_month, language) }),
    ...(showMembers ? [t('billing.limits.members', { count: plan.max_members })] : []),
  ]
  return (
    <ul className={cx('space-y-2 text-sm text-zinc-900', dark(surface, 'dark:text-zinc-100'))}>
      {limits.map((limit) => (
        <li key={limit} className="flex items-center gap-2.5 font-medium">
          <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500', dark(surface, 'dark:bg-brand-400'))} aria-hidden="true" />
          <span className="figure">{limit}</span>
        </li>
      ))}
    </ul>
  )
}

export function PlanCards({
  plans,
  interval,
  surface,
  showMembers = false,
  currentPlanCode,
  selection,
  renderAction,
  headingLevel = 'h3',
}: {
  plans: BillingPlan[]
  interval: BillingInterval
  surface: PlanSurface
  showMembers?: boolean
  currentPlanCode?: string | null
  /** Turns the cards into a radio group. Nothing is selected until the owner chooses. */
  selection?: { name: string; value: string | null; onChange: (code: string) => void; label: string }
  renderAction?: (plan: BillingPlan) => ReactNode
  headingLevel?: 'h2' | 'h3'
}) {
  const { t } = useTranslation(undefined, { lng: surface === 'public' ? 'he' : undefined })
  const Heading = headingLevel
  const selectable = Boolean(selection)

  const cards = plans.map((plan) => {
    const recommended = plan.recommended
    const selected = selection?.value === plan.code
    const current = currentPlanCode === plan.code
    const inputId = `${selection?.name ?? 'plan'}-${plan.code}`
    const body = (
      <>
        {recommended && (
          <span
            className={cx(
              'absolute inset-x-0 top-0 flex h-8 items-center justify-center rounded-t-[14px] bg-brand-600 text-xs font-semibold tracking-wide text-white',
              dark(surface, 'dark:bg-brand-500 dark:text-brand-950'),
            )}
          >
            {t('billing.recommended')}
          </span>
        )}
        {/* Keeps names and prices level across the row; the recommended band occupies this space. */}
        <div className={cx('flex items-start justify-between gap-3', recommended ? 'mt-8' : 'md:mt-8')}>
          <div className="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
            <Heading id={`${inputId}-name`} className={cx('text-lg font-semibold text-zinc-900', dark(surface, 'dark:text-zinc-50'))}>
              <bdi>{plan.name}</bdi>
            </Heading>
            {current && (
              <span className={cx('rounded-full bg-zinc-100 px-2 py-0.5 text-[11px] font-medium text-zinc-700 ring-1 ring-zinc-200 ring-inset', dark(surface, 'dark:bg-zinc-800 dark:text-zinc-300 dark:ring-zinc-700'))}>
                {t('billing.currentPlan')}
              </span>
            )}
          </div>
          {selectable && (
            <span
              aria-hidden="true"
              className={cx(
                'mt-1 grid h-5 w-5 shrink-0 place-items-center rounded-full border-2 transition-colors',
                selected
                  ? cx('border-brand-600 bg-brand-600', dark(surface, 'dark:border-brand-400 dark:bg-brand-400'))
                  : cx('border-zinc-300 bg-white', dark(surface, 'dark:border-zinc-600 dark:bg-zinc-900')),
              )}
            >
              {selected && <span className={cx('h-1.5 w-1.5 rounded-full bg-white', dark(surface, 'dark:bg-zinc-950'))} />}
            </span>
          )}
        </div>
        <p className={cx('mt-1 text-sm leading-relaxed text-zinc-600', dark(surface, 'dark:text-zinc-400'))} dir="auto">
          {plan.tagline}
        </p>
        <PlanPrice plan={plan} interval={interval} surface={surface} />
        <div className={cx('my-6 border-t border-zinc-100', dark(surface, 'dark:border-zinc-800'))} />
        <PlanLimits plan={plan} surface={surface} showMembers={showMembers} />
        <ul className={cx('mt-4 space-y-2.5 text-sm text-zinc-700', dark(surface, 'dark:text-zinc-300'))}>
          {plan.features.map((feature) => (
            <li key={feature} className="flex items-start gap-2.5" dir="auto">
              <Check className={cx('mt-0.5 h-4 w-4 shrink-0 text-brand-600', dark(surface, 'dark:text-brand-400'))} aria-hidden="true" />
              <span>{feature}</span>
            </li>
          ))}
        </ul>
        {renderAction && <div className="mt-auto pt-7">{renderAction(plan)}</div>}
      </>
    )

    const frame = cx(
      'relative flex h-full flex-col rounded-2xl bg-white p-6 text-start transition-[border-color,box-shadow,transform] duration-200 sm:p-7',
      dark(surface, 'dark:bg-zinc-900'),
      recommended
        // Stacked on narrow screens, the recommended plan comes first; side by side it takes the centre.
        ? cx('max-md:order-first border-2 border-brand-600 shadow-raised lg:-translate-y-2', dark(surface, 'dark:border-brand-400'))
        : cx('border border-zinc-200 shadow-card', dark(surface, 'dark:border-zinc-800')),
      selectable && 'cursor-pointer has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-brand-500',
      selectable && !recommended && !selected && cx('hover:border-zinc-300', dark(surface, 'dark:hover:border-zinc-700')),
      selectable && selected && !recommended && cx('border-brand-500 ring-1 ring-brand-500', dark(surface, 'dark:border-brand-400 dark:ring-brand-400')),
      selectable && selected && recommended && cx('ring-2 ring-brand-600/25', dark(surface, 'dark:ring-brand-400/30')),
    )

    if (selection) {
      return (
        <label key={plan.code} htmlFor={inputId} className={frame}>
          <input
            id={inputId}
            type="radio"
            name={selection.name}
            value={plan.code}
            checked={selected}
            onChange={() => selection.onChange(plan.code)}
            aria-labelledby={`${inputId}-name`}
            className="sr-only"
          />
          {body}
        </label>
      )
    }
    return (
      <article key={plan.code} className={frame} aria-labelledby={`${inputId}-name`}>
        {body}
      </article>
    )
  })

  const grid = 'grid items-stretch gap-5 md:grid-cols-3 lg:gap-6'
  return selection ? (
    <div role="radiogroup" aria-label={selection.label} className={grid}>
      {cards}
    </div>
  ) : (
    <div className={grid}>{cards}</div>
  )
}
