import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { DocumentStatusBadge } from '../components/DocumentStatusBadge'
import { FinancialBreakdown } from '../components/dashboard/FinancialBreakdown'
import { NeedsAttentionPanel } from '../components/dashboard/NeedsAttentionPanel'
import { PeriodToolbar } from '../components/dashboard/PeriodToolbar'
import { PrimaryMetricCard } from '../components/dashboard/PrimaryMetricCard'
import { TopServicesList } from '../components/dashboard/TopServicesList'
import { RevenueTrendChart } from '../components/RevenueTrendChart'
import { SaleStatusBadge } from '../components/SaleStatusBadge'
import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { getDashboardStats } from '../services/dashboardService'
import { formatCurrency, formatDateTime } from '../lib/format'
import { toApiError } from '../services/apiClient'
import type { CurrencyAmount, DashboardPeriodName } from '../types/dashboard'

function currenciesOf(amounts: CurrencyAmount[]): string[] {
  const set = new Set(amounts.map((row) => row.currency))
  return set.size > 0 ? Array.from(set).sort() : ['ILS']
}

function SecondaryStat({
  label,
  amounts,
  plainValue,
  to,
}: {
  label: string
  amounts?: CurrencyAmount[]
  plainValue?: number
  to?: string
}) {
  const { i18n } = useTranslation()
  const rows = amounts && amounts.length > 0 ? amounts : amounts ? [{ currency: 'ILS', amount: 0 }] : []
  const content = (
    <>
      <p className="text-sm font-medium text-zinc-500 dark:text-zinc-400">{label}</p>
      {plainValue !== undefined ? (
        <p className="mt-1 text-2xl font-semibold tracking-tight tabular-nums text-zinc-900 dark:text-zinc-100">
          {new Intl.NumberFormat(i18n.language).format(plainValue)}
        </p>
      ) : (
        <div className={rows.length > 1 ? 'mt-2 space-y-1' : undefined}>
          {rows.map((row) => (
            <p
              key={row.currency}
              className="mt-1 text-2xl font-semibold tracking-tight tabular-nums text-zinc-900 dark:text-zinc-100"
            >
              {formatCurrency(row.amount, row.currency, i18n.language)}
              {rows.length > 1 && <span className="ms-1 text-xs font-medium text-zinc-400">{row.currency}</span>}
            </p>
          ))}
        </div>
      )}
    </>
  )
  const className =
    'block rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900' +
    (to ? ' transition-colors hover:border-brand-300 dark:hover:border-brand-700' : '')

  if (to) {
    return (
      <Link to={to} className={className}>
        {content}
      </Link>
    )
  }
  return <div className={className}>{content}</div>
}

export function DashboardPage() {
  const { t, i18n } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const period = (searchParams.get('period') as DashboardPeriodName | null) ?? 'this_month'
  const customStart = searchParams.get('custom_start') ?? ''
  const customEnd = searchParams.get('custom_end') ?? ''
  const [showComparison, setShowComparison] = useState(true)
  const [trendMetric, setTrendMetric] = useState<'gross' | 'net'>('net')

  function updateParams(updates: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams)
    for (const [key, value] of Object.entries(updates)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setSearchParams(next, { replace: true })
  }

  function handlePeriodChange(next: DashboardPeriodName) {
    updateParams({ period: next, ...(next === 'custom' ? {} : { custom_start: null, custom_end: null }) })
  }

  const customRangeIncomplete = period === 'custom' && (!customStart || !customEnd)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['dashboard-stats', period, customStart, customEnd],
    queryFn: () => getDashboardStats({ period, customStart, customEnd }),
    enabled: !customRangeIncomplete,
  })

  const toolbar = (
    <PeriodToolbar
      period={period}
      onPeriodChange={handlePeriodChange}
      customStart={customStart}
      customEnd={customEnd}
      onCustomStartChange={(value) => updateParams({ custom_start: value })}
      onCustomEndChange={(value) => updateParams({ custom_end: value })}
      showComparison={showComparison}
      onToggleComparison={setShowComparison}
    />
  )

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{t('dashboard.title')}</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('dashboard.subtitle')}</p>
      </div>

      {toolbar}

      {customRangeIncomplete && (
        <EmptyState title={t('dashboard.pickCustomRange')} description={t('dashboard.pickCustomRangeDescription')} />
      )}

      {!customRangeIncomplete && isLoading && <LoadingState label={t('common.loading')} />}
      {!customRangeIncomplete && isError && (
        <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />
      )}

      {!customRangeIncomplete && !isLoading && !isError && data && (
        <div className="space-y-5">
          {/* Primary metrics */}
          <div className="space-y-4">
            <PrimaryMetricCard
              label={t('dashboard.netRevenue')}
              explanation={t('dashboard.netRevenueExplanation')}
              amounts={data.net_revenue_current_period}
              comparisons={data.comparison}
              showComparison={showComparison}
            />
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <SecondaryStat
                label={t('dashboard.grossRevenue')}
                amounts={data.gross_revenue}
                to={`/sales?date_from=${data.period.start_date}&date_to=${data.period.end_date}`}
              />
              <SecondaryStat label={t('dashboard.successfulSalesCount')} plainValue={data.successful_sales_count} />
              <SecondaryStat label={t('dashboard.averageTransactionValue')} amounts={data.average_transaction_value} />
            </div>
          </div>

          {/* Revenue trend + needs attention */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm lg:col-span-2 dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{t('dashboard.revenueTrend')}</h2>
                <div className="inline-flex rounded-lg border border-zinc-200 p-0.5 text-xs font-medium dark:border-zinc-700">
                  {(['gross', 'net'] as const).map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setTrendMetric(option)}
                      className={[
                        'rounded-md px-2.5 py-1 transition-colors',
                        trendMetric === option
                          ? 'bg-brand-600 text-white'
                          : 'text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100',
                      ].join(' ')}
                    >
                      {t(`dashboard.trendMetric.${option}`)}
                    </button>
                  ))}
                </div>
              </div>
              <div className="mt-4 space-y-6">
                {currenciesOf(data.net_revenue_current_period.length > 0 ? data.net_revenue_current_period : data.gross_revenue).map(
                  (currency) => {
                    const points = data.revenue_trend.filter((point) => point.currency === currency)
                    const showLabel =
                      currenciesOf(data.net_revenue_current_period.length > 0 ? data.net_revenue_current_period : data.gross_revenue).length > 1
                    return (
                      <div key={currency}>
                        {showLabel && (
                          <p className="mb-2 text-xs font-semibold tracking-wide text-zinc-400 uppercase dark:text-zinc-500">
                            {currency}
                          </p>
                        )}
                        <RevenueTrendChart
                          data={points}
                          currency={currency}
                          metric={trendMetric}
                          granularity={data.period.trend_granularity}
                        />
                      </div>
                    )
                  },
                )}
              </div>
            </div>

            <NeedsAttentionPanel
              pendingDocumentsCount={data.pending_documents_count}
              documentFailuresCount={data.document_failures_count}
              failedPaymentsCount={data.failed_payments_count}
              refundsNeedingAttentionCount={data.refunds_needing_attention_count}
              incompleteDetailsCount={data.incomplete_details_count}
            />
          </div>

          {/* Recent sales + top services */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="rounded-xl border border-zinc-200 bg-white shadow-sm lg:col-span-2 dark:border-zinc-800 dark:bg-zinc-900">
              <div className="flex items-center justify-between border-b border-zinc-100 px-5 py-4 dark:border-zinc-800">
                <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{t('dashboard.recentSales')}</h2>
                <Link to="/sales" className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300">
                  {t('dashboard.viewAll')}
                </Link>
              </div>
              {data.recent_sales.length === 0 ? (
                <div className="px-5 py-10 text-center">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('dashboard.recentSalesEmpty')}</p>
                  <Link
                    to="/add-sale"
                    className="mt-3 inline-flex rounded-md bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
                  >
                    {t('sales.addSaleManually')}
                  </Link>
                </div>
              ) : (
                <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
                  {data.recent_sales.map((sale) => (
                    <li key={sale.id}>
                      <Link
                        to={`/sales/${sale.id}`}
                        className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                      >
                        <div className="min-w-0">
                          <p className="truncate font-medium text-zinc-900 dark:text-zinc-100">{sale.customer_name}</p>
                          <p className="truncate text-xs text-zinc-500 dark:text-zinc-400">
                            {sale.service_name} · {formatDateTime(sale.occurred_at, i18n.language)}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          {sale.payment_method && (
                            <span className="hidden text-xs text-zinc-400 sm:inline dark:text-zinc-500">
                              {t(`paymentMethod.${sale.payment_method}`, sale.payment_method)}
                            </span>
                          )}
                          <SaleStatusBadge status={sale.status} />
                          <DocumentStatusBadge status={sale.document_status} />
                          <span className="font-medium tabular-nums text-zinc-900 dark:text-zinc-100">
                            {formatCurrency(sale.gross_amount, sale.currency, i18n.language)}
                          </span>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{t('dashboard.topServices')}</h2>
              <div className="mt-4 space-y-6">
                {currenciesOf(data.gross_revenue).map((currency) => (
                  <div key={currency}>
                    {currenciesOf(data.gross_revenue).length > 1 && (
                      <p className="mb-2 text-xs font-semibold tracking-wide text-zinc-400 uppercase dark:text-zinc-500">
                        {currency}
                      </p>
                    )}
                    <TopServicesList services={data.top_services} currency={currency} />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <FinancialBreakdown
            grossRevenue={data.gross_revenue}
            vatCollected={data.vat_collected}
            processingFees={data.processing_fees}
            refundsTotal={data.refunds_total}
            netRevenue={data.net_revenue_current_period}
          />
        </div>
      )}
    </div>
  )
}
