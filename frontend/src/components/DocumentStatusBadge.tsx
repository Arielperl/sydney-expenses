import { useTranslation } from 'react-i18next'

import type { DocumentStatus } from '../types/expense'

const STATUS_STYLES: Record<DocumentStatus, string> = {
  missing: 'bg-danger-500/10 text-danger-700 dark:text-danger-400',
  suggested: 'bg-accent-500/10 text-accent-600 dark:text-accent-400',
  needs_review: 'bg-accent-500/10 text-accent-600 dark:text-accent-400',
  attached: 'bg-success-500/10 text-success-700 dark:text-success-400',
  not_required: 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-400',
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
