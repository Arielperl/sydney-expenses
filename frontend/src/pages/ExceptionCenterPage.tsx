import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useSearchParams } from 'react-router-dom'

import { ErrorState, LoadingState } from '../components/StatusStates'
import { formatCurrency, formatDate } from '../lib/format'
import { toApiError } from '../services/apiClient'
import { getExceptionCenter } from '../services/exceptionService'
import type { ExceptionCenter } from '../types/exceptions'
import type { Sale } from '../types/sale'

type Category = 'documentFailures' | 'pendingDocuments' | 'incompleteDetails'
type Filter = 'all' | Category
type Task = { sale: Sale; reasons: Category[] }

const CATEGORIES: Category[] = ['documentFailures', 'pendingDocuments', 'incompleteDetails']
const HASH_FILTERS: Record<string, Filter> = {
  '#document-failures': 'documentFailures',
  '#pending-documents': 'pendingDocuments',
  '#incomplete-details': 'incompleteDetails',
}

function tasksFromResponse(data: ExceptionCenter): Task[] {
  const tasks = new Map<string, Task>()
  const groups: Record<Category, Sale[]> = {
    documentFailures: data.document_failures,
    pendingDocuments: data.pending_documents,
    incompleteDetails: data.incomplete_details,
  }
  for (const category of CATEGORIES) {
    for (const sale of groups[category]) {
      const existing = tasks.get(sale.id)
      if (existing) existing.reasons.push(category)
      else tasks.set(sale.id, { sale, reasons: [category] })
    }
  }
  return [...tasks.values()].sort((a, b) => {
    const severity = CATEGORIES.indexOf(a.reasons[0]) - CATEGORIES.indexOf(b.reasons[0])
    return severity || b.sale.occurred_at.localeCompare(a.sale.occurred_at)
  })
}

function TaskRow({ task, selected }: { task: Task; selected: Filter }) {
  const { t, i18n } = useTranslation()
  const { sale, reasons } = task
  const category = selected === 'all' ? reasons[0] : selected
  const isAutomatic = category === 'documentFailures' && sale.document_status === 'waiting_automatic'
  const description = isAutomatic
    ? t('exceptions.reasons.automaticDocumentLate')
    : t(`exceptions.reasons.${category}`)
  const action = category === 'pendingDocuments'
    ? { to: `/import-document?saleId=${sale.id}`, label: t('exceptions.importDocument') }
    : { to: `/sales/${sale.id}`, label: t('exceptions.reviewSale') }

  return (
    <li className="flex flex-col gap-3 border-b border-zinc-100 p-4 last:border-0 sm:flex-row sm:items-center sm:justify-between dark:border-zinc-800">
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${category === 'documentFailures' ? 'bg-danger-500/10 text-danger-700 dark:text-danger-400' : 'bg-amber-500/10 text-amber-800 dark:text-amber-300'}`}>
            {t(`exceptions.filters.${category}`)}
          </span>
          <Link to={`/sales/${sale.id}`} className="font-semibold text-zinc-900 hover:text-brand-700 dark:text-zinc-100 dark:hover:text-brand-400">
            {sale.customer_name}
          </Link>
          {selected === 'all' && reasons.length > 1 && <span className="text-xs text-zinc-500 dark:text-zinc-400">{t('exceptions.moreReasons', { count: reasons.length - 1 })}</span>}
        </div>
        <p className="text-sm text-zinc-600 dark:text-zinc-300">{description}</p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{sale.service_name} · {formatDate(sale.occurred_at.slice(0, 10), i18n.language)}</p>
      </div>
      <div className="flex shrink-0 items-center justify-between gap-3 sm:justify-end">
        <span className="font-semibold tabular-nums text-zinc-900 dark:text-zinc-100">{formatCurrency(sale.gross_amount, sale.currency, i18n.language)}</span>
        <Link to={action.to} className="whitespace-nowrap rounded-lg border border-zinc-300 px-3 py-1.5 text-sm font-medium text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800">
          {action.label}
        </Link>
      </div>
    </li>
  )
}

export function ExceptionCenterPage() {
  const { t } = useTranslation()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [limit, setLimit] = useState(20)
  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ['exception-center', limit],
    queryFn: () => getExceptionCenter(limit),
    placeholderData: (previousData) => previousData,
  })

  if (isLoading) return <LoadingState label={t('common.loading')} />
  if (isError) return <ErrorState message={toApiError(error).message} onRetry={() => refetch()} />
  if (!data) return null

  const requested = searchParams.get('category')
  const selected: Filter = requested === 'all' || CATEGORIES.includes(requested as Category)
    ? requested as Filter
    : HASH_FILTERS[location.hash] ?? 'all'
  const tasks = tasksFromResponse(data)
  const visible = selected === 'all' ? tasks : tasks.filter((task) => task.reasons.includes(selected))
  const totals: Record<Filter, number> = {
    all: data.attention_count,
    documentFailures: data.document_failures_count,
    pendingDocuments: data.pending_documents_count,
    incompleteDetails: data.incomplete_details_count,
  }
  const total = totals[selected]

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-100">{t('exceptions.title')}</h1>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('exceptions.subtitle')}</p>
      </div>

      <div className="rounded-2xl border border-zinc-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <p className="text-xs font-medium text-zinc-500 dark:text-zinc-400">{t('exceptions.totalLabel')}</p>
        <p className="mt-1 text-3xl font-semibold tabular-nums text-zinc-900 dark:text-zinc-100">{data.attention_count}</p>
        <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('exceptions.totalHint')}</p>
      </div>

      <div role="group" aria-label={t('exceptions.filterLabel')} className="flex flex-wrap gap-2">
        {(['all', ...CATEGORIES] as Filter[]).map((category) => (
          <button
            key={category}
            type="button"
            aria-pressed={selected === category}
            onClick={() => setSearchParams({ category })}
            className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${selected === category ? 'border-brand-600 bg-brand-600 text-white' : 'border-zinc-200 bg-white text-zinc-700 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800'}`}
          >
            {t(`exceptions.filters.${category}`)} <span className="ms-1 tabular-nums opacity-75">{totals[category]}</span>
          </button>
        ))}
      </div>

      <section aria-label={t('exceptions.listLabel')}>
        {visible.length === 0 ? (
          <div className="rounded-2xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-900">
            <p className="font-medium text-zinc-900 dark:text-zinc-100">{t('exceptions.emptyTitle')}</p>
            <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('exceptions.emptyDescription')}</p>
          </div>
        ) : (
          <>
            <p className="mb-3 text-sm text-zinc-500 dark:text-zinc-400">{t('exceptions.showingCount', { shown: visible.length, total })}</p>
            <ul className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
              {visible.map((task) => <TaskRow key={task.sale.id} task={task} selected={selected} />)}
            </ul>
            {visible.length < total && (limit < 500 ? (
              <button type="button" onClick={() => setLimit((current) => Math.min(current + 20, 500))} disabled={isFetching} className="mt-4 rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50 disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800">
                {isFetching ? t('common.loading') : t('exceptions.loadMore')}
              </button>
            ) : <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">{t('exceptions.resultLimit')}</p>)}
          </>
        )}
      </section>
    </div>
  )
}
