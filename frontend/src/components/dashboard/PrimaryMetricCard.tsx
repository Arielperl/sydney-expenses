import { useTranslation } from 'react-i18next'

import { formatCurrency } from '../../lib/format'
import type { CurrencyAmount, PeriodComparison } from '../../types/dashboard'

function ComparisonBadge({ comparison }: { comparison: PeriodComparison | undefined }) {
  const { t } = useTranslation()
  if (!comparison || comparison.percentage_change === null || comparison.amount_change === null) {
    return (
      <p className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-stone-100 px-3 py-1 text-xs font-medium text-stone-500 dark:bg-stone-800 dark:text-stone-400">
        {t('dashboard.noComparisonBaseline')}
      </p>
    )
  }

  const { percentage_change: percentageChange, amount_change: amountChange, currency } = comparison
  const isIncrease = percentageChange > 0
  const isDecrease = percentageChange < 0
  const amountNumber = Number(amountChange)
  const signedAmount = formatCurrency(Math.abs(amountNumber), currency, 'he')

  return (
    <p
      className={[
        'mt-3 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold',
        isIncrease
          ? 'bg-success-500/10 text-success-700 dark:text-success-400'
          : isDecrease
            ? 'bg-danger-500/10 text-danger-700 dark:text-danger-400'
            : 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-400',
      ].join(' ')}
    >
      <span aria-hidden="true">{isIncrease ? '▲' : isDecrease ? '▼' : '–'}</span>
      {Math.abs(percentageChange).toFixed(1)}% ({isIncrease ? '+' : isDecrease ? '−' : ''}
      {signedAmount}) {t('dashboard.comparedToPreviousPeriod')}
    </p>
  )
}

/** The single, clearly dominant card on the dashboard — net revenue after
 * VAT, processing fees, and refunds. Deliberately never labeled "income" or
 * "profit": true accounting profit would also require the business's own
 * expenses, which this app does not track — see `explanationText`. */
export function PrimaryMetricCard({
  label,
  explanation,
  amounts,
  comparisons,
  showComparison,
}: {
  label: string
  explanation: string
  amounts: CurrencyAmount[]
  comparisons: PeriodComparison[]
  showComparison: boolean
}) {
  const { i18n } = useTranslation()
  const rows = amounts.length > 0 ? amounts : [{ currency: 'ILS', amount: 0 }]
  const isMultiCurrency = amounts.length > 1

  return (
    <div className="rounded-xl border-s-4 border-brand-600 bg-white p-6 shadow-sm dark:border-brand-500 dark:bg-stone-900 sm:p-8">
      <p className="text-sm font-semibold text-stone-500 dark:text-stone-400">{label}</p>
      <div className={isMultiCurrency ? 'mt-3 space-y-4' : undefined}>
        {rows.map((row) => (
          <div key={row.currency}>
            {isMultiCurrency && (
              <p className="text-xs font-semibold tracking-wide text-stone-400 uppercase dark:text-stone-500">
                {row.currency}
              </p>
            )}
            <p
              className={[
                'font-bold tracking-tight tabular-nums text-stone-900 dark:text-stone-100',
                isMultiCurrency ? 'text-3xl' : 'mt-2 text-4xl sm:text-5xl',
              ].join(' ')}
            >
              {formatCurrency(row.amount, row.currency, i18n.language)}
            </p>
            {showComparison && (
              <ComparisonBadge comparison={comparisons.find((c) => c.currency === row.currency)} />
            )}
          </div>
        ))}
      </div>
      <p className="mt-4 text-sm text-stone-500 dark:text-stone-400">{explanation}</p>
    </div>
  )
}
