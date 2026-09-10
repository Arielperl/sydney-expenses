import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { StatCard } from '../components/StatCard'
import { TopServicesChart } from '../components/TopServicesChart'
import { RevenueTrendChart } from '../components/RevenueTrendChart'
import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { ServiceBadge } from '../components/ServiceBadge'
import { getDashboardStats } from '../services/dashboardService'
import { formatCurrency, formatDate } from '../lib/format'
import { toApiError } from '../services/apiClient'
import type { RevenueTrendPoint, TopService } from '../types/dashboard'

function CountStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900">
      <p className="text-sm font-medium text-stone-500 dark:text-stone-400">{label}</p>
      <p className="mt-2 text-3xl font-semibold tracking-tight tabular-nums text-stone-900 dark:text-stone-100">
        {value}
      </p>
    </div>
  )
}

function currenciesOf<T extends { currency: string }>(rows: T[]): string[] {
  return Array.from(new Set(rows.map((row) => row.currency))).sort()
}

export function DashboardPage() {
  const { t, i18n } = useTranslation()
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
  })

  if (isLoading) return <LoadingState label={t('common.loading')} />

  if (isError) {
    return <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />
  }

  if (!data) return null

  const hasAnySales = data.recent_sales.length > 0 || data.top_services.length > 0
  const topServicesByCurrency = currenciesOf<TopService>(data.top_services)
  const revenueTrendByCurrency = currenciesOf<RevenueTrendPoint>(data.revenue_trend)

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('dashboard.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('dashboard.subtitle')}</p>
      </div>

      {!hasAnySales ? (
        <EmptyState
          title={t('dashboard.emptyTitle')}
          description={t('dashboard.emptyDescription')}
          action={
            <div className="flex justify-center gap-3">
              <Link
                to="/add-sale"
                className="rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
              >
                {t('sales.addSaleManually')}
              </Link>
              <Link
                to="/imports"
                className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200 dark:hover:bg-stone-700"
              >
                {t('nav.imports')}
              </Link>
            </div>
          }
        />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <StatCard
              label={t('dashboard.revenueThisMonth')}
              amounts={data.net_revenue_this_month}
              changePercentByCurrency={data.percentage_change}
            />
            <StatCard label={t('dashboard.revenueLastMonth')} amounts={data.net_revenue_previous_month} />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <CountStat label={t('dashboard.successfulSales')} value={data.successful_sales_count} />
            <StatCard label={t('dashboard.averageTransactionValue')} amounts={data.average_transaction_value} />
            <StatCard label={t('dashboard.grossRevenue')} amounts={data.gross_revenue} />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <StatCard label={t('dashboard.vatCollected')} amounts={data.vat_collected} />
            <StatCard label={t('dashboard.processingFees')} amounts={data.processing_fees} />
          </div>

          <div>
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">
                {t('dashboard.exceptionsOverview')}
              </h2>
              <Link
                to="/exceptions"
                className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
              >
                {t('dashboard.viewAll')}
              </Link>
            </div>
            <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <StatCard
                label={t('dashboard.pendingDocuments', { count: data.pending_documents_count })}
                amounts={data.pending_documents_total}
              />
              <CountStat label={t('dashboard.documentFailures')} value={data.document_failures_count} />
              <CountStat label={t('dashboard.failedPayments')} value={data.failed_payments_count} />
            </div>
            {data.refunds_count > 0 && (
              <div className="mt-4">
                <StatCard
                  label={t('dashboard.refunds', { count: data.refunds_count })}
                  amounts={data.refunds_total}
                />
              </div>
            )}
          </div>

          {data.top_services.length > 0 && (
            <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900">
              <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{t('dashboard.topServices')}</h2>
              <p className="text-sm text-stone-500 dark:text-stone-400">{t('dashboard.currentMonth')}</p>
              <div className="mt-4 space-y-6">
                {topServicesByCurrency.map((currency) => (
                  <div key={currency}>
                    {topServicesByCurrency.length > 1 && (
                      <p className="mb-2 text-xs font-semibold tracking-wide text-stone-400 uppercase dark:text-stone-500">
                        {currency}
                      </p>
                    )}
                    <TopServicesChart
                      data={data.top_services.filter((row) => row.currency === currency)}
                      currency={currency}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-2xl border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900">
            <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{t('dashboard.revenueTrend')}</h2>
            <div className="mt-4 space-y-6">
              {revenueTrendByCurrency.length === 0 && <RevenueTrendChart data={[]} currency="ILS" />}
              {revenueTrendByCurrency.map((currency) => (
                <div key={currency}>
                  {revenueTrendByCurrency.length > 1 && (
                    <p className="mb-2 text-xs font-semibold tracking-wide text-stone-400 uppercase dark:text-stone-500">
                      {currency}
                    </p>
                  )}
                  <RevenueTrendChart
                    data={data.revenue_trend.filter((row) => row.currency === currency)}
                    currency={currency}
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-stone-200 bg-white shadow-sm dark:border-stone-800 dark:bg-stone-900">
            <div className="flex items-center justify-between border-b border-stone-100 px-5 py-4 dark:border-stone-800">
              <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{t('dashboard.recentSales')}</h2>
              <Link to="/sales" className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300">
                {t('dashboard.viewAll')}
              </Link>
            </div>
            <ul className="divide-y divide-stone-100 dark:divide-stone-800">
              {data.recent_sales.map((sale) => (
                <li key={sale.id} className="flex items-center justify-between gap-4 px-5 py-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium text-stone-900 dark:text-stone-100">{sale.customer_name}</p>
                    <p className="text-xs text-stone-500 dark:text-stone-400">
                      {formatDate(sale.occurred_at.slice(0, 10), i18n.language)} · {t(`saleSource.${sale.source}`)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <ServiceBadge serviceName={sale.service_name} />
                    <span className="font-medium tabular-nums text-stone-900 dark:text-stone-100">
                      {formatCurrency(sale.gross_amount, sale.currency, i18n.language)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}
    </div>
  )
}
