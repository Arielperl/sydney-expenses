import { useTranslation } from 'react-i18next'

import { formatCurrency } from '../lib/format'
import type { CurrencyAmount } from '../types/dashboard'

function ChangeBadge({ changePercent }: { changePercent: number | null | undefined }) {
  const { t } = useTranslation()
  if (changePercent === undefined) return null

  // `changePercent === null` (as opposed to `undefined`) is a deliberate signal from
  // the backend: this currency tracks change, but the previous period had zero revenue,
  // so no percentage can be computed honestly — show that explicitly rather than hiding
  // it or fabricating a number.
  if (changePercent === null) {
    return (
      <p className="mt-2 inline-flex items-center gap-1 rounded-full bg-stone-100 px-2 py-0.5 text-xs font-medium text-stone-500 dark:bg-stone-800 dark:text-stone-400">
        {t('dashboard.noComparisonBaseline')}
      </p>
    )
  }

  const isIncrease = changePercent > 0
  const isDecrease = changePercent < 0
  return (
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
      {isIncrease ? '▲' : isDecrease ? '▼' : '–'} {Math.abs(changePercent).toFixed(1)}% {t('dashboard.vsLastMonth')}
    </p>
  )
}

/** A dashboard money card. `amounts` is always a list — a single-currency
 * dataset naturally produces one element (rendered exactly like a plain
 * figure); a dataset spanning more than one currency renders one clearly
 * labeled row per currency, never a combined number. See
 * dashboard_service.py's module docstring on the backend for why. */
export function StatCard({
  label,
  amounts,
  changePercentByCurrency,
  fallbackCurrency = 'ILS',
}: {
  label: string
  amounts: CurrencyAmount[]
  changePercentByCurrency?: Record<string, number | null>
  fallbackCurrency?: string
}) {
  const { i18n } = useTranslation()
  const rows = amounts.length > 0 ? amounts : [{ currency: fallbackCurrency, amount: 0 }]
  const isMultiCurrency = amounts.length > 1

  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900">
      <p className="text-sm font-medium text-stone-500 dark:text-stone-400">{label}</p>
      <div className={isMultiCurrency ? 'mt-2 space-y-3' : undefined}>
        {rows.map((row) => (
          <div key={row.currency}>
            {isMultiCurrency && (
              <p className="text-xs font-semibold tracking-wide text-stone-400 uppercase dark:text-stone-500">
                {row.currency}
              </p>
            )}
            <p
              className={[
                'font-semibold tracking-tight tabular-nums text-stone-900 dark:text-stone-100',
                isMultiCurrency ? 'text-xl' : 'mt-2 text-3xl',
              ].join(' ')}
            >
              {formatCurrency(row.amount, row.currency, i18n.language)}
            </p>
            {changePercentByCurrency && <ChangeBadge changePercent={changePercentByCurrency[row.currency]} />}
          </div>
        ))}
      </div>
    </div>
  )
}
