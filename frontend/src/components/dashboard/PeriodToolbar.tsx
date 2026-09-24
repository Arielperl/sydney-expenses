import { CalendarRange } from 'lucide-react'
import { useTranslation } from 'react-i18next'

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
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
      <div className="relative">
        <label htmlFor="dashboard-period" className="sr-only">
          {t('dashboard.periodLabel')}
        </label>
        <CalendarRange className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" aria-hidden="true" />
        <select
          id="dashboard-period"
          value={period}
          onChange={(event) => onPeriodChange(event.target.value as DashboardPeriodName)}
          className={`${inputClasses} w-full min-w-[12rem] ps-9 font-medium sm:w-auto`}
        >
          {DASHBOARD_PERIODS.map((value) => (
            <option key={value} value={value}>
              {t(`dashboard.period.${value}`)}
            </option>
          ))}
        </select>
      </div>

      {period === 'custom' && (
        <div className="flex items-center gap-2">
          <input
            type="date"
            aria-label={t('sales.dateFromLabel')}
            value={customStart}
            onChange={(event) => onCustomStartChange(event.target.value)}
            className={`${inputClasses} w-auto`}
          />
          <span className="text-zinc-500" aria-hidden="true">–</span>
          <input
            type="date"
            aria-label={t('sales.dateToLabel')}
            value={customEnd}
            onChange={(event) => onCustomEndChange(event.target.value)}
            className={`${inputClasses} w-auto`}
          />
        </div>
      )}

      <label className="inline-flex cursor-pointer items-center gap-2.5 text-sm text-zinc-700 select-none dark:text-zinc-300">
        <input
          type="checkbox"
          checked={showComparison}
          onChange={(event) => onToggleComparison(event.target.checked)}
          className="h-4 w-4 rounded border-zinc-300 accent-brand-600 dark:border-zinc-600"
        />
        {t('dashboard.compareToPreviousPeriod')}
      </label>
    </div>
  )
}
