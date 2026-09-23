import { useTranslation } from 'react-i18next'

import type { DocumentStatus } from '../types/sale'

const STATUS_STYLES: Record<DocumentStatus, string> = {
  pending: 'bg-accent-500/10 text-accent-600 dark:text-accent-400',
  waiting_automatic: 'bg-accent-500/10 text-accent-600 dark:text-accent-400',
  issued: 'bg-success-500/10 text-success-700 dark:text-success-400',
  failed: 'bg-danger-500/10 text-danger-700 dark:text-danger-400',
  not_required: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400',
}

export function DocumentStatusBadge({ status }: { status: DocumentStatus }) {
  const { t } = useTranslation()
  return (
    <span
      className={[
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        STATUS_STYLES[status],
      ].join(' ')}
    >
      {t(`documentStatus.${status}`)}
    </span>
  )
}
