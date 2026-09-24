import { useTranslation } from 'react-i18next'

import { colorForService } from '../../lib/serviceColors'
import type { TopService } from '../../types/dashboard'
import { Money } from '../Money'

/** A compact ranked list — deliberately not a chart. A bar/pie chart reads
 * fine with a dozen data points; the top-services list on a small
 * business is often 1-3 rows, where a chart looks empty and unintentional.
 * A ranked list with a share-of-revenue bar looks complete at any size. */
export function TopServicesList({ services, currency }: { services: TopService[]; currency: string }) {
  const { t } = useTranslation()
  const rows = services.filter((service) => service.currency === currency)

  if (rows.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-zinc-500 dark:text-zinc-400">
        {t('dashboard.topServicesEmpty')}
      </p>
    )
  }

  return (
    <ol className="space-y-4">
      {rows.map((service) => (
        <li key={`${service.service_name}-${service.currency}`}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="min-w-0 text-sm font-medium break-words text-zinc-800 dark:text-zinc-100">{service.service_name}</span>
            <span className="shrink-0 text-sm font-medium text-zinc-900 dark:text-zinc-50">
              <Money amount={service.total} currency={service.currency} />
            </span>
          </div>
          <div className="mt-2 flex items-center gap-2.5">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
              <div
                className="h-full rounded-full transition-[width] duration-500"
                style={{
                  width: `${Math.min(service.percentage_of_revenue, 100)}%`,
                  backgroundColor: colorForService(service.service_name),
                }}
              />
            </div>
            <span className="figure w-9 shrink-0 text-end text-xs text-zinc-500 dark:text-zinc-400">
              {service.percentage_of_revenue.toFixed(0)}%
            </span>
          </div>
          <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
            {t('dashboard.topServicesSaleCount', { count: service.count })}
          </p>
        </li>
      ))}
    </ol>
  )
}
