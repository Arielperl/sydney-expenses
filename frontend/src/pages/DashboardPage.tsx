import { useQuery } from '@tanstack/react-query'
import { CalendarRange, CalendarX2, ChevronLeft, Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { DocumentStatusBadge } from '../components/DocumentStatusBadge'
import { FinancialBreakdown } from '../components/dashboard/FinancialBreakdown'
import { NeedsAttentionPanel } from '../components/dashboard/NeedsAttentionPanel'
import { PeriodSummary } from '../components/dashboard/PeriodSummary'
import { PeriodToolbar } from '../components/dashboard/PeriodToolbar'
import { TopServicesList } from '../components/dashboard/TopServicesList'
import { Money } from '../components/Money'
import { RevenueTrendChart } from '../components/RevenueTrendChart'
import { SaleStatusBadge } from '../components/SaleStatusBadge'
import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { Card, CardHeader, PageHeader, SegmentedControl } from '../components/ui'
import { buttonClasses } from '../components/ui-classes'
import { getDashboardStats } from '../services/dashboardService'
import { formatDateTime } from '../lib/format'
import { toApiError } from '../services/apiClient'
import type { CurrencyAmount, DashboardPeriodName } from '../types/dashboard'

// The business's own currency first, then any others alphabetically — matching the backend's ordering.
function currenciesOf(amounts: CurrencyAmount[]): string[] {
  const set = new Set(amounts.map((row) => row.currency))
  return set.size > 0 ? Array.from(set).sort((a, b) => Number(b === 'ILS') - Number(a === 'ILS') || a.localeCompare(b)) : ['ILS']
}

function CurrencyLabel({ currency }: { currency: string }) {
  return <p className="mb-2 text-[11px] font-medium tracking-wider text-zinc-500 dark:text-zinc-400">{currency}</p>
}

export function DashboardPage() {
  const { t, i18n } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const period = (searchParams.get('period') as DashboardPeriodName | null) ?? 'this_month'
  const customStart = searchParams.get('custom_start') ?? ''
  const customEnd = searchParams.get('custom_end') ?? ''
  const [showComparison, setShowComparison] = useState(true)
  const [trendMetric, setTrendMetric] = useState<'gross' | 'net'>('net')
  const [trendCurrencyChoice, setTrendCurrencyChoice] = useState<string | null>(null)

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

  const customRangeInvalid = period === 'custom' && Boolean(customStart && customEnd) && customStart > customEnd
  // An inverted range is treated like an unfinished one: explained here, never sent to the server.
  const customRangeIncomplete = period === 'custom' && (!customStart || !customEnd || customRangeInvalid)

  const { data, isPending: isLoading, isError, error, refetch } = useQuery({
    queryKey: ['dashboard-stats', period, customStart, customEnd],
    queryFn: () => getDashboardStats({ period, customStart, customEnd }),
    enabled: !customRangeIncomplete,
    // Keep the previous period on screen while the next one loads, so figures ease instead of blinking.
    placeholderData: (previous) => previous,
  })

  const trendCurrencies = data
    ? currenciesOf(data.net_revenue_current_period.length > 0 ? data.net_revenue_current_period : data.gross_revenue)
    : []
  const serviceCurrencies = data ? currenciesOf(data.gross_revenue) : []
  const trendCurrency = trendCurrencyChoice && trendCurrencies.includes(trendCurrencyChoice) ? trendCurrencyChoice : trendCurrencies[0]

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('dashboard.title')}
        description={t('dashboard.subtitle')}
        actions={
          <Link to="/add-sale" className={buttonClasses('primary')}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            {t('sales.addSaleManually')}
          </Link>
        }
      />

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

      {customRangeIncomplete && (
        customRangeInvalid
          ? <EmptyState title={t('dashboard.invalidCustomRange')} description={t('dashboard.invalidCustomRangeDescription')} icon={<CalendarX2 className="h-5 w-5" />} />
          : <EmptyState title={t('dashboard.pickCustomRange')} description={t('dashboard.pickCustomRangeDescription')} icon={<CalendarRange className="h-5 w-5" />} />
      )}

      {!customRangeIncomplete && isLoading && <LoadingState label={t('common.loading')} variant="skeleton" />}
      {!customRangeIncomplete && isError && (
        <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />
      )}

      {!customRangeIncomplete && !isLoading && !isError && data && (
        <div className="space-y-6">
          <PeriodSummary data={data} showComparison={showComparison} />

          {/* Main column + side rail on desktop. On phones both columns dissolve (display: contents)
              into one stream, ordered so the actionable panel comes right after the summary. */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3 lg:items-start">
            <div className="max-lg:contents lg:col-span-2 lg:space-y-6">
            <Card className="max-lg:order-2" aria-labelledby="trend-title">
              <CardHeader
                id="trend-title"
                title={t('dashboard.revenueTrend')}
                description={t('dashboard.trendDescription', { granularity: t(`dashboard.granularity.${data.period.trend_granularity}`) })}
                actions={
                  <>
                    {trendCurrencies.length > 1 && (
                      <SegmentedControl
                        label={t('dashboard.trendCurrency')}
                        value={trendCurrency}
                        onChange={setTrendCurrencyChoice}
                        options={trendCurrencies.map((currency) => ({ value: currency, label: currency }))}
                      />
                    )}
                    <SegmentedControl
                      label={t('dashboard.trendMetricLabel')}
                      value={trendMetric}
                      onChange={setTrendMetric}
                      options={(['net', 'gross'] as const).map((option) => ({ value: option, label: t(`dashboard.trendMetric.${option}`) }))}
                    />
                  </>
                }
              />
              <div className="px-3 pt-4 pb-4 sm:px-4">
                <RevenueTrendChart
                  data={data.revenue_trend.filter((point) => point.currency === trendCurrency)}
                  currency={trendCurrency}
                  metric={trendMetric}
                  granularity={data.period.trend_granularity}
                />
              </div>
            </Card>

            <Card className="max-lg:order-3" aria-labelledby="recent-title">
              <CardHeader
                id="recent-title"
                title={t('dashboard.recentSales')}
                actions={
                  <Link to="/sales" className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:text-brand-800 dark:text-brand-300 dark:hover:text-brand-200">
                    {t('dashboard.viewAll')}
                    <ChevronLeft className="h-4 w-4 ltr:rotate-180" aria-hidden="true" />
                  </Link>
                }
              />
              {data.recent_sales.length === 0 ? (
                <div className="px-5 py-10 text-center">
                  <p className="text-sm text-zinc-500 dark:text-zinc-400">{t('dashboard.recentSalesEmpty')}</p>
                  <Link to="/add-sale" className={buttonClasses('secondary', 'md', 'mt-4')}>
                    {t('sales.addSaleManually')}
                  </Link>
                </div>
              ) : (
                <ul className="mt-3 divide-y divide-zinc-100 border-t border-zinc-100 dark:divide-zinc-800 dark:border-zinc-800">
                  {data.recent_sales.map((sale) => (
                    <li key={sale.id}>
                      <Link
                        to={`/sales/${sale.id}`}
                        className="flex flex-col gap-2 px-5 py-3.5 transition-colors hover:bg-zinc-50 sm:flex-row sm:items-center sm:justify-between sm:gap-4 dark:hover:bg-zinc-800/40"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-zinc-900 dark:text-zinc-100" title={sale.customer_name}>{sale.customer_name}</p>
                          <p className="mt-0.5 truncate text-xs text-zinc-500 dark:text-zinc-400">
                            {sale.service_name} · <bdi>{formatDateTime(sale.occurred_at, i18n.language)}</bdi>
                            {sale.payment_method && <> · {t(`paymentMethod.${sale.payment_method}`, sale.payment_method)}</>}
                          </p>
                        </div>
                        <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
                          <SaleStatusBadge status={sale.status} />
                          <DocumentStatusBadge status={sale.document_status} />
                          <span className="min-w-[6.5rem] text-sm font-medium text-zinc-900 sm:text-end dark:text-zinc-50">
                            <Money amount={sale.gross_amount} currency={sale.currency} />
                          </span>
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <FinancialBreakdown
              className="max-lg:order-5"
              grossRevenue={data.gross_revenue}
              vatCollected={data.vat_collected}
              processingFees={data.processing_fees}
              refundsTotal={data.refunds_total}
              netRevenue={data.net_revenue_current_period}
            />
            </div>

            <div className="max-lg:contents lg:space-y-6">
              <NeedsAttentionPanel
                className="max-lg:order-1"
                pendingDocumentsCount={data.pending_documents_count}
                documentFailuresCount={data.document_failures_count}
                incompleteDetailsCount={data.incomplete_details_count}
              />

              <Card className="max-lg:order-4" aria-labelledby="services-title">
                <CardHeader id="services-title" title={t('dashboard.topServices')} description={t('dashboard.topServicesDescription')} />
                <div className="space-y-6 px-5 pt-4 pb-5">
                  {serviceCurrencies.map((currency) => (
                    <div key={currency}>
                      {serviceCurrencies.length > 1 && <CurrencyLabel currency={currency} />}
                      <TopServicesList services={data.top_services} currency={currency} />
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
