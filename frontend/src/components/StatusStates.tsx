import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

export function LoadingState({ label }: { label?: string }) {
  const { t } = useTranslation()
  return (
    <div role="status" className="flex items-center justify-center gap-3 py-16 text-zinc-500 dark:text-zinc-400">
      <span
        aria-hidden="true"
        className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-300 border-t-brand-600 dark:border-zinc-700"
      />
      <span>{label ?? t('common.loading')}</span>
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
    <div role="alert" className="rounded-lg border border-danger-500/30 bg-danger-50 p-4 text-danger-700 dark:bg-danger-500/10 dark:text-danger-400">
      <p className="font-semibold">{title ?? t('common.somethingWentWrong')}</p>
      <p className="mt-1 text-sm">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-md border border-danger-500/40 px-3 py-1.5 text-sm font-medium text-danger-700 hover:bg-danger-500/10 dark:text-danger-400"
        >
          {t('common.tryAgain')}
        </button>
      )}
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-zinc-300 bg-white px-6 py-16 text-center dark:border-zinc-700 dark:bg-zinc-900">
      <p className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-zinc-500 dark:text-zinc-400">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
