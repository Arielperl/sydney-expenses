import { useTranslation } from 'react-i18next'

import { formatCurrency } from '../../lib/format'
import { colorForService } from '../../lib/serviceColors'
import type { TopService } from '../../types/dashboard'

/** A compact ranked list — deliberately not a chart. A bar/pie chart reads
 * fine with a dozen data points; the top-services list on a small demo
 * business is often 1-3 rows, where a chart looks empty and unintentional.
 * A ranked list with a share-of-revenue bar looks complete at any size. */
export function TopServicesList({ services, currency }: { services: TopService[]; currency: string }) {
  const { t, i18n } = useTranslation()
  const rows = services.filter((service) => service.currency === currency)

  if (rows.length === 0) {
    return (
      <p className="py-6 text-center text-sm text-stone-500 dark:text-stone-400">
        {t('dashboard.topServicesEmpty')}
      </p>
    )
  }

  return (
    <ol className="space-y-3">
      {rows.map((service, index) => (
        <li key={`${service.service_name}-${service.currency}`}>
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <span
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
                style={{ backgroundColor: colorForService(service.service_name) }}
                aria-hidden="true"
              >
                {index + 1}
              </span>
              <span className="truncate text-sm font-medium text-stone-800 dark:text-stone-100">
                {service.service_name}
              </span>
            </div>
            <span className="shrink-0 text-sm font-semibold tabular-nums text-stone-900 dark:text-stone-100">
              {formatCurrency(service.total, service.currency, i18n.language)}
            </span>
          </div>
          <div className="mt-1.5 flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${Math.min(service.percentage_of_revenue, 100)}%`,
                  backgroundColor: colorForService(service.service_name),
                }}
              />
            </div>
            <span className="shrink-0 text-xs tabular-nums text-stone-400 dark:text-stone-500">
              {service.percentage_of_revenue.toFixed(0)}%
            </span>
          </div>
          <p className="mt-0.5 text-xs text-stone-400 dark:text-stone-500">
            {t('dashboard.topServicesSaleCount', { count: service.count })}
          </p>
        </li>
      ))}
    </ol>
  )
}
