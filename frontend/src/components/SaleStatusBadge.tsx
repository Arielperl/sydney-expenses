import { useTranslation } from 'react-i18next'

import type { SaleStatus } from '../types/sale'

const STATUS_STYLES: Record<SaleStatus, string> = {
  succeeded: 'bg-success-500/10 text-success-700 dark:text-success-400',
  pending: 'bg-accent-500/10 text-accent-600 dark:text-accent-400',
  failed: 'bg-danger-500/10 text-danger-700 dark:text-danger-400',
  refunded: 'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-400',
  partially_refunded: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
}

export function SaleStatusBadge({ status }: { status: SaleStatus }) {
  const { t } = useTranslation()
  return (
    <span
      className={[
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        STATUS_STYLES[status],
      ].join(' ')}
    >
      {t(`saleStatus.${status}`)}
    </span>
  )
}
