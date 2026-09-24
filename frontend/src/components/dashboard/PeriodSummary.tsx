import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { formatCurrency, formatDate } from '../../lib/format'
import type { CurrencyAmount, DashboardStats, PeriodComparison } from '../../types/dashboard'
import { Count, Money } from '../Money'
import { Card } from '../ui'
import { cx } from '../ui-classes'

// The business's own currency first, matching the rest of the dashboard.
function rowsOrZero(amounts: CurrencyAmount[]): CurrencyAmount[] {
  if (amounts.length === 0) return [{ currency: 'ILS', amount: 0 }]
  return [...amounts].sort((a, b) => Number(b.currency === 'ILS') - Number(a.currency === 'ILS') || a.currency.localeCompare(b.currency))
}

/** A quiet, fully worded comparison: direction, percentage, amount and the actual previous range. */
function ComparisonLine({ comparison, previousRange }: { comparison: PeriodComparison | undefined; previousRange: string }) {
  const { t, i18n } = useTranslation()
  if (!comparison || comparison.percentage_change === null || comparison.amount_change === null) {
    return <p className="mt-2 text-xs text-zinc-500 dark:text-zinc-400">{t('dashboard.noComparisonBaseline')}</p>
  }
  const change = comparison.percentage_change
  const amount = Math.abs(Number(comparison.amount_change))
  const direction = change > 0 ? 'up' : change < 0 ? 'down' : 'flat'
  const Icon = direction === 'up' ? ArrowUpRight : direction === 'down' ? ArrowDownRight : Minus
  return (
    <p className="mt-2 flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-xs text-zinc-500 dark:text-zinc-400">
      <span
        className={cx(
          'inline-flex items-center gap-0.5 font-medium',
          direction === 'up' && 'text-success-700 dark:text-success-500',
          direction === 'down' && 'text-danger-700 dark:text-danger-500',
          direction === 'flat' && 'text-zinc-600 dark:text-zinc-300',
        )}
      >
        <Icon className="h-3.5 w-3.5 rtl:-scale-x-100" aria-hidden="true" />
        <span className="sr-only">{direction === 'up' ? t('dashboard.summary.increase') : direction === 'down' ? t('dashboard.summary.decrease') : t('dashboard.summary.noChange')}</span>
        <bdi className="figure">{Math.abs(change).toFixed(1)}%</bdi>
      </span>
      <bdi className="figure">({direction === 'down' ? '−' : direction === 'up' ? '+' : ''}{formatCurrency(amount, comparison.currency, i18n.language)})</bdi>
      <span>{t('dashboard.summary.vsPrevious', { range: previousRange })}</span>
    </p>
  )
}

function SupportingFigure({
  label,
  hint,
  children,
  to,
  linkLabel,
}: {
  label: string
  hint: string
  children: React.ReactNode
  to?: string
  linkLabel?: string
}) {
  return (
    <div className="min-w-0 px-5 py-4 sm:px-6">
      <dt className="text-sm text-zinc-600 dark:text-zinc-400">{label}</dt>
      <dd className="mt-1.5 space-y-0.5 text-lg font-medium text-zinc-900 dark:text-zinc-50">{children}</dd>
      <dd className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
        {hint}
        {to && linkLabel && (
          <>
            {' · '}
            <Link to={to} className="font-medium text-brand-700 underline-offset-2 hover:underline dark:text-brand-300">
              {linkLabel}
            </Link>
          </>
        )}
      </dd>
    </div>
  )
}

export function PeriodSummary({ data, showComparison }: { data: DashboardStats; showComparison: boolean }) {
  const { t, i18n } = useTranslation()
  const net = rowsOrZero(data.net_revenue_current_period)
  const gross = rowsOrZero(data.gross_revenue)
  const average = rowsOrZero(data.average_transaction_value)
  const multiCurrency = new Set([...data.net_revenue_current_period, ...data.gross_revenue].map((row) => row.currency)).size > 1
  const range = t('dashboard.summary.range', { start: formatDate(data.period.start_date, i18n.language), end: formatDate(data.period.end_date, i18n.language) })
  const previousRange = t('dashboard.summary.range', {
    start: formatDate(data.period.previous_start_date, i18n.language),
    end: formatDate(data.period.previous_end_date, i18n.language),
  })

  return (
    <Card aria-labelledby="period-summary-title">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-zinc-100 px-5 py-3.5 sm:px-6 dark:border-zinc-800">
        <h2 id="period-summary-title" className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{t('dashboard.summary.title')}</h2>
        <p className="text-xs text-zinc-500 dark:text-zinc-400"><bdi>{range}</bdi></p>
      </div>

      <div className="px-5 pt-5 pb-6 sm:px-6">
        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t('dashboard.netRevenue')}</p>
        <div className={cx('mt-2', multiCurrency && 'grid gap-5 sm:grid-cols-2 lg:grid-cols-3')}>
          {net.map((row) => (
            <div key={row.currency} className={cx(multiCurrency && 'border-s-2 border-zinc-200 ps-3 dark:border-zinc-700')}>
              {multiCurrency && (
                <p className="mb-0.5 text-[11px] font-medium tracking-wider text-zinc-500 dark:text-zinc-400">{row.currency}</p>
              )}
              <p className={cx('font-medium tracking-[-0.02em] text-zinc-900 dark:text-zinc-50', multiCurrency ? 'text-2xl' : 'text-[2rem] leading-tight sm:text-[2.25rem]')}>
                <Money amount={row.amount} currency={row.currency} animate />
              </p>
              {showComparison && (
                <ComparisonLine comparison={data.comparison.find((c) => c.currency === row.currency)} previousRange={previousRange} />
              )}
            </div>
          ))}
        </div>
        <p className="mt-4 max-w-2xl text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
          {t('dashboard.netRevenueExplanation')} {t('dashboard.summary.scope')}
          {multiCurrency && <> {t('dashboard.summary.multiCurrencyNote')}</>}
        </p>
      </div>

      <dl className="grid grid-cols-1 divide-y divide-zinc-100 border-t border-zinc-100 bg-zinc-50/60 sm:grid-cols-3 sm:divide-x sm:divide-y-0 dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-950/30">
        <SupportingFigure
          label={t('dashboard.grossRevenue')}
          hint={t('dashboard.summary.grossHint')}
          to={`/sales?date_from=${data.period.start_date}&date_to=${data.period.end_date}`}
          linkLabel={t('dashboard.summary.viewSales')}
        >
          {gross.map((row) => <span key={row.currency} className="block"><Money amount={row.amount} currency={row.currency} animate /></span>)}
        </SupportingFigure>
        <SupportingFigure label={t('dashboard.successfulSalesCount')} hint={t('dashboard.summary.countHint')}>
          <Count value={data.successful_sales_count} />
        </SupportingFigure>
        <SupportingFigure label={t('dashboard.averageTransactionValue')} hint={t('dashboard.summary.averageHint')}>
          {average.map((row) => <span key={row.currency} className="block"><Money amount={row.amount} currency={row.currency} animate /></span>)}
        </SupportingFigure>
      </dl>
    </Card>
  )
}
