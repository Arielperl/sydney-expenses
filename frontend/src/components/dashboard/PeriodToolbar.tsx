import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { inputClasses } from '../FormField'
import { DASHBOARD_PERIODS, type DashboardPeriodName } from '../../types/dashboard'

export function PeriodToolbar({
  period,
  onPeriodChange,
  customStart,
  customEnd,
  onCustomStartChange,
  onCustomEndChange,
  showComparison,
  onToggleComparison,
}: {
  period: DashboardPeriodName
  onPeriodChange: (period: DashboardPeriodName) => void
  customStart: string
  customEnd: string
  onCustomStartChange: (value: string) => void
  onCustomEndChange: (value: string) => void
  showComparison: boolean
  onToggleComparison: (value: boolean) => void
}) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-zinc-200 bg-white p-3 shadow-sm sm:flex-row sm:flex-wrap sm:items-center sm:justify-between dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex flex-wrap items-center gap-2">
        <label htmlFor="dashboard-period" className="sr-only">
          {t('dashboard.periodLabel')}
        </label>
        <select
          id="dashboard-period"
          value={period}
          onChange={(event) => onPeriodChange(event.target.value as DashboardPeriodName)}
          className={`${inputClasses} w-auto min-w-[10rem]`}
        >
          {DASHBOARD_PERIODS.map((value) => (
            <option key={value} value={value}>
              {t(`dashboard.period.${value}`)}
            </option>
          ))}
        </select>

        {period === 'custom' && (
          <div className="flex items-center gap-2">
            <input
              type="date"
              aria-label={t('sales.dateFromLabel')}
              value={customStart}
              onChange={(event) => onCustomStartChange(event.target.value)}
              className={`${inputClasses} w-auto`}
            />
            <span className="text-zinc-400">–</span>
            <input
              type="date"
              aria-label={t('sales.dateToLabel')}
              value={customEnd}
              onChange={(event) => onCustomEndChange(event.target.value)}
              className={`${inputClasses} w-auto`}
            />
          </div>
        )}

        <label className="flex items-center gap-2 rounded-lg border border-zinc-300 px-3 py-2 text-sm font-medium text-zinc-700 dark:border-zinc-700 dark:text-zinc-200">
          <input
            type="checkbox"
            checked={showComparison}
            onChange={(event) => onToggleComparison(event.target.checked)}
            className="h-4 w-4 rounded border-zinc-300 text-brand-600 focus:ring-brand-500 dark:border-zinc-600"
          />
          {t('dashboard.compareToPreviousPeriod')}
        </label>
      </div>

      <Link
        to="/add-sale"
        className="inline-flex shrink-0 items-center justify-center rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
      >
        {t('sales.addSaleManually')}
      </Link>
    </div>
  )
}
