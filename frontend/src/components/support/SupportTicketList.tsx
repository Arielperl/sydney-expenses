import { ChevronLeft } from 'lucide-react'
import { useId, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { providerLabel } from '../../lib/support'
import { formatFullTimestamp, formatRelativeTime, parseServerTimestamp } from '../../lib/supportTime'
import type { SupportRequest } from '../../services/supportService'
import { Skeleton } from '../ui'
import { cx } from '../ui-classes'
import { SupportStatusBadge } from './SupportStatusBadge'

function TicketRow({
  request,
  now,
  staff,
  onOpen,
  actions,
}: {
  request: SupportRequest
  now: Date
  staff: boolean
  onOpen: () => void
  actions?: ReactNode
}) {
  const { t, i18n } = useTranslation()
  const subjectId = useId()
  const detailsId = useId()
  const updated = parseServerTimestamp(request.updated_at)
  const resolved = request.status === 'resolved'

  return (
    <li className="group relative flex items-center gap-2 transition-colors hover:bg-zinc-50/80 dark:hover:bg-zinc-800/40">
      <button
        type="button"
        onClick={onOpen}
        aria-labelledby={subjectId}
        aria-describedby={detailsId}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3.5 text-start focus-visible:-outline-offset-2 sm:px-5"
      >
        <span className="min-w-0 flex-1">
          <span className="flex min-w-0 items-baseline justify-between gap-3">
            <span
              id={subjectId}
              title={request.subject}
              className={cx('min-w-0 truncate text-sm font-semibold', resolved ? 'text-zinc-600 dark:text-zinc-400' : 'text-zinc-900 dark:text-zinc-50')}
              dir="auto"
            >
              {request.subject}
            </span>
            <time
              dateTime={updated.toISOString()}
              title={formatFullTimestamp(updated, i18n.language)}
              className="shrink-0 text-xs whitespace-nowrap text-zinc-500 dark:text-zinc-400"
            >
              {formatRelativeTime(updated, i18n.language, now)}
            </time>
          </span>
          <span id={detailsId} className="mt-1 block min-w-0">
            {staff && (request.business_name || request.requester_email) && (
              <span className="block truncate text-xs text-zinc-600 dark:text-zinc-300">
                {request.business_name}
                {request.business_name && request.requester_email && <span aria-hidden="true"> · </span>}
                {request.requester_email && <bdi dir="ltr">{request.requester_email}</bdi>}
              </span>
            )}
            <span className="mt-0.5 line-clamp-1 text-sm break-words text-zinc-500 dark:text-zinc-400" dir="auto">
              {request.message}
            </span>
            <span className="mt-2 flex flex-wrap items-center gap-1.5">
              <SupportStatusBadge status={request.status} />
              {request.provider && (
                <span className="inline-flex items-center rounded-full bg-zinc-100 px-2 py-0.5 text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
                  <span className="sr-only">{t('support.provider')}: </span>
                  {providerLabel(request.provider)}
                </span>
              )}
            </span>
          </span>
        </span>
        <span className="hidden shrink-0 items-center gap-1 text-xs font-medium text-brand-700 sm:inline-flex dark:text-brand-300" aria-hidden="true">
          <span className="underline-offset-2 group-hover:underline">{t('support.openConversation')}</span>
          <ChevronLeft className="h-4 w-4 ltr:rotate-180" />
        </span>
      </button>
      {actions && <div className="shrink-0 pe-3 sm:pe-4">{actions}</div>}
    </li>
  )
}

export function SupportTicketList({
  requests,
  now,
  staff = false,
  onOpen,
  renderActions,
}: {
  requests: SupportRequest[]
  now: Date
  staff?: boolean
  onOpen: (id: string) => void
  renderActions?: (request: SupportRequest) => ReactNode
}) {
  return (
    <ul className="divide-y divide-zinc-100 dark:divide-zinc-800">
      {requests.map((request) => (
        <TicketRow
          key={request.id}
          request={request}
          now={now}
          staff={staff}
          onOpen={() => onOpen(request.id)}
          actions={renderActions?.(request)}
        />
      ))}
    </ul>
  )
}

export function SupportTicketListSkeleton({ rows = 3, label }: { rows?: number; label: string }) {
  return (
    <div role="status" aria-label={label} className="divide-y divide-zinc-100 dark:divide-zinc-800">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="space-y-2.5 px-4 py-4 sm:px-5">
          <div className="flex justify-between gap-4">
            <Skeleton className="h-4 w-2/5" />
            <Skeleton className="h-3 w-16" />
          </div>
          <Skeleton className="h-3.5 w-3/4" />
          <Skeleton className="h-5 w-16 rounded-full" />
        </div>
      ))}
    </div>
  )
}
