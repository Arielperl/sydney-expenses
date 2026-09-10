import { useTranslation } from 'react-i18next'

import { formatCurrency } from '../lib/format'

export function StatCard({
  label,
  amount,
  currency,
  changePercent,
}: {
  label: string
  amount: number | string
  currency: string
  changePercent?: number | null
}) {
  const { t, i18n } = useTranslation()
  // `changePercent === null` (as opposed to `undefined`) is a deliberate signal from
  // the backend: this card tracks change, but the previous period had zero revenue, so
  // no percentage can be computed honestly — show that explicitly rather than hiding it
  // or fabricating a number.
  const hasNoBaseline = changePercent === null
  const hasChange = changePercent !== undefined && changePercent !== null
  const isIncrease = hasChange && changePercent! > 0
  const isDecrease = hasChange && changePercent! < 0

  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900">
      <p className="text-sm font-medium text-stone-500 dark:text-stone-400">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums text-stone-900 dark:text-stone-100">
        {formatCurrency(amount, currency, i18n.language)}
      </p>
      {hasChange && (
        <p
          className={[
            'mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
            isIncrease
              ? 'bg-success-500/10 text-success-700 dark:text-success-400'
              : isDecrease
                ? 'bg-danger-500/10 text-danger-700 dark:text-danger-400'
                : 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-400',
          ].join(' ')}
        >
          {isIncrease ? '▲' : isDecrease ? '▼' : '–'} {Math.abs(changePercent!).toFixed(1)}%{' '}
          {t('dashboard.vsLastMonth')}
        </p>
      )}
      {hasNoBaseline && (
        <p className="mt-2 inline-flex items-center gap-1 rounded-full bg-stone-100 px-2 py-0.5 text-xs font-medium text-stone-500 dark:bg-stone-800 dark:text-stone-400">
          {t('dashboard.noComparisonBaseline')}
        </p>
      )}
    </div>
  )
}
