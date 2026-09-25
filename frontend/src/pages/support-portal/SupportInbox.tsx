import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Inbox, RotateCcw, Search } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { inputClasses } from '../../components/FormField'
import { EmptyState, ErrorState } from '../../components/StatusStates'
import { SupportConversationDialog } from '../../components/SupportConversationDialog'
import { SupportTicketList, SupportTicketListSkeleton } from '../../components/support/SupportTicketList'
import { providerLabel, sortTickets } from '../../lib/support'
import { Card, SegmentedControl } from '../../components/ui'
import { buttonClasses, cx } from '../../components/ui-classes'
import { useNow } from '../../hooks/useNow'
import { listStaffSupportRequests, setSupportRequestStatus, type SupportRequest } from '../../services/supportService'

type Filter = 'all' | 'open' | 'resolved'

function matches(request: SupportRequest, query: string): boolean {
  if (!query) return true
  const haystack = [request.business_name, request.requester_email, request.subject, request.provider, request.provider && providerLabel(request.provider)]
  return haystack.some((value) => value?.toLocaleLowerCase().includes(query))
}

export function SupportInbox() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const now = useNow()
  const [filter, setFilter] = useState<Filter>('open')
  const [search, setSearch] = useState('')
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null)

  const requests = useQuery({
    queryKey: ['staff-requests'],
    queryFn: listStaffSupportRequests,
    refetchInterval: selectedRequestId ? 3_000 : 15_000,
    refetchOnWindowFocus: 'always',
  })
  const changeStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: SupportRequest['status'] }) => setSupportRequestStatus(id, status),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['staff-requests'] }),
  })

  const all = sortTickets(requests.data ?? [])
  const openCount = all.filter((item) => item.status === 'open').length
  const counts: Record<Filter, number> = { all: all.length, open: openCount, resolved: all.length - openCount }
  const query = search.trim().toLocaleLowerCase()
  const visible = all.filter((item) => (filter === 'all' || item.status === filter) && matches(item, query))
  const selectedRequest = all.find((item) => item.id === selectedRequestId)

  function statusAction(request: SupportRequest, inHeader = false) {
    const open = request.status === 'open'
    const pending = changeStatus.isPending && changeStatus.variables?.id === request.id
    const Icon = open ? CheckCircle2 : RotateCcw
    return (
      <button
        type="button"
        disabled={pending}
        onClick={() => changeStatus.mutate({ id: request.id, status: open ? 'resolved' : 'open' })}
        aria-label={inHeader
          ? t(open ? 'supportPortal.inbox.resolve' : 'supportPortal.inbox.reopen')
          : t(open ? 'supportPortal.inbox.resolveFor' : 'supportPortal.inbox.reopenFor', { subject: request.subject })}
        title={inHeader ? undefined : t(open ? 'supportPortal.inbox.resolve' : 'supportPortal.inbox.reopen')}
        className={inHeader ? buttonClasses('secondary', 'md') : cx(buttonClasses('ghost', 'sm'), 'h-10 w-10 px-0 lg:w-auto lg:px-3')}
      >
        <Icon className="h-4 w-4" aria-hidden="true" />
        <span className={inHeader ? 'hidden sm:inline' : 'hidden lg:inline'}>{t(open ? 'supportPortal.inbox.resolve' : 'supportPortal.inbox.reopen')}</span>
      </button>
    )
  }

  return (
    <section aria-labelledby="inbox-heading" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 id="inbox-heading" className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t('supportPortal.inbox.title')}</h2>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">{t('supportPortal.inbox.description')}</p>
        </div>
        {requests.data && (
          <p
            className={cx(
              'inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset',
              openCount > 0
                ? 'bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/25'
                : 'bg-zinc-100 text-zinc-600 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:ring-zinc-700',
            )}
          >
            <span className={cx('h-2 w-2 rounded-full', openCount > 0 ? 'bg-amber-500' : 'bg-zinc-400')} aria-hidden="true" />
            {openCount > 0 ? t('supportPortal.inbox.openCount', { count: openCount }) : t('supportPortal.inbox.noneOpen')}
          </p>
        )}
      </div>

      {requests.isError && !requests.data ? (
        <ErrorState message={t('support.loadError')} onRetry={() => void requests.refetch()} />
      ) : requests.data?.length === 0 ? (
        <EmptyState title={t('supportPortal.inbox.emptyTitle')} description={t('supportPortal.inbox.emptyDescription')} icon={<Inbox className="h-5 w-5" />} />
      ) : (
        <Card className="overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-zinc-100 p-3 sm:flex-row sm:items-center sm:justify-between sm:px-4 dark:border-zinc-800">
            <SegmentedControl
              label={t('support.filterLabel')}
              value={filter}
              onChange={setFilter}
              options={(['all', 'open', 'resolved'] as const).map((value) => ({
                value,
                label: <>{t(`support.filters.${value}`)} <span className="figure text-zinc-500 dark:text-zinc-400">{counts[value]}</span></>,
              }))}
            />
            <div className="relative sm:w-80">
              <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-400" aria-hidden="true" />
              <label htmlFor="support-inbox-search" className="sr-only">{t('supportPortal.inbox.searchLabel')}</label>
              <input
                id="support-inbox-search"
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t('supportPortal.inbox.searchPlaceholder')}
                className={cx(inputClasses, 'ps-9')}
              />
            </div>
          </div>
          {requests.isPending ? (
            <SupportTicketListSkeleton rows={4} label={t('support.loading')} />
          ) : visible.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{t('supportPortal.inbox.noMatchesTitle')}</p>
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('supportPortal.inbox.noMatchesDescription')}</p>
              <button type="button" className={buttonClasses('secondary', 'sm', 'mt-4')} onClick={() => { setSearch(''); setFilter('all') }}>
                {t('supportPortal.inbox.clearFilters')}
              </button>
            </div>
          ) : (
            <>
              <p className="sr-only" role="status">{t('supportPortal.inbox.resultCount', { count: visible.length })}</p>
              <SupportTicketList requests={visible} now={now} staff onOpen={setSelectedRequestId} renderActions={(request) => statusAction(request)} />
            </>
          )}
        </Card>
      )}
      {changeStatus.isError && <p role="alert" className="text-sm text-danger-700 dark:text-danger-500">{t('supportPortal.inbox.statusError')}</p>}

      {selectedRequest && (
        <SupportConversationDialog
          request={selectedRequest}
          staff
          onClose={() => setSelectedRequestId(null)}
          actions={statusAction(selectedRequest, true)}
        />
      )}
    </section>
  )
}
