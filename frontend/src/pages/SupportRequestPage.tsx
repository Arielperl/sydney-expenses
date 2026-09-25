import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ChevronRight, MessageSquareText, Plus, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

import { EmptyState, ErrorState } from '../components/StatusStates'
import { SupportConversationDialog } from '../components/SupportConversationDialog'
import { NewSupportRequestDialog } from '../components/support/NewSupportRequestDialog'
import { SupportTicketList, SupportTicketListSkeleton } from '../components/support/SupportTicketList'
import { sortTickets } from '../lib/support'
import { Card, PageHeader, SegmentedControl } from '../components/ui'
import { buttonClasses } from '../components/ui-classes'
import { useNow } from '../hooks/useNow'
import { listOwnSupportRequests } from '../services/supportService'

type Filter = 'all' | 'open' | 'resolved'

export function SupportRequestPage() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const now = useNow()
  const [filter, setFilter] = useState<Filter>('all')
  const [showCreate, setShowCreate] = useState(false)
  const [sentNotice, setSentNotice] = useState(false)
  const [selectedRequestId, setSelectedRequestId] = useState<string | null>(null)
  const requests = useQuery({
    queryKey: ['support-requests-own'],
    queryFn: listOwnSupportRequests,
    // While a conversation is open, status changes made by staff show up within one sync interval.
    refetchInterval: selectedRequestId ? 3_000 : 15_000,
    refetchOnWindowFocus: 'always',
  })

  const all = sortTickets(requests.data ?? [])
  const openCount = all.filter((item) => item.status === 'open').length
  const visible = filter === 'all' ? all : all.filter((item) => item.status === filter)
  const selectedRequest = all.find((item) => item.id === selectedRequestId)
  const counts: Record<Filter, number> = { all: all.length, open: openCount, resolved: all.length - openCount }

  function openCreateForm() {
    setSentNotice(false)
    setShowCreate(true)
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <Link to="/imports" className="inline-flex items-center gap-1 text-sm font-medium text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">
          <ChevronRight className="h-4 w-4 ltr:rotate-180" aria-hidden="true" />
          {t('support.backToImports')}
        </Link>
        <div className="mt-3">
          <PageHeader
            title={t('support.title')}
            description={t('support.subtitle')}
            actions={
              <button type="button" className={buttonClasses('primary')} onClick={openCreateForm}>
                <Plus className="h-4 w-4" aria-hidden="true" />
                {t('support.newRequest')}
              </button>
            }
          />
        </div>
      </div>

      {sentNotice && (
        <div role="status" className="flex animate-pop-in items-start gap-3 rounded-xl border border-success-500/20 bg-success-50 px-4 py-3 text-sm text-success-700 dark:bg-success-500/10 dark:text-success-500">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <p className="flex-1">{t('support.sentNotice')}</p>
          <button type="button" onClick={() => setSentNotice(false)} aria-label={t('support.dismiss')} className="-m-1 grid h-7 w-7 shrink-0 place-items-center rounded-md hover:bg-success-500/10">
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      )}

      {requests.isError && !requests.data ? (
        <ErrorState message={t('support.loadError')} onRetry={() => void requests.refetch()} />
      ) : requests.data?.length === 0 ? (
        <EmptyState
          title={t('support.emptyTitle')}
          description={t('support.emptyDescription')}
          icon={<MessageSquareText className="h-5 w-5" />}
          action={
            <button type="button" className={buttonClasses('primary')} onClick={openCreateForm}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              {t('support.emptyAction')}
            </button>
          }
        />
      ) : (
        <Card aria-labelledby="support-requests-title" className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-100 px-4 py-3.5 sm:px-5 dark:border-zinc-800">
            <div className="min-w-0">
              <h2 id="support-requests-title" className="text-[0.9375rem] font-semibold text-zinc-900 dark:text-zinc-50">{t('support.myRequests')}</h2>
              {requests.data && (
                <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
                  {openCount > 0 ? t('support.summary', { count: openCount, total: all.length }) : t('support.summaryNoneOpen', { total: all.length })}
                </p>
              )}
            </div>
            {requests.data && (
              <SegmentedControl
                label={t('support.filterLabel')}
                value={filter}
                onChange={setFilter}
                options={(['all', 'open', 'resolved'] as const).map((value) => ({
                  value,
                  label: <>{t(`support.filters.${value}`)} <span className="figure text-zinc-500 dark:text-zinc-400">{counts[value]}</span></>,
                }))}
              />
            )}
          </div>
          {requests.isPending ? (
            <SupportTicketListSkeleton label={t('support.loading')} />
          ) : visible.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{t('support.noMatchesTitle')}</p>
              <p className="mt-1 text-sm text-zinc-500 dark:text-zinc-400">{t('support.noMatchesDescription')}</p>
            </div>
          ) : (
            <SupportTicketList requests={visible} now={now} onOpen={setSelectedRequestId} />
          )}
        </Card>
      )}

      {showCreate && (
        <NewSupportRequestDialog
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false)
            setSentNotice(true)
            setFilter('all')
            void queryClient.invalidateQueries({ queryKey: ['support-requests-own'] })
          }}
        />
      )}
      {selectedRequest && <SupportConversationDialog request={selectedRequest} staff={false} onClose={() => setSelectedRequestId(null)} />}
    </div>
  )
}
