import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useTranslation } from 'react-i18next'

import type { RevenueTrendPoint } from '../types/dashboard'
import { useTheme } from '../contexts/ThemeContext'
import { getChartColors } from '../lib/chartColors'
import { formatCurrency, formatDate } from '../lib/format'

export function RevenueTrendChart({ data, currency }: { data: RevenueTrendPoint[]; currency: string }) {
  const { i18n } = useTranslation()
  const { resolvedTheme } = useTheme()
  const colors = getChartColors(resolvedTheme)
  const chartData = data.map((point) => ({
    period: formatDate(point.period_start, i18n.language),
    total: Number(point.total),
  }))

  return (
    <div className="h-64 w-full" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ left: 8, right: 24, top: 8, bottom: 8 }}>
          <CartesianGrid stroke={colors.grid} />
          <XAxis dataKey="period" tick={{ fontSize: 12, fill: colors.tick }} />
          <YAxis
            tickFormatter={(value: number) => formatCurrency(value, currency, i18n.language)}
            tick={{ fontSize: 12, fill: colors.tick }}
            width={80}
          />
          <Tooltip formatter={(value) => formatCurrency(Number(value), currency, i18n.language)} />
          <Line type="monotone" dataKey="total" stroke="#2563eb" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
