import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useTranslation } from 'react-i18next'

import type { RevenueTrendPoint, TrendGranularity } from '../types/dashboard'
import { useTheme } from '../contexts/ThemeContext'
import { getChartColors } from '../lib/chartColors'
import { formatCompactCurrency, formatCurrency, formatTrendPeriodLabel } from '../lib/format'

export function RevenueTrendChart({
  data,
  currency,
  metric,
  granularity,
}: {
  data: RevenueTrendPoint[]
  currency: string
  metric: 'gross' | 'net'
  granularity: TrendGranularity
}) {
  const { t, i18n } = useTranslation()
  const { resolvedTheme } = useTheme()
  const colors = getChartColors(resolvedTheme)
  const chartData = data.map((point) => ({
    period: formatTrendPeriodLabel(point.period_start, i18n.language, granularity),
    total: Number(metric === 'gross' ? point.gross_total : point.net_total),
  }))
  const hasAnyRevenue = chartData.some((point) => point.total > 0)

  if (!hasAnyRevenue) {
    return (
      <div className="flex h-64 w-full flex-col items-center justify-center rounded-lg border border-dashed border-stone-200 text-center dark:border-stone-800">
        <p className="text-sm font-medium text-stone-500 dark:text-stone-400">{t('dashboard.trendEmptyTitle')}</p>
        <p className="mt-1 max-w-xs text-xs text-stone-400 dark:text-stone-500">{t('dashboard.trendEmptyDescription')}</p>
      </div>
    )
  }

  return (
    <div className="h-72 w-full sm:h-80" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ left: 8, right: 16, top: 8, bottom: 8 }}>
          <CartesianGrid stroke={colors.grid} />
          <XAxis dataKey="period" tick={{ fontSize: 12, fill: colors.tick }} tickMargin={8} />
          <YAxis
            tickFormatter={(value: number) => formatCompactCurrency(value, currency, i18n.language)}
            tick={{ fontSize: 12, fill: colors.tick }}
            width={64}
          />
          <Tooltip
            formatter={(value) => formatCurrency(Number(value), currency, i18n.language)}
            contentStyle={{ direction: i18n.dir() === 'rtl' ? 'rtl' : 'ltr' }}
          />
          <Line
            type="monotone"
            dataKey="total"
            stroke="#0d9488"
            strokeWidth={2.5}
            dot={{ r: 3, fill: '#0d9488' }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
