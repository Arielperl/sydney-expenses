import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router-dom'

import { DocumentStatusBadge } from '../components/DocumentStatusBadge'
import { SaleStatusBadge } from '../components/SaleStatusBadge'
import { ErrorState, LoadingState } from '../components/StatusStates'
import { formatCurrency, formatDate } from '../lib/format'
import { toApiError } from '../services/apiClient'
import { getExceptionCenter } from '../services/exceptionService'
import type { Sale } from '../types/sale'

function SaleRow({ sale, action }: { sale: Sale; action?: ReactNode }) {
  const { i18n } = useTranslation()
  return (
    <li className="flex items-center justify-between gap-4 px-4 py-3">
      <div className="min-w-0">
        <p className="truncate font-medium text-zinc-900 dark:text-zinc-100">{sale.customer_name}</p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          {sale.service_name} · {formatDate(sale.occurred_at.slice(0, 10), i18n.language)}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <SaleStatusBadge status={sale.status} />
        <DocumentStatusBadge status={sale.document_status} />
        <span className="font-medium tabular-nums text-zinc-900 dark:text-zinc-100">
          {formatCurrency(sale.gross_amount, sale.currency, i18n.language)}
        </span>
        {action}
      </div>
    </li>
  )
}

function SaleSection({
  id,
  title,
  emptyLabel,
  sales,
  total,
  onLoadMore,
  isLoadingMore,
  action,
}: {
  id: string
  title: string
  emptyLabel: string
  sales: Sale[]
  total: number
  onLoadMore: () => void
  isLoadingMore: boolean
  action?: (sale: Sale) => ReactNode
}) {
  const { t } = useTranslation()
  return (
    <section id={id} className="scroll-mt-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{title}</h2>
        {total > 0 && (
          <span className="text-xs text-zinc-500 dark:text-zinc-400">
            {t('exceptions.showingCount', { shown: sales.length, total })}
          </span>
        )}
      </div>
      {sales.length === 0 ? (
        <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">{emptyLabel}</p>
      ) : (
        <>
          <ul className="mt-3 divide-y divide-zinc-100 rounded-2xl border border-zinc-200 bg-white dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-900">
            {sales.map((sale) => (
              <SaleRow key={sale.id} sale={sale} action={action?.(sale)} />
            ))}
          </ul>
          {sales.length < total && (
            <button
              type="button"
              onClick={onLoadMore}
              disabled={isLoadingMore}
              className="mt-3 rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:cursor-wait disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
            >
              {isLoadingMore ? t('common.loading') : t('exceptions.loadMore')}
            </button>
          )}
        </>
      )}
    </section>
  )
}

export function ExceptionCenterPage() {
  const { t } = useTranslation()
  const location = useLocation()
  const [limit, setLimit] = useState(20)
  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['exception-center', limit],
    queryFn: () => getExceptionCenter(limit),
    placeholderData: (previousData) => previousData,
  })

  const loadMore = () => setLimit((current) => Math.min(current + 20, 500))

  // React Router doesn't scroll to a `#hash` on its own client-side
  // navigations (only real browser navigation does that) — this is what
  // makes a dashboard link like `/exceptions#document-failures` actually
  // land on the right section once the page's own data has rendered.
  useEffect(() => {
    if (!location.hash || !data) return
    const target = document.querySelector(location.hash)
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [location.hash, data])

  if (isLoading) return <LoadingState label={t('common.loading')} />
  if (isError) return <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />
  if (!data) return null

  const importLink = (sale: Sale) => (
    <Link
      to={`/import-document?saleId=${sale.id}`}
      className="whitespace-nowrap rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
    >
      {t('exceptions.importDocument')}
    </Link>
  )

  const editLink = () => (
    <Link
      to="/sales"
      className="whitespace-nowrap rounded-md border border-zinc-300 px-2.5 py-1 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
    >
      {t('exceptions.editInSales')}
    </Link>
  )

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{t('exceptions.title')}</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('exceptions.subtitle')}</p>
      </div>

      <SaleSection
        id="pending-documents"
        title={t('exceptions.sections.pendingDocuments')}
        emptyLabel={t('exceptions.emptyPendingDocuments')}
        sales={data.pending_documents}
        total={data.pending_documents_count}
        onLoadMore={loadMore}
        isLoadingMore={isFetching}
        action={importLink}
      />

      <SaleSection
        id="document-failures"
        title={t('exceptions.sections.documentFailures')}
        emptyLabel={t('exceptions.emptyDocumentFailures')}
        sales={data.document_failures}
        total={data.document_failures_count}
        onLoadMore={loadMore}
        isLoadingMore={isFetching}
        action={importLink}
      />

      <SaleSection
        id="refunds-needing-attention"
        title={t('exceptions.sections.refundsNeedingAttention')}
        emptyLabel={t('exceptions.emptyRefunds')}
        sales={data.refunds_needing_attention}
        total={data.refunds_needing_attention_count}
        onLoadMore={loadMore}
        isLoadingMore={isFetching}
      />

      <SaleSection
        id="incomplete-details"
        title={t('exceptions.sections.incompleteDetails')}
        emptyLabel={t('exceptions.emptyIncompleteDetails')}
        sales={data.incomplete_details}
        total={data.incomplete_details_count}
        onLoadMore={loadMore}
        isLoadingMore={isFetching}
        action={editLink}
      />
    </div>
  )
}
