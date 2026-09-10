import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

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
        <p className="truncate font-medium text-stone-900 dark:text-stone-100">{sale.customer_name}</p>
        <p className="text-xs text-stone-500 dark:text-stone-400">
          {sale.service_name} · {formatDate(sale.occurred_at.slice(0, 10), i18n.language)}
        </p>
      </div>
      <div className="flex items-center gap-3">
        <SaleStatusBadge status={sale.status} />
        <DocumentStatusBadge status={sale.document_status} />
        <span className="font-medium tabular-nums text-stone-900 dark:text-stone-100">
          {formatCurrency(sale.gross_amount, sale.currency, i18n.language)}
        </span>
        {action}
      </div>
    </li>
  )
}

function SaleSection({
  title,
  emptyLabel,
  sales,
  action,
}: {
  title: string
  emptyLabel: string
  sales: Sale[]
  action?: (sale: Sale) => ReactNode
}) {
  return (
    <section>
      <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">{title}</h2>
      {sales.length === 0 ? (
        <p className="mt-2 text-sm text-stone-500 dark:text-stone-400">{emptyLabel}</p>
      ) : (
        <ul className="mt-3 divide-y divide-stone-100 rounded-2xl border border-stone-200 bg-white dark:divide-stone-800 dark:border-stone-800 dark:bg-stone-900">
          {sales.map((sale) => (
            <SaleRow key={sale.id} sale={sale} action={action?.(sale)} />
          ))}
        </ul>
      )}
    </section>
  )
}

export function ExceptionCenterPage() {
  const { t } = useTranslation()
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['exception-center'],
    queryFn: getExceptionCenter,
  })

  if (isLoading) return <LoadingState label={t('common.loading')} />
  if (isError) return <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />
  if (!data) return null

  const importLink = (sale: Sale) => (
    <Link
      to={`/import-document?saleId=${sale.id}`}
      className="whitespace-nowrap rounded-md border border-stone-300 px-2.5 py-1 text-xs font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
    >
      {t('exceptions.importDocument')}
    </Link>
  )

  const editLink = () => (
    <Link
      to="/sales"
      className="whitespace-nowrap rounded-md border border-stone-300 px-2.5 py-1 text-xs font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-700 dark:text-stone-200 dark:hover:bg-stone-800"
    >
      {t('exceptions.editInSales')}
    </Link>
  )

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-stone-900 dark:text-stone-100">{t('exceptions.title')}</h1>
        <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{t('exceptions.subtitle')}</p>
      </div>

      <SaleSection
        title={t('exceptions.sections.pendingDocuments')}
        emptyLabel={t('exceptions.emptyPendingDocuments')}
        sales={data.pending_documents}
        action={importLink}
      />

      <SaleSection
        title={t('exceptions.sections.documentFailures')}
        emptyLabel={t('exceptions.emptyDocumentFailures')}
        sales={data.document_failures}
        action={importLink}
      />

      <SaleSection
        title={t('exceptions.sections.refundsNeedingAttention')}
        emptyLabel={t('exceptions.emptyRefunds')}
        sales={data.refunds_needing_attention}
      />

      <SaleSection
        title={t('exceptions.sections.incompleteDetails')}
        emptyLabel={t('exceptions.emptyIncompleteDetails')}
        sales={data.incomplete_details}
        action={editLink}
      />
    </div>
  )
}
