import { CheckCircle2, CircleDot } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { SupportRequest } from '../../services/supportService'
import { cx } from '../ui-classes'

/** Open and resolved differ by icon and wording, not only colour. */
export function SupportStatusBadge({ status, className }: { status: SupportRequest['status']; className?: string }) {
  const { t } = useTranslation()
  const open = status === 'open'
  const Icon = open ? CircleDot : CheckCircle2
  return (
    <span
      className={cx(
        'inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset',
        open
          ? 'bg-amber-50 text-amber-800 ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-300 dark:ring-amber-500/25'
          : 'bg-zinc-100 text-zinc-700 ring-zinc-200 dark:bg-zinc-800 dark:text-zinc-300 dark:ring-zinc-700',
        className,
      )}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {t(`support.status.${status}`)}
    </span>
  )
}
