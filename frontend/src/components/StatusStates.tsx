import { AlertCircle, Inbox } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Button, Skeleton } from './ui'

export function LoadingState({ label, variant = 'spinner' }: { label?: string; variant?: 'spinner' | 'skeleton' }) {
  const { t } = useTranslation()
  const text = label ?? t('common.loading')
  if (variant === 'skeleton') {
    return (
      <div role="status" className="space-y-4" aria-live="polite">
        <span className="sr-only">{text}</span>
        <div className="grid gap-4 sm:grid-cols-3">
          <Skeleton className="h-28 sm:col-span-3" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
        <Skeleton className="h-64" />
      </div>
    )
  }
  return (
    <div role="status" aria-live="polite" className="flex items-center justify-center gap-3 py-16 text-sm text-zinc-500 dark:text-zinc-400">
      <span
        aria-hidden="true"
        className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-300 border-t-brand-600 dark:border-zinc-700 dark:border-t-brand-400"
      />
      <span>{text}</span>
    </div>
  )
}

export function ErrorState({
  title,
  message,
  onRetry,
}: {
  title?: string
  message: string
  onRetry?: () => void
}) {
  const { t } = useTranslation()
  return (
    <div role="alert" className="flex gap-3 rounded-xl border border-danger-600/20 bg-danger-50 p-4 text-danger-700 dark:border-danger-500/25 dark:bg-danger-500/10 dark:text-danger-500">
      <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">{title ?? t('common.somethingWentWrong')}</p>
        <p className="mt-1 text-sm break-words text-danger-700/90 dark:text-danger-500/90">{message}</p>
        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry} className="mt-3">
            {t('common.tryAgain')}
          </Button>
        )}
      </div>
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string
  description?: string
  action?: ReactNode
  icon?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-zinc-300 bg-white/60 px-6 py-14 text-center dark:border-zinc-700 dark:bg-zinc-900/40">
      <span className="mb-4 grid h-11 w-11 place-items-center rounded-full bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400" aria-hidden="true">
        {icon ?? <Inbox className="h-5 w-5" />}
      </span>
      <p className="text-[0.9375rem] font-semibold text-zinc-900 dark:text-zinc-100">{title}</p>
      {description && <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-zinc-500 dark:text-zinc-400">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
