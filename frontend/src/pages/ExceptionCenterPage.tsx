import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, CircleCheck, FileUp, ListTodo } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useSearchParams } from 'react-router-dom'

import { EmptyState, ErrorState, LoadingState } from '../components/StatusStates'
import { Money } from '../components/Money'
import { Badge, Card, PageHeader } from '../components/ui'
import { formatDate } from '../lib/format'
import { toApiError } from '../services/apiClient'
import { getExceptionCenter } from '../services/exceptionService'
import type { ExceptionCenter } from '../types/exceptions'
import type { Sale } from '../types/sale'
import { buttonClasses, cardClasses, cx } from '../components/ui-classes'

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
    ? { to: `/import-document?saleId=${sale.id}`, label: t('exceptions.importDocument'), icon: FileUp }
    : { to: `/sales/${sale.id}`, label: t('exceptions.reviewSale'), icon: ChevronLeft }

  return (
    <li className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
      <div className="min-w-0 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={category === 'documentFailures' ? 'danger' : 'warning'}>{t(`exceptions.filters.${category}`)}</Badge>
          <Link to={`/sales/${sale.id}`} className="font-semibold break-words text-zinc-900 underline-offset-2 hover:text-brand-700 hover:underline dark:text-zinc-100 dark:hover:text-brand-300">
            {sale.customer_name}
          </Link>
          {selected === 'all' && reasons.length > 1 && <span className="text-xs text-zinc-500 dark:text-zinc-400">{t('exceptions.moreReasons', { count: reasons.length - 1 })}</span>}
        </div>
        <p className="text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{description}</p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{sale.service_name} · <bdi>{formatDate(sale.occurred_at.slice(0, 10), i18n.language)}</bdi></p>
      </div>
      <div className="flex shrink-0 items-center justify-between gap-4 sm:justify-end">
        <span className="text-sm font-medium text-zinc-900 dark:text-zinc-50"><Money amount={sale.gross_amount} currency={sale.currency} /></span>
        <Link to={action.to} className={buttonClasses('secondary', 'sm', 'whitespace-nowrap')}>
          {action.label}
          <action.icon className={`h-3.5 w-3.5 ${action.icon === ChevronLeft ? 'ltr:rotate-180' : ''}`} aria-hidden="true" />
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
  const { data, isPending: isLoading, isFetching, isError, error, refetch } = useQuery({
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
      <PageHeader title={t('exceptions.title')} description={t('exceptions.subtitle')} />

      {/* One control surface: how much is waiting, and the filters that slice it. */}
      <Card className="overflow-hidden">
        <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-4">
          <span className={cx('grid h-11 w-11 shrink-0 place-items-center rounded-full', data.attention_count > 0 ? 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300' : 'bg-success-50 text-success-700 dark:bg-success-500/10 dark:text-success-500')} aria-hidden="true">
            {data.attention_count > 0 ? <ListTodo className="h-5 w-5" /> : <CircleCheck className="h-5 w-5" />}
          </span>
          <div>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">{t('exceptions.totalLabel')}</p>
            <p className="figure text-2xl font-medium text-zinc-900 dark:text-zinc-50">{data.attention_count}</p>
          </div>
        </div>
        <p className="max-w-sm text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">{t('exceptions.totalHint')}</p>
        </div>

      <div role="group" aria-label={t('exceptions.filterLabel')} className="flex flex-wrap gap-2 border-t border-zinc-100 bg-zinc-50/60 px-5 py-3 dark:border-zinc-800 dark:bg-zinc-950/30">
        {(['all', ...CATEGORIES] as Filter[]).map((category) => {
          const active = selected === category
          return (
            <button
              key={category}
              type="button"
              aria-pressed={active}
              onClick={() => setSearchParams({ category })}
              className={cx(
                'inline-flex h-9 items-center gap-2 rounded-full border px-3.5 text-sm font-medium transition-colors',
                active
                  ? 'border-brand-600/30 bg-brand-50 text-brand-800 dark:border-brand-400/30 dark:bg-brand-500/10 dark:text-brand-200'
                  : 'border-zinc-200 bg-white text-zinc-700 hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800',
              )}
            >
              {t(`exceptions.filters.${category}`)}{' '}
              <span className={cx('figure rounded-full px-1.5 text-xs', active ? 'bg-brand-600/10 dark:bg-brand-400/15' : 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400')}>{totals[category]}</span>
            </button>
          )
        })}
      </div>
      </Card>

      <section aria-label={t('exceptions.listLabel')}>
        {visible.length === 0 ? (
          <EmptyState title={t('exceptions.emptyTitle')} description={t('exceptions.emptyDescription')} icon={<CircleCheck className="h-5 w-5 text-success-600 dark:text-success-500" />} />
        ) : (
          <>
            <p className="mb-3 text-sm text-zinc-500 dark:text-zinc-400">{t('exceptions.showingCount', { shown: visible.length, total })}</p>
            <ul className={cx(cardClasses, 'divide-y divide-zinc-100 overflow-hidden dark:divide-zinc-800')}>
              {visible.map((task) => <TaskRow key={task.sale.id} task={task} selected={selected} />)}
            </ul>
            {visible.length < total && (limit < 500 ? (
              <button type="button" onClick={() => setLimit((current) => Math.min(current + 20, 500))} disabled={isFetching} className={buttonClasses('secondary', 'md', 'mt-4')}>
                {isFetching ? t('common.loading') : t('exceptions.loadMore')}
              </button>
            ) : <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">{t('exceptions.resultLimit')}</p>)}
          </>
        )}
      </section>
    </div>
  )
}
