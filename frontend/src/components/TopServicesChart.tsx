import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from 'recharts'

import type { TopService } from '../types/dashboard'
import { useTheme } from '../contexts/ThemeContext'
import { colorForService } from '../lib/serviceColors'
import { getChartColors } from '../lib/chartColors'
import { formatCurrency } from '../lib/format'
import { useTranslation } from 'react-i18next'

export function TopServicesChart({ data, currency }: { data: TopService[]; currency: string }) {
  const { i18n } = useTranslation()
  const { resolvedTheme } = useTheme()
  const colors = getChartColors(resolvedTheme)
  const chartData = data.map((item) => ({ service: item.service_name, total: Number(item.total) }))

  return (
    <div className="h-72 w-full" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 24, top: 8, bottom: 8 }}>
          <CartesianGrid horizontal={false} stroke={colors.grid} />
          <XAxis
            type="number"
            tickFormatter={(value: number) => formatCurrency(value, currency, i18n.language)}
            tick={{ fontSize: 12, fill: colors.tick }}
          />
          <YAxis
            type="category"
            dataKey="service"
            width={120}
            orientation={i18n.dir() === 'rtl' ? 'right' : 'left'}
            tick={{ fontSize: 12, fill: colors.axisLabel }}
          />
          <Tooltip
            formatter={(value) => formatCurrency(Number(value), currency, i18n.language)}
            cursor={{ fill: colors.tooltipCursor }}
          />
          <Bar dataKey="total" radius={[0, 4, 4, 0]} barSize={18}>
            {chartData.map((entry) => (
              <Cell key={entry.service} fill={colorForService(entry.service)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
