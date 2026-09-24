import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useTranslation } from 'react-i18next'
import { useId } from 'react'

import type { RevenueTrendPoint, TrendGranularity } from '../types/dashboard'
import { useTheme } from '../contexts/ThemeContext'
import { prefersReducedMotion } from '../hooks/useAnimatedNumber'
import { getChartColors } from '../lib/chartColors'
import { formatCompactCurrency, formatCurrency, formatTrendPeriodLabel } from '../lib/format'

function ChartTooltip({ active, payload, label, currency, metricLabel }: {
  active?: boolean
  payload?: { value?: number | string }[]
  label?: string
  currency: string
  metricLabel: string
}) {
  const { i18n } = useTranslation()
  if (!active || !payload?.length) return null
  return (
    <div dir={i18n.dir()} className="rounded-lg border border-zinc-200 bg-white px-3 py-2 text-xs shadow-raised dark:border-zinc-700 dark:bg-zinc-900">
      <p className="text-zinc-500 dark:text-zinc-400">{label}</p>
      <p className="mt-0.5 text-zinc-600 dark:text-zinc-300">
        {metricLabel}:{' '}
        <bdi className="figure font-semibold text-zinc-900 dark:text-zinc-50">{formatCurrency(Number(payload[0].value ?? 0), currency, i18n.language)}</bdi>
      </p>
    </div>
  )
}

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
  const gradientId = useId().replace(/:/g, '')
  const colors = getChartColors(resolvedTheme)
  const chartData = data.map((point) => ({
    period: formatTrendPeriodLabel(point.period_start, i18n.language, granularity),
    total: Number(metric === 'gross' ? point.gross_total : point.net_total),
  }))
  const hasAnyRevenue = chartData.some((point) => point.total > 0)

  if (!hasAnyRevenue) {
    return (
      <div className="flex h-60 w-full flex-col items-center justify-center rounded-lg border border-dashed border-zinc-200 px-6 text-center dark:border-zinc-800">
        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">{t('dashboard.trendEmptyTitle')}</p>
        <p className="mt-1 max-w-xs text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">{t('dashboard.trendEmptyDescription')}</p>
      </div>
    )
  }

  return (
    // Time runs left-to-right in both languages, as in financial reporting; labels stay localized.
    <div className="h-64 w-full sm:h-72" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ left: 4, right: 12, top: 8, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={colors.seriesFill} stopOpacity={resolvedTheme === 'dark' ? 0.28 : 0.18} />
              <stop offset="100%" stopColor={colors.seriesFill} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={colors.grid} strokeDasharray="3 4" vertical={false} />
          <XAxis dataKey="period" tick={{ fontSize: 11, fill: colors.tick }} tickLine={false} axisLine={false} tickMargin={10} minTickGap={16} />
          <YAxis
            tickFormatter={(value: number) => formatCompactCurrency(value, currency, i18n.language)}
            tick={{ fontSize: 11, fill: colors.tick }}
            tickLine={false}
            axisLine={false}
            width={60}
          />
          <Tooltip
            cursor={{ stroke: colors.tooltipCursor, strokeWidth: 1 }}
            content={<ChartTooltip currency={currency} metricLabel={t(`dashboard.trendMetric.${metric}`)} />}
          />
          <Area
            type="monotone"
            dataKey="total"
            stroke={colors.series}
            strokeWidth={2}
            fill={`url(#${gradientId})`}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 2, stroke: resolvedTheme === 'dark' ? '#151a19' : '#ffffff', fill: colors.series }}
            isAnimationActive={!prefersReducedMotion()}
            animationDuration={600}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
