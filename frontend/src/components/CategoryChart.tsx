import { useTranslation } from 'react-i18next'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from 'recharts'

import type { CategoryTotal } from '../types/dashboard'
import { colorForCategory } from '../lib/categoryColors'
import { formatCurrency } from '../lib/format'

export function CategoryChart({ data, currency }: { data: CategoryTotal[]; currency: string }) {
  const { t, i18n } = useTranslation()
  const chartData = data.map((item) => ({
    category: t(`categories.${item.category}`, item.category),
    rawCategory: item.category,
    total: Number(item.total),
  }))

  return (
    <div className="h-72 w-full" dir="ltr">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 24, top: 8, bottom: 8 }}>
          <CartesianGrid horizontal={false} stroke="#e2e8f0" />
          <XAxis
            type="number"
            tickFormatter={(value: number) => formatCurrency(value, currency, i18n.language)}
            tick={{ fontSize: 12, fill: '#64748b' }}
          />
          <YAxis
            type="category"
            dataKey="category"
            width={100}
            orientation={i18n.dir() === 'rtl' ? 'right' : 'left'}
            tick={{ fontSize: 12, fill: '#334155' }}
          />
          <Tooltip
            formatter={(value) => formatCurrency(Number(value), currency, i18n.language)}
            cursor={{ fill: '#f1f5f9' }}
          />
          <Bar dataKey="total" radius={[0, 4, 4, 0]} barSize={18}>
            {chartData.map((entry) => (
              <Cell key={entry.rawCategory} fill={colorForCategory(entry.rawCategory)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
