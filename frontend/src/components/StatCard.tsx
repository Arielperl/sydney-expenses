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
  const hasChange = changePercent !== undefined && changePercent !== null
  const isIncrease = hasChange && changePercent! > 0
  const isDecrease = hasChange && changePercent! < 0

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">
        {formatCurrency(amount, currency, i18n.language)}
      </p>
      {hasChange && (
        <p
          className={[
            'mt-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
            isIncrease
              ? 'bg-danger-50 text-danger-700'
              : isDecrease
                ? 'bg-success-50 text-success-700'
                : 'bg-slate-100 text-slate-600',
          ].join(' ')}
        >
          {isIncrease ? '▲' : isDecrease ? '▼' : '–'} {Math.abs(changePercent!).toFixed(1)}%{' '}
          {t('dashboard.vsLastMonth')}
        </p>
      )}
    </div>
  )
}
